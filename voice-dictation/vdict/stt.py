"""
Module: stt.py
Purpose: Whisper STT (speech-to-text) engine

Responsibilities:
  - Load Whisper model (Faster-Whisper)
  - Transcribe audio to text
  - Handle CPU/GPU device selection

Performance (tested):
  - CPU: 200-300ms per 1-3 second phrase (FASTER for short clips)
  - GPU: 175-340ms (context swap overhead kills it for short clips)

Design Decision: Default to CPU for PTT use case
"""

from faster_whisper import WhisperModel
import os
import glob
import threading
import numpy as np

# Fix CUDA DLL resolution for Python 3.8+ on Windows (for ctranslate2)
import site

for sp in site.getsitepackages() + [site.getusersitepackages()]:
    nvidia_bins = glob.glob(os.path.join(sp, "nvidia", "*", "bin"))
    if nvidia_bins:
        os.environ["PATH"] = ";".join(nvidia_bins) + ";" + os.environ.get("PATH", "")
        break

# Suppress HuggingFace cache symlink and auth warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

class STTEngine:
    """Speech-to-text engine using Faster-Whisper"""

    def __init__(self, model_name="base.en", device="cpu"):
        """
        Initialize STT engine

        Args:
            model_name: Whisper model size (tiny.en, base.en, small.en)
            device: "cpu" or "cuda" (CPU recommended for PTT)
        """
        self.model_name = model_name
        self.device = device
        self.model = None

    def load(self):
        """Load Whisper model into memory (crash-fast on external boundary)"""
        try:
            # Deterministic check for local cache to signal UI
            from huggingface_hub import snapshot_download
            from huggingface_hub.errors import LocalEntryNotFoundError
            try:
                repo_id = f"Systran/faster-whisper-{self.model_name}"
                snapshot_download(repo_id=repo_id, local_files_only=True)
            except LocalEntryNotFoundError:
                print(f"[SYSTEM] INITIATING DOWNLOAD: {self.model_name}")

            # CPU requires float32. CUDA runs fastest on float16.
            compute_type = "float16" if self.device == "cuda" else "float32"
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=compute_type)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load Whisper model '{
                    self.model_name}': {e}") from e

    def wake_gpu(self):
        """
        Fire a dummy transcription on a background thread to force the GPU
        to spool up to P-State 0. Call this exactly when PTT is pressed.
        """
        if self.device != "cuda" or self.model is None:
            return

        def _primer():
            try:
                # 0.1 seconds of absolute silence
                dummy = np.zeros(1600, dtype=np.float32)
                _ = list(
                    self.model.transcribe(
                        dummy,
                        beam_size=1,
                        vad_filter=False))
            except Exception:
                pass

        threading.Thread(target=_primer, daemon=True).start()

    def transcribe(self, audio_data, initial_prompt=""):
        """
        Transcribe audio to text

        Args:
            audio_data: Audio samples (numpy array, 16kHz float32)
            initial_prompt: Jargon/vocabulary hints for Whisper (comma-separated terms)

        Returns:
            str: Transcribed text (empty string if no speech detected)
        """
        if self.model is None:
            raise RuntimeError("STT model not loaded - call load() first")

        # Transcribe with faster-whisper, bias toward prompt vocabulary.
        # vad_filter trims non-speech/noise segments before transcribing,
        # which matters more with a distant mic picking up room noise.
        segments, info = self.model.transcribe(
            audio_data, beam_size=5, initial_prompt=initial_prompt, vad_filter=True)

        # Concatenate all segments into single string
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        result = "".join(text_parts).strip()
        return result
        # text = " ".join([segment.text for segment in segments])
        # return text.strip()

        return ""  # Stub
