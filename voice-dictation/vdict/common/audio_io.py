"""Shared audio-file writes -- daemon and any future ambient pipeline both use this."""

from datetime import datetime
from pathlib import Path

import soundfile as sf


def write_timestamped_flac(directory, audio_data, samplerate):
    """Write audio_data to directory as a timestamped FLAC file. Returns the path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    path = directory / f"{timestamp}.flac"
    sf.write(path, audio_data, samplerate, format="FLAC", compression_level=1.0)
    return path
