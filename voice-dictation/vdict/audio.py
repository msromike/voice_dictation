"""
Module: audio.py
Purpose: Audio capture with PTT (push-to-talk) support

Responsibilities:
  - Capture audio from default microphone
  - Start/stop recording on demand
  - Buffer audio during PTT hold
  - Return audio data as numpy array
"""

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Audio capture engine for PTT voice recording"""
    
    def __init__(self, sample_rate=16000, required_device="USB 2.0 Camera"):
        """
        Initialize audio capture
        
        Args:
            sample_rate: Audio sample rate (Whisper expects 16kHz)
            required_device: Substring to match in device name (hardcoded for user's headset)
        """
        self.sample_rate = sample_rate
        self.recording = False
        self.buffer = []
        self.stream = None
        self.device_id = None
        
        # Find required device by name (crash-fast on external boundary)
        try:
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                if required_device in device['name'] and device['max_input_channels'] > 0:
                    self.device_id = idx
                    break
            
            if self.device_id is None:
                raise RuntimeError(f"ERROR: Required microphone not found: '{required_device}'\n"
                                   f"       Plug in your headset and restart.")
                
        except Exception as e:
            if "Required microphone not found" in str(e):
                raise
            raise RuntimeError(f"Audio device error: {e}") from e
    
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
        else:
            audio_data = np.array([], dtype=np.float32)
        
        return audio_data
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording
