"""
Test script for STTEngine - Chunk 3 validation

Tests Whisper model loading and transcription.
Records ~3 seconds of audio and transcribes it.
"""

from vdict.stt import STTEngine
from vdict.audio import AudioCapture
import sys
sys.path.insert(0, '.')


def main():
    print("STTEngine Test")
    print("=" * 50)

    # Initialize STT engine
    print("Initializing STT engine...")
    stt = STTEngine(model_name="base.en", device="cpu")

    # Load model (downloads ~140MB on first run)
    stt.load()
    print()

    # Initialize audio (requires USB 2.0 Camera headset)
    print("Initializing audio capture...")
    audio = AudioCapture(sample_rate=16000, required_device="USB 2.0 Camera")
    print("Audio capture initialized!")
    print()

    # Record audio
    print("Test: Record and transcribe speech")
    print("Press Enter to start recording...")
    input()

    audio.start_capture()
    print("[RECORDING] Speak clearly into microphone...")
    print("Press Enter to stop...")
    input()

    audio_data = audio.stop_capture()
    print(f"[STOPPED] Captured {len(audio_data)} samples")
    print()

    # Transcribe
    print("[TRANSCRIBING...]")
    text = stt.transcribe(audio_data)
    print()

    # Display result
    print("=" * 50)
    print("Transcribed text:")
    print(f'"{text}"')
    print("=" * 50)
    print()

    # Validation
    if len(text) > 0:
        print("✓ PASS: Transcription returned text")
        print()
        print("Chunk 3 validation complete!")
        return 0
    else:
        print("✗ FAIL: Empty transcription (speak louder or check mic)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
