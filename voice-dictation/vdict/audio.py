"""
Module: audio.py
Purpose: Audio capture with PTT (push-to-talk) support

Responsibilities:
  - Capture audio from default microphone
  - Start/stop recording on demand
  - Buffer audio during PTT hold
  - Return audio data as numpy array
"""

import time

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Audio capture engine for PTT voice recording"""

    # Device resolution plus a retry loop. Splitting it would spread one
    # decision across two functions.
    def __init__(self, sample_rate=16000, required_device="",  # noqa: C901
                 retry_attempts=5, retry_delay=1.0):
        """
        Initialize audio capture

        Args:
            sample_rate: Audio sample rate (Whisper expects 16kHz)
            required_device: Substring to match in device name (hardcoded for user's headset)
            retry_attempts: Times to re-query devices before giving up (survives
                USB re-enumeration races on sleep/wake)
            retry_delay: Seconds to wait between retry attempts
        """
        self.sample_rate = sample_rate
        self.recording = False
        self.buffer = []
        self.stream = None
        self.device_id = None

        # Find required device by name, retrying to survive transient USB
        # re-enumeration (e.g. sleep/wake); crash-fast once retries are
        # exhausted
        last_error = None
        for attempt in range(retry_attempts):
            try:
                # Resolve against WASAPI only. PortAudio lists every mic once
                # per Windows backend, and the tray's device dropdown
                # enumerates WASAPI -- matching the same backend here keeps
                # both sides naming the same device.
                wasapi = next(
                    (i for i, api in enumerate(sd.query_hostapis())
                     if api['name'] == 'Windows WASAPI'), None)

                if wasapi is not None:
                    if required_device:
                        for idx, device in enumerate(sd.query_devices()):
                            if (device['hostapi'] == wasapi
                                    and required_device in device['name']
                                    and device['max_input_channels'] > 0):
                                self.device_id = idx
                                break
                    else:
                        # System default, as WASAPI reports it
                        default_id = sd.query_hostapis(
                            wasapi)['default_input_device']
                        if default_id >= 0:
                            self.device_id = default_id

                if self.device_id is not None:
                    break
            except Exception as e:
                last_error = e

            if attempt < retry_attempts - 1:
                time.sleep(retry_delay)

        if self.device_id is None:
            import sys
            if last_error:
                print(f"\033[91m[ERROR] Device lookup failed: {last_error}\033[0m")
            print("\033[91m[ERROR] Configured microphone not found. Pick a "
                  "different one in Settings, or reconnect the device, then "
                  "click Save & Restart.\033[0m")
            from .config import EXIT_NO_MICROPHONE
            sys.exit(EXIT_NO_MICROPHONE)

    def start_capture(self):
        """Start capturing audio from microphone"""
        if self.recording:
            return

        self.recording = True
        self.buffer = []

        # Create input stream with callback to buffer audio.
        #
        # auto_convert enables the Windows audio engine's resampler. WASAPI
        # shared mode otherwise accepts only the device's native rate (48kHz
        # on typical hardware), while Whisper's mel filterbank is defined
        # against 16kHz and cannot take anything else. MME performed this same
        # conversion implicitly; doing it through WASAPI just makes it
        # explicit, and on a lower-latency backend.
        self.stream = sd.InputStream(
            device=self.device_id,
            samplerate=self.sample_rate,
            channels=1,  # Mono
            dtype='float32',
            callback=self._audio_callback,
            extra_settings=sd.WasapiSettings(auto_convert=True)
        )
        self.stream.start()

    def _audio_callback(self, indata, frames, time, status):
        """
        Internal callback for audio stream (runs in background thread)

        Args:
            indata: Audio samples from input device
            frames: Number of frames
            time: Timestamp info
            status: Stream status flags
        """
        if status:
            print(f"Audio stream status: {status}")

        if self.recording:
            # Append audio data to buffer (copy to prevent memory issues)
            self.buffer.append(indata.copy())

    def stop_capture(self):
        """
        Stop capturing and return audio data

        Returns:
            np.ndarray: Audio samples as float32 array, shape (samples,)
        """
        if not self.recording:
            return np.array([], dtype=np.float32)

        self.recording = False

        # Stop and close stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Concatenate buffered chunks into single array
        if self.buffer:
            audio_data = np.concatenate(self.buffer, axis=0)
            # Flatten to 1D array (samples,)
            audio_data = audio_data.flatten()

            # Peak-normalize so a quiet/distant mic signal isn't left near
            # the noise floor -- boosts effective SNR before transcription
            peak = np.abs(audio_data).max()
            if peak > 0:
                audio_data = audio_data * (0.95 / peak)
        else:
            audio_data = np.array([], dtype=np.float32)

        return audio_data
