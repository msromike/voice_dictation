"""
Voice Dictation Daemon - System-wide PTT voice-to-text

Main entry point for background daemon that listens for middle mouse button,
captures audio, transcribes via Whisper, and injects text at cursor.

Usage:
    python vdict.py                      # Run with default profile
    python vdict.py --profile radio      # Run with radio profile
    python vdict.py --profile general    # Run with general profile
"""

import sys
import argparse
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

def generate_tone(filename, freq=880.0, duration_ms=90, volume=0.3, sample_rate=44100):
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

def generate_double_tone(filename, freq=440.0, tone_duration_ms=90, gap_duration_ms=150, volume=0.3, sample_rate=44100):
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
TEMP_DIR = tempfile.gettempdir()
TONE_START = os.path.join(TEMP_DIR, "vdict_start.wav")
TONE_STOP = os.path.join(TEMP_DIR, "vdict_stop.wav")
TONE_TIMEOUT = os.path.join(TEMP_DIR, "vdict_timeout.wav")

generate_tone(TONE_START, freq=783.99, duration_ms=80, volume=0.22275)
generate_tone(TONE_STOP, freq=523.25, duration_ms=90, volume=0.18225)
generate_double_tone(TONE_TIMEOUT, freq=523.25, tone_duration_ms=90, gap_duration_ms=150, volume=0.18225)

def play_tone(tone_type):
    """Play the requested tone 100% asynchronously"""
    if tone_type == "start":
        winsound.PlaySound(TONE_START, winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif tone_type == "stop":
        winsound.PlaySound(TONE_STOP, winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif tone_type == "timeout":
        winsound.PlaySound(TONE_TIMEOUT, winsound.SND_FILENAME | winsound.SND_ASYNC)



def main():
    """Main daemon loop"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Voice Dictation - PTT voice-to-text')
    parser.add_argument('--profile', type=str, default=None,
                       help='Configuration profile to use (dev, radio, general)')
    args = parser.parse_args()
    
    # Load configuration with selected profile
    config = load_config(profile_name=args.profile)
    
    # Initialize components
    audio = AudioCapture(
        sample_rate=config['audio']['sample_rate'],
        required_device=config['audio']['device']
    )
    
    stt = STTEngine(
        model_name=config['stt']['model'],
        device=config['stt']['device']
    )
    
    stt.load()
    
    keyboard = KeyboardInjector(
        preserve_clipboard=config.get('keyboard', {}).get('preserve_clipboard', False)
    )
    
    ptt = PTTListener(button=config['ptt']['button'])
    
    # Get prompt for jargon biasing
    prompt = config['stt'].get('prompt', '')
    
    print("\033[90mVoice Dictation READY\033[0m")
    print(f"\033[90mClick {config['ptt']['button'].upper()} MOUSE BUTTON to paste at cursor\033[0m")
    
    try:
        cycle = 0
        while True:
            # Wait for MMB click to start (press then release)
            ptt.wait_for_press()
            ptt.wait_for_release()
            play_tone("start")
            print(f"\033[90m[{cycle}] Recording...\033[0m")
            audio.start_capture()
            
            # Wait for MMB click to stop (press then release) with 120s timeout
            pressed = ptt.wait_for_press(timeout_secs=120.0)
            if not pressed:
                play_tone("timeout")
                print(f"\033[90m[{cycle}] Error: Timeout reached.\033[0m")
                print(f"\033[90m[{cycle}] Closed (Timeout).\033[0m")
                audio.stop_capture()
                cycle += 1
                continue
                
            ptt.wait_for_release()
            audio_data = audio.stop_capture()
            play_tone("stop")
            
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

