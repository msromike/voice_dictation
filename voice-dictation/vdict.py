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
    
    keyboard = KeyboardInjector()
    
    ptt = PTTListener(button=config['ptt']['button'])
    
    # Get prompt for jargon biasing
    prompt = config['stt'].get('prompt', '')
    
    print("Voice Dictation READY")
    print(f"Click {config['ptt']['button'].upper()} MOUSE BUTTON to paste at cursor")
    
    try:
        cycle = 0
        while True:
            # Wait for MMB click to start (press then release)
            ptt.wait_for_press()
            ptt.wait_for_release()
            print(f"[{cycle}] Recording...")
            audio.start_capture()
            
            # Wait for MMB click to stop (press then release) with 120s timeout
            pressed = ptt.wait_for_press(timeout_secs=120.0)
            if not pressed:
                print(f"[{cycle}] Error: 2-minute time limit reached. Discarding audio.")
                audio.stop_capture()
                continue
                
            ptt.wait_for_release()
            audio_data = audio.stop_capture()
            
            # Transcribe with prompt for jargon biasing
            text = stt.transcribe(audio_data, initial_prompt=prompt)
            
            if text:
                print(f"[{cycle}] {text}")
                keyboard.inject(text)
            
            cycle += 1
    
    except KeyboardInterrupt:
        print("\n\nStopped")
        ptt.stop()


if __name__ == "__main__":
    main()

