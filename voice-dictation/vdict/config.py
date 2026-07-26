"""
Module: config.py
Purpose: Configuration management

Responsibilities:
  - Load config.json
  - Read vocabulary.txt and convert it to a recognizer hint string
  - Return merged configuration
"""

import json
from pathlib import Path

# User-editable word list. Kept at the repo root rather than beside the code
# so it is visible to someone who never opens the voice-dictation/ folder.
VOCABULARY_PATH = Path(__file__).parent.parent.parent / "vocabulary.txt"

# Daemon exit code the tray matches on to open Settings. Both sides must agree.
EXIT_NO_MICROPHONE = 2


def load_config():
    """
    Load configuration

    vdict_tray.py creates config.json from config.default.json before this
    process starts, so every key is expected to be present. A missing or
    malformed key raises rather than falling back to a value the user never
    chose -- a silent default is harder to diagnose than a loud failure.

    Returns:
        dict: Configuration, with stt['prompt'] resolved from vocabulary.txt
    """
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
    """
    Load recognizer hint terms from vocabulary.txt

    One term per line. Lines starting with '#' are comments and are skipped,
    which is what lets the shipped file document itself without those example
    words biasing the recognizer.

    Returns:
        str: Comma-separated term string ("" when the file has no live terms)
    """
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
