import math
import struct
import wave
import winsound
import time


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


def generate_double_tone(
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
            # First tone
            if i < tone_samples:
                t = float(i) / sample_rate
                sample = math.sin(2.0 * math.pi * freq * t)
                if i < fade_len:
                    sample *= i / fade_len
                elif i > tone_samples - fade_len:
                    sample *= (tone_samples - i) / fade_len

            # Gap (Pure silence)
            elif i < tone_samples + gap_samples:
                sample = 0.0

            # Second tone
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


print("Generating baked tones (3 separate waves)...")
generate_tone("test_start.wav", freq=783.99, duration_ms=80, volume=0.22275)
generate_tone("test_stop.wav", freq=523.25, duration_ms=90, volume=0.18225)
generate_double_tone(
    "test_timeout.wav",
    freq=523.25,
    tone_duration_ms=90,
    gap_duration_ms=150,
    volume=0.18225)

print("1. Playing Start (Push) Tone...")
winsound.PlaySound("test_start.wav", winsound.SND_FILENAME)
time.sleep(1)

print("2. Playing Stop (After Push) Tone...")
winsound.PlaySound("test_stop.wav", winsound.SND_FILENAME)
time.sleep(1)

print("3. Playing Baked Timeout Tone ASYNCHRONOUSLY...")
t0 = time.time()
winsound.PlaySound(
    "test_timeout.wav",
    winsound.SND_FILENAME | winsound.SND_ASYNC)
t1 = time.time()

print(f"--> PlaySound function returned in {t1 - t0:.5f} seconds!")
print("--> The Python script is immediately free to capture mic data while the sound plays in the background...")

# Sleep just to keep the script alive long enough for you to hear the
# background sound before Python exits
time.sleep(1.0)
print("Done testing.")
