"""Loads config.json and vocabulary.txt. There are no key-level fallbacks."""

import json
from pathlib import Path

# User-editable word list. Kept at the repo root rather than beside the code
# so it is visible to someone who never opens the voice-dictation/ folder.
VOCABULARY_PATH = Path(__file__).parent.parent.parent / "vocabulary.txt"

# Daemon exit code the tray matches on to open Settings. Both sides must agree.
EXIT_NO_MICROPHONE = 2


def load_config():
    """Return config.json with stt['prompt'] resolved from vocabulary.txt.
    Every key is required. The tray seeds config.json before this process starts."""
    config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        raise RuntimeError(
            f"Config file not found: {config_path}. Launch via run.bat -- "
            f"the tray seeds config.json from config.default.json.")

    with open(config_path, 'r') as f:
        config = json.load(f)

    config['stt']['prompt'] = _load_vocabulary()

    return config


def _load_vocabulary():
    """Return vocabulary.txt as a comma-separated hint string, "" when it has no terms.
    One term per line. '#' lines are skipped, so the shipped file can document itself."""
    if not VOCABULARY_PATH.exists():
        raise RuntimeError(
            f"Vocabulary file not found: {VOCABULARY_PATH}. Restore it from "
            f"the repository -- to use no custom words, empty the file "
            f"rather than deleting it.")

    with open(VOCABULARY_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    terms = [line.strip() for line in lines
             if line.strip() and not line.lstrip().startswith('#')]
    return ", ".join(terms)
