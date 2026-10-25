"""Whisper transcription via faster-whisper. Defaults to CPU so the app runs without CUDA.
Model and device guidance for users is in README.md, "Which model and which device"."""

from faster_whisper import WhisperModel
import os
import glob
import threading
import numpy as np

from vdict.common.output import log

# Fix CUDA DLL resolution for Python 3.8+ on Windows (for ctranslate2)
import site

for sp in site.getsitepackages() + [site.getusersitepackages()]:
    nvidia_bins = glob.glob(os.path.join(sp, "nvidia", "*", "bin"))
    if nvidia_bins:
        os.environ["PATH"] = ";".join(nvidia_bins) + ";" + os.environ.get("PATH", "")
        break


class STTEngine:
    """Whisper transcription engine (via faster-whisper)"""

    def __init__(self, model_name="base.en", device="cpu"):
        """Configure the engine. Loads no weights until load() is called."""
        self.model_name = model_name
        self.device = device
        self.model = None
        self.compute_type = None

    def load(self):
        """Load Whisper model into memory (crash-fast on external boundary)"""
        try:
            # Probe for model.bin specifically. faster-whisper caches a partial
            # snapshot, which a whole-snapshot check reports as absent every launch.
            from huggingface_hub import try_to_load_from_cache
            repo_id = f"Systran/faster-whisper-{self.model_name}"
            if not isinstance(try_to_load_from_cache(repo_id, "model.bin"), str):
                log("download", f"Initiating download: {self.model_name}")

            # CPU requires float32. CUDA runs fastest on float16.
            self.compute_type = "float16" if self.device == "cuda" else "float32"
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type)
        except Exception as e:
            import sys
            log("model-fault",
                f"Failed to load Whisper model '{self.model_name}': {e}. "
                f"Pick a different model or switch to CPU in Settings, "
                f"then Save.")
            sys.exit(1)

    def wake_gpu(self):
        """
        Fire a dummy transcription on a background thread to force the GPU
        to spool up to P-State 0. Call this exactly when PTT is pressed.
        """
        if self.device != "cuda" or self.model is None:
            return

        model = self.model

        def _primer():
            try:
                # 0.1 seconds of absolute silence
                dummy = np.zeros(1600, dtype=np.float32)
                _ = list(
                    model.transcribe(
                        dummy,
                        beam_size=1,
                        vad_filter=False))
            except Exception:
                pass

        threading.Thread(target=_primer, daemon=True).start()

    def transcribe(self, audio_data, initial_prompt=""):
        """Transcribe 16kHz float32 samples, returning "" when no speech is detected.
        initial_prompt is a comma-separated hint, passed fresh on every call."""
        if self.model is None:
            raise RuntimeError("STT model not loaded - call load() first")

        # vad_filter trims room noise before transcribing. language="en" skips
        # large-v3's per-clip language guess, which costs its own encoder pass.
        segments, _ = self.model.transcribe(
            audio_data, beam_size=5, initial_prompt=initial_prompt, vad_filter=True,
            language="en")

        # Concatenate all segments into single string
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        return "".join(text_parts).strip()
