"""Shared audio-file writes -- daemon and any future ambient pipeline both use this."""

from datetime import datetime
from pathlib import Path

import soundfile as sf


def write_timestamped_flac(directory, audio_data, samplerate):
    """Write audio to timestamped FLAC. Returns (path, timestamp_str).
    If audio_data is empty, returns (None, None)."""
    if len(audio_data) == 0:
        return None, None
        
    directory = Path(directory)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    
    # YYYY/MM/DD subfolders
    date_parts = timestamp.split("_")[0].split("-") # ['2026', '08', '09']
    year_dir = date_parts[0]
    month_dir = date_parts[1]
    day_dir = date_parts[2]
    
    full_dir = directory / year_dir / month_dir / day_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    
    path = full_dir / f"{timestamp}.flac"
    sf.write(path, audio_data, samplerate, format="FLAC", compression_level=1.0)
    return path, timestamp
