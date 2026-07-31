"""PTT daemon: captures audio on the configured trigger, transcribes, injects at cursor.
Launched by vdict_tray.py, which writes config.json first. Requires it to exist."""

import sys

# Must precede the imports below -- vdict.daemon.audio is WASAPI-specific and
# the whole app is Windows-only regardless.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

from vdict.daemon.audio import AudioCapture
from vdict.daemon.stt import STTEngine
from vdict.daemon.keyboard import KeyboardInjector, PTTListener
from vdict.common.config import load_config, load_vocabulary
from vdict.common.output import log
import wave
import os
import queue
from datetime import datetime
import numpy as np
import sounddevice as sd

__version__ = "1.0.0"


# 0.4 seconds at 16kHz. Shorter recordings are treated as accidental clicks.
MIN_RECORDING_SAMPLES = 6400


def _load_tone(filename):
    """Read a WAV file into (sample_rate, float32 samples -1.0 to 1.0)."""
    with wave.open(filename, "rb") as wav_file:
        rate = wav_file.getframerate()
        raw_bytes = wav_file.readframes(wav_file.getnframes())
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return rate, samples


SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "vdict", "sounds")
_high_rate, TONE_HIGH = _load_tone(os.path.join(SOUNDS_DIR, "high.wav"))
_low_rate, TONE_LOW = _load_tone(os.path.join(SOUNDS_DIR, "low.wav"))
_double_rate, TONE_LOW_DOUBLE = _load_tone(os.path.join(SOUNDS_DIR, "low_double.wav"))
assert _high_rate == _low_rate == _double_rate
TONE_SAMPLE_RATE = _high_rate

_output_stream = None
_tone_queue = queue.Queue()
_current_tone = None
_current_tone_pos = 0


def _output_callback(outdata, frames, _time_info, status):
    """Fills outdata in place -- called by PortAudio's own real-time
    thread whenever it needs more data. Never blocks."""
    global _current_tone, _current_tone_pos
    if status:
        log("note", f"Output stream status: {status}")

    filled = 0
    while filled < frames:
        if _current_tone is None:
            try:
                _current_tone = _tone_queue.get_nowait()
                _current_tone_pos = 0
            except queue.Empty:
                outdata[filled:] = 0.0
                return

        remaining = len(_current_tone) - _current_tone_pos
        take = min(remaining, frames - filled)
        outdata[filled:filled + take] = (
            _current_tone[_current_tone_pos:_current_tone_pos + take])
        _current_tone_pos += take
        filled += take

        if _current_tone_pos >= len(_current_tone):
            _current_tone = None


def _resolve_output_device():
    """WASAPI's own default output endpoint. No retry -- an output device
    disappearing mid-session is not the microphone's recovery problem."""
    wasapi = next(
        (i for i, api in enumerate(sd.query_hostapis())
         if api["name"] == "Windows WASAPI"), None)
    if wasapi is None:
        log("error", "Windows WASAPI audio backend not available.")
        sys.exit(1)
    default_id = sd.query_hostapis(wasapi)["default_output_device"]
    if default_id < 0:
        log("error", "No default WASAPI output device found.")
        sys.exit(1)
    return default_id


TONE_VOLUME_HIGH = 0.22275
TONE_VOLUME_LOW = 0.18225


def play_tone(tone_type, enabled=True, volume=1.0):
    """Play the requested tone 100% asynchronously. enabled silences start,
    stop and too_short; ready and timeout always sound."""
    if tone_type in ("timeout", "ready"):
        tone, reference_volume = TONE_LOW_DOUBLE, TONE_VOLUME_LOW
    elif not enabled:
        return
    elif tone_type == "start":
        tone, reference_volume = TONE_HIGH, TONE_VOLUME_HIGH
    elif tone_type == "stop":
        tone, reference_volume = TONE_LOW, TONE_VOLUME_LOW
    elif tone_type == "too_short":
        tone, reference_volume = TONE_LOW_DOUBLE, TONE_VOLUME_LOW
    else:
        return
    scaled = (tone * (reference_volume * volume)).reshape(-1, 1)
    _tone_queue.put(scaled)


def main():  # noqa: PLR0915
    """Main daemon loop"""
    config = load_config()

    # Initialize components
    audio = AudioCapture(
        required_device=config.audio.device
    )

    stt = STTEngine(
        model_name=config.stt.model,
        device=config.stt.device
    )

    log("loading", "Loading model")
    stt.load()

    keyboard = KeyboardInjector(
        preserve_clipboard=config.keyboard.preserve_clipboard)

    ptt = PTTListener(button=config.ptt.button)

    global _output_stream
    _output_stream = sd.OutputStream(
        samplerate=TONE_SAMPLE_RATE,
        device=_resolve_output_device(),
        channels=1,
        dtype="float32",
        callback=_output_callback,
        extra_settings=sd.WasapiSettings(auto_convert=True))
    _output_stream.start()

    # Get prompt for jargon biasing
    prompt = load_vocabulary()

    # Get PTT mode and audio feedback settings
    ptt_mode = config.ptt.mode
    audio_feedback = config.audio.feedback

    # Closes the session block. Dashes, not the startup header's equals signs --
    # this divides sections, it does not open the log. Blank line after.
    log("ready", f"Voice Dictation v{__version__} READY")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("block", f" {timestamp} ".center(60, "-"))
    log("block", "")
    play_tone("ready", enabled=audio_feedback)

    try:
        while True:
            # Wait for button to be pressed
            ptt.wait_for_press()

            # Fire the GPU primer to wake up CUDA cores while user is talking
            stt.wake_gpu()

            # If toggle mode, wait for release before starting
            if ptt_mode == "toggle":
                ptt.wait_for_release()

            play_tone("start", enabled=audio_feedback)
            log("rec", "")
            audio.start_capture()

            if ptt_mode == "toggle":
                # Wait for second click to stop (with timeout)
                pressed = ptt.wait_for_press(timeout_secs=120.0)
                if not pressed:
                    play_tone("timeout", enabled=audio_feedback)
                    log("note", "Timeout reached.")
                    log("done", "")
                    audio.stop_capture()
                    continue
                ptt.wait_for_release()
            else:
                # Hold mode: stop immediately on release, no timeout
                ptt.wait_for_release()

            audio_data = audio.stop_capture()

            # Short captures can make Whisper hallucinate plausible-but-false
            # text instead of returning empty -- see spike_notes.txt.
            if len(audio_data) < MIN_RECORDING_SAMPLES:
                play_tone("too_short", enabled=audio_feedback)
                log("note", "Not transcribed -- hold the button at least 0.4s.")
                log("done", "")
                continue

            play_tone("stop", enabled=audio_feedback)

            # Transcribe with prompt for jargon biasing
            text = stt.transcribe(audio_data, initial_prompt=prompt)

            if text:
                log("transcript", text)
                keyboard.inject(text)
            else:
                log("note", "No speech detected.")

            log("done", "")

    except KeyboardInterrupt:
        print("\n\n\033[90mStopped\033[0m")
        ptt.stop()


if __name__ == "__main__":
    main()
