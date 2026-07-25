"""
Module: config.py
Purpose: Configuration management with profile support

Responsibilities:
  - Load config.json
  - Select profile (default or specified)
  - Read prompt files and convert to prompt strings
  - Return merged configuration
"""

import json
from pathlib import Path


def load_config(profile_name=None):
    """
    Load configuration

    Returns:
        dict: Merged configuration with stt settings
    """
    config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Ensure stt key exists
    stt = config.setdefault('stt', {})

    # Load prompt from file or inline
    prompt = ""
    if 'prompt_file' in stt:
        prompt = _load_prompt_file(stt['prompt_file'])
    elif 'prompt' in stt:
        prompt = stt['prompt']

    stt['model'] = stt.get('model', 'small.en')
    stt['device'] = stt.get('device', 'cpu')
    stt['prompt'] = prompt

    return config


def _load_prompt_file(prompt_file_path):
    """
    Load prompt terms from text file (one term per line)

    Args:
        prompt_file_path: Relative path from voice-dictation/ folder

    Returns:
        str: Comma-separated prompt string
    """
    prompt_path = Path(__file__).parent.parent / prompt_file_path

    if not prompt_path.exists():
        # Silently return empty if prompt file missing (non-critical)
        return ""

    with open(prompt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Strip whitespace, filter empty lines, join with commas
    terms = [line.strip() for line in lines if line.strip()]
    return ", ".join(terms)
