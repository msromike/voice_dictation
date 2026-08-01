"""Audio capture from the configured microphone, buffered while PTT is held."""

import time

import numpy as np
import sounddevice as sd

from vdict.common.output import log


class AudioCapture:
    """Audio capture engine for PTT voice recording"""

    def _find_device_id(self, required_device):
        """Match required_device against WASAPI input devices, or WASAPI's own
        default when empty. WASAPI only -- PortAudio lists each mic once per backend."""
        wasapi = next(
            (i for i, api in enumerate(sd.query_hostapis())
             if api['name'] == 'Windows WASAPI'), None)
        if wasapi is None:
            return None

        if not required_device:
            default_id = sd.query_hostapis(wasapi)['default_input_device']
            return default_id if default_id >= 0 else None

        for idx, device in enumerate(sd.query_devices()):
            if (device['hostapi'] == wasapi
                    and required_device in device['name']
                    and device['max_input_channels'] > 0):
                return idx
        return None

    def __init__(self, sample_rate=16000, required_device="",
                 retry_attempts=5, retry_delay=1.0):
        """Resolve the configured input device. Opens no stream.
        Whisper requires sample_rate=16000. required_device matches a name substring."""
        self.sample_rate = sample_rate
        self.required_device = required_device
        self.recording = False
        self.buffer = []
        self.stream = None
        self.device_id = None

        # Retry to survive transient USB re-enumeration on sleep/wake. Crash-
        # fast once exhausted; the final sleep is wasted but not worth a branch.
        last_error = None
        for _ in range(retry_attempts):
            try:
                device_id = self._find_device_id(required_device)
            except sd.PortAudioError as e:
                device_id, last_error = None, e

            if device_id is not None:
                self.device_id = device_id
                break

            time.sleep(retry_delay)

        if self.device_id is None:
            self._exit_no_microphone(
                f"Device lookup failed: {last_error}" if last_error else None)

    def _exit_no_microphone(self, detail):
        """Log the standard no-microphone message and exit. Shared by device
        lookup at startup and stream-open failure mid-session."""
        import sys
        if self.required_device:
            text = f'Microphone "{self.required_device}" not found'
            suffix = (". Reconnect the device or pick a different one in "
                      "Settings -- System Default is recommended.")
        else:
            text = "No default microphone found"
            suffix = ". Reconnect the device or pick a different one in Settings."
        if detail:
            text += f" ({detail})"
        text += suffix
        log("mic-fault", text)
        sys.exit(1)

    def start_capture(self):
        """Start capturing audio from microphone"""
        if self.recording:
            return

        self.recording = True
        self.buffer = []

        # auto_convert enables the Windows resampler. WASAPI shared mode accepts
        # only the device's native rate; Whisper's mel filterbank requires 16kHz.
        try:
            self.stream = sd.InputStream(
                device=self.device_id,
                samplerate=self.sample_rate,
                channels=1,  # Mono
                dtype='float32',
                callback=self._audio_callback,
                extra_settings=sd.WasapiSettings(auto_convert=True)
            )
            self.stream.start()
        except sd.PortAudioError as e:
            self._exit_no_microphone(f"Microphone disconnected: {e}")

    def _audio_callback(self, indata, frames, time, status):
        """Buffer incoming samples. Runs on the sounddevice background thread."""
        if status:
            log("note", f"Audio stream status: {status}")

        if self.recording:
            # Append audio data to buffer (copy to prevent memory issues)
            self.buffer.append(indata.copy())

    def stop_capture(self):
        """Stop the stream and return buffered audio, peak-normalized.
        Returns a float32 ndarray of shape (samples,), empty if not recording."""
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
