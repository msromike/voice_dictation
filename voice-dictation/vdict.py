"""PTT daemon: captures audio on the configured trigger, transcribes, injects at cursor.
Launched by vdict_tray.py, which writes config.json first. Requires it to exist."""

import sys

# Must precede the imports below -- vdict.audio is WASAPI-specific and the
# whole app is Windows-only regardless.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

from vdict.audio import AudioCapture
from vdict.stt import STTEngine
from vdict.keyboard import KeyboardInjector, PTTListener
from vdict.config import load_config, load_vocabulary
import wave
import os
import threading
import queue
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
_KEEPALIVE_CHUNK = np.zeros((int(TONE_SAMPLE_RATE * 0.02), 1), dtype=np.float32)


def _audio_writer_loop():
    """Owns every write to the stream. A queued tone plays immediately;
    otherwise silence, so the stream never drains and clicks on resume."""
    assert _output_stream is not None
    while True:
        try:
            data = _tone_queue.get(timeout=0.02)
        except queue.Empty:
            data = _KEEPALIVE_CHUNK
        _output_stream.write(data)


def _resolve_output_device():
    """WASAPI's own default output endpoint. No retry -- an output device
    disappearing mid-session is not the microphone's recovery problem."""
    wasapi = next(
        (i for i, api in enumerate(sd.query_hostapis())
         if api["name"] == "Windows WASAPI"), None)
    if wasapi is None:
        sys.exit("Windows WASAPI audio backend not available.")
    default_id = sd.query_hostapis(wasapi)["default_output_device"]
    if default_id < 0:
        sys.exit("No default WASAPI output device found.")
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

    # Must keep the "Loading " prefix -- the tray matches on it to animate dots.
    print("\033[90mLoading model\033[0m")
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
        extra_settings=sd.WasapiSettings(auto_convert=True))
    _output_stream.start()
    threading.Thread(target=_audio_writer_loop, daemon=True).start()

    # Get prompt for jargon biasing
    prompt = load_vocabulary()

    # Get PTT mode and audio feedback settings
    ptt_mode = config.ptt.mode
    audio_feedback = config.audio.feedback

    # Closes the session block. Dashes, not the startup header's equals signs --
    # this divides sections, it does not open the log. Blank line after.
    print(f"\033[90mVoice Dictation v{__version__} READY\033[0m")
    print("\033[90m" + "-" * 60 + "\033[0m")
    print()
    play_tone("ready", enabled=audio_feedback)

    try:
        cycle = 0
        while True:
            # Wait for button to be pressed
            ptt.wait_for_press()

            # Fire the GPU primer to wake up CUDA cores while user is talking
            stt.wake_gpu()

            # If toggle mode, wait for release before starting
            if ptt_mode == "toggle":
                ptt.wait_for_release()

            play_tone("start", enabled=audio_feedback)
            print(f"\033[90m[{cycle}] Recording...\033[0m")
            audio.start_capture()

            if ptt_mode == "toggle":
                # Wait for second click to stop (with timeout)
                pressed = ptt.wait_for_press(timeout_secs=120.0)
                if not pressed:
                    play_tone("timeout", enabled=audio_feedback)
                    print(f"\033[90m[{cycle}] Error: Timeout reached.\033[0m")
                    print(f"\033[90m[{cycle}] Closed (Timeout).\033[0m")
                    audio.stop_capture()
                    cycle += 1
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
                print(
                    f"\033[90m[{cycle}] Not transcribed -- hold the button "
                    "at least 0.4s.\033[0m")
                cycle += 1
                continue

            play_tone("stop", enabled=audio_feedback)

            # Transcribe with prompt for jargon biasing
            text = stt.transcribe(audio_data, initial_prompt=prompt)

            if text:
                print(text)
                keyboard.inject(text)
            else:
                print(f"\033[90m[{cycle}] Error: No speech detected.\033[0m")

            print(f"\033[90m[{cycle}] Closed.\033[0m")
            cycle += 1

    except KeyboardInterrupt:
        print("\n\n\033[90mStopped\033[0m")
        ptt.stop()


if __name__ == "__main__":
    main()
