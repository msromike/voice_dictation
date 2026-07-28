"""PTT daemon: captures audio on the configured trigger, transcribes, injects at cursor.
Launched by vdict_tray.py, which writes config.json first. Requires it to exist."""

import sys

# Must precede the imports below -- winsound raises ImportError elsewhere.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

from vdict.audio import AudioCapture
from vdict.stt import STTEngine
from vdict.keyboard import KeyboardInjector, PTTListener
from vdict.config import load_config
import math
import struct
import wave
import os
import tempfile
import winsound

__version__ = "1.0.0"


def generate_tone(
        filename,
        freq=880.0,
        duration_ms=90,
        volume=0.3,
        sample_rate=44100):
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    fade_len = int(sample_rate * 0.01)

    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            t = float(i) / sample_rate
            sample = math.sin(2.0 * math.pi * freq * t)
            if i < fade_len:
                sample *= i / fade_len
            elif i > num_samples - fade_len:
                sample *= (num_samples - i) / fade_len
            packed_sample = struct.pack("<h", int(sample * volume * 32767.0))
            wav_file.writeframes(packed_sample)


# Every parameter is a tone characteristic with a default.
def generate_double_tone(  # noqa: PLR0913, PLR0917
        filename,
        freq=440.0,
        tone_duration_ms=90,
        gap_duration_ms=150,
        volume=0.3,
        sample_rate=44100):
    tone_samples = int(sample_rate * (tone_duration_ms / 1000.0))
    gap_samples = int(sample_rate * (gap_duration_ms / 1000.0))
    total_samples = (tone_samples * 2) + gap_samples
    fade_len = int(sample_rate * 0.01)

    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for i in range(total_samples):
            if i < tone_samples:
                t = float(i) / sample_rate
                sample = math.sin(2.0 * math.pi * freq * t)
                if i < fade_len:
                    sample *= i / fade_len
                elif i > tone_samples - fade_len:
                    sample *= (tone_samples - i) / fade_len
            elif i < tone_samples + gap_samples:
                sample = 0.0
            else:
                tone2_i = i - (tone_samples + gap_samples)
                t = float(tone2_i) / sample_rate
                sample = math.sin(2.0 * math.pi * freq * t)
                if tone2_i < fade_len:
                    sample *= tone2_i / fade_len
                elif tone2_i > tone_samples - fade_len:
                    sample *= (tone_samples - tone2_i) / fade_len
            packed_sample = struct.pack("<h", int(sample * volume * 32767.0))
            wav_file.writeframes(packed_sample)


# Generate UI tones to the temp directory on every launch
# 0.4 seconds at 16kHz. Shorter recordings are treated as accidental clicks.
MIN_RECORDING_SAMPLES = 6400

TEMP_DIR = tempfile.gettempdir()
TONE_HIGH = os.path.join(TEMP_DIR, "vdict_high.wav")
TONE_LOW = os.path.join(TEMP_DIR, "vdict_low.wav")
TONE_LOW_DOUBLE = os.path.join(TEMP_DIR, "vdict_low_double.wav")

generate_tone(TONE_HIGH, freq=783.99, duration_ms=80, volume=0.22275)
generate_tone(TONE_LOW, freq=523.25, duration_ms=90, volume=0.18225)
# The only double, and low on purpose. High is the user-action register, so a
# high double would be heard as a recording starting.
generate_double_tone(
    TONE_LOW_DOUBLE,
    freq=523.25,
    tone_duration_ms=90,
    gap_duration_ms=150,
    volume=0.18225)


def play_tone(tone_type, enabled=True):
    """Play the requested tone 100% asynchronously. enabled silences the
    per-dictation singles only -- the system double always sounds."""
    if tone_type in ("timeout", "ready"):
        tone = TONE_LOW_DOUBLE
    elif not enabled:
        return
    elif tone_type == "start":
        tone = TONE_HIGH
    elif tone_type == "stop":
        tone = TONE_LOW
    else:
        return
    winsound.PlaySound(tone, winsound.SND_FILENAME | winsound.SND_ASYNC)


def main():  # noqa: PLR0915
    """Main daemon loop"""
    config = load_config()

    # Initialize components
    audio = AudioCapture(
        sample_rate=config['audio']['sample_rate'],
        required_device=config['audio']['device']
    )

    stt = STTEngine(
        model_name=config['stt']['model'],
        device=config['stt']['device']
    )

    # Must keep the "Loading " prefix -- the tray matches on it to animate dots.
    print("\033[90mLoading model\033[0m")
    stt.load()

    keyboard = KeyboardInjector(
        preserve_clipboard=config['keyboard']['preserve_clipboard'])

    ptt = PTTListener(button=config['ptt']['button'])

    # Get prompt for jargon biasing
    prompt = config['stt']['prompt']

    # Get PTT mode and audio feedback settings
    ptt_mode = config['ptt']['mode']
    audio_feedback = config['audio']['feedback']

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
            play_tone("stop", enabled=audio_feedback)

            # Short-circuit on accidental/rapid clicks to prevent Whisper
            # thread blocking
            if len(audio_data) < MIN_RECORDING_SAMPLES:
                print(
                    f"\033[90m[{cycle}] Error: Recording too short (ignored).\033[0m")
                cycle += 1
                continue

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
