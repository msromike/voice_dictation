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
    Load configuration with profile support
    
    Args:
        profile_name: Profile to use (None = use default_profile from config)
        
    Returns:
        dict: Merged configuration with profile settings in 'stt' key
    """
    config_path = Path(__file__).parent.parent / "config.json"
    
    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Determine which profile to use
    if profile_name is None:
        profile_name = config.get('default_profile', 'general')
    
    # Get profile settings
    profiles = config.get('profiles', {})
    if profile_name not in profiles:
        raise RuntimeError(f"Profile '{profile_name}' not found in config")
    
    profile = profiles[profile_name]
    
    # Load prompt from file or inline
    prompt = ""
    if 'prompt_file' in profile:
        prompt = _load_prompt_file(profile['prompt_file'])
    elif 'prompt' in profile:
        prompt = profile['prompt']
    
    # Build STT config from profile
    stt_config = {
        'model': profile.get('model', 'base.en'),
        'device': profile.get('device', 'cpu'),
        'prompt': prompt
    }
    
    # Merge into config (backward compat with old 'stt' key)
    config['stt'] = stt_config
    
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
