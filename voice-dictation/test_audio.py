"""
Test script for AudioCapture - Chunk 2 validation

Tests audio recording: press Enter to start, Enter again to stop.
Verifies audio capture returns valid numpy array with samples.
"""

import sys
sys.path.insert(0, '.')

from vdict.audio import AudioCapture
import numpy as np


def main():
    print("AudioCapture Test")
    print("=" * 50)
    print("Initializing audio capture...")
    
    try:
        audio = AudioCapture(sample_rate=16000)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        print("Plug in microphone and restart.")
        return 1
    
    print("Audio capture initialized!")
    print()
    print("Test: Record 2-second audio clip")
    print("Press Enter to start recording...")
    input()
    
    audio.start_capture()
    print("[RECORDING] Speak into microphone...")
    print("Press Enter to stop...")
    input()
    
    audio_data = audio.stop_capture()
    print(f"[STOPPED]")
    print()
    
    # Verify audio data
    print("Validation:")
    print(f"  Samples captured: {len(audio_data)}")
    print(f"  Duration: {len(audio_data) / 16000:.2f} seconds")
    print(f"  Data type: {audio_data.dtype}")
    print(f"  Shape: {audio_data.shape}")
    print(f"  Min value: {audio_data.min():.4f}")
    print(f"  Max value: {audio_data.max():.4f}")
    print()
    
    # Pass criteria
    if len(audio_data) > 0:
        print("✓ PASS: Audio data captured")
    else:
        print("✗ FAIL: No audio data")
        return 1
    
    if audio_data.dtype == np.float32:
        print("✓ PASS: Correct data type (float32)")
    else:
        print(f"✗ FAIL: Wrong data type ({audio_data.dtype})")
        return 1
    
    if len(audio_data.shape) == 1:
        print("✓ PASS: 1D array (flattened)")
    else:
        print(f"✗ FAIL: Wrong shape ({audio_data.shape})")
        return 1
    
    print()
    print("Chunk 2 validation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
