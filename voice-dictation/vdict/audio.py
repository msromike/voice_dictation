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

    def __init__(self, sample_rate=16000, required_device="USB 2.0 Camera",
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
        # re-enumeration (e.g. sleep/wake); crash-fast once retries are exhausted
        last_error = None
        for attempt in range(retry_attempts):
            try:
                devices = sd.query_devices()
                for idx, device in enumerate(devices):
                    if required_device in device['name'] and device['max_input_channels'] > 0:
                        self.device_id = idx
                        break
                if self.device_id is not None:
                    break
            except Exception as e:
                last_error = e

            if attempt < retry_attempts - 1:
                time.sleep(retry_delay)

        if self.device_id is None:
            if last_error is not None:
                raise RuntimeError(f"Audio device error: {last_error}") from last_error
            raise RuntimeError(f"ERROR: Required microphone not found: '{required_device}'\n"
                               f"       Plug in your headset and restart.")
    
    def start_capture(self):
        """Start capturing audio from microphone"""
        if self.recording:
            return
            
        self.recording = True
        self.buffer = []
        
        # Create input stream with callback to buffer audio
        self.stream = sd.InputStream(
            device=self.device_id,
            samplerate=self.sample_rate,
            channels=1,  # Mono
            dtype='float32',
            callback=self._audio_callback
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
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording
