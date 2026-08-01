"""Loads config.json and vocabulary.txt. There are no key-level fallbacks."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

# User-editable word list, seeded from the tracked template when absent.
VOCABULARY_PATH = Path(__file__).parent.parent.parent.parent / "userdata" / "vocabulary.txt"
VOCABULARY_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent.parent / "templates" / "vocabulary.txt")

# Single source for both processes -- the tray writes this path, the daemon reads it.
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "userdata" / "config.json"


class Pos(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    x: int
    y: int


class AudioConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    device: str = ""
    feedback: bool = True


class PttConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    button: str = "middle"
    mode: Literal["hold", "toggle"] = "hold"


class KeyboardConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    preserve_clipboard: bool = True


class SttConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    model: str = "base.en"
    device: Literal["cpu", "cuda"] = "cpu"


class HotkeyConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    modifiers: int | None = None
    vk: int | None = None
    name: str | None = None


class UiConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    open_console_on_boot: bool = True
    first_run: bool = True
    settings_pos: Pos | None = None
    console_geometry: str | None = None
    console_font_size: int = 12


class Config(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    audio: AudioConfig = AudioConfig()
    ptt: PttConfig = PttConfig()
    keyboard: KeyboardConfig = KeyboardConfig()
    stt: SttConfig = SttConfig()
    hotkey: HotkeyConfig = HotkeyConfig()
    ui: UiConfig = UiConfig()


def read_config():
    """Read and validate config.json against the Config model. Raises
    FileNotFoundError or ValidationError (which also covers malformed JSON)."""
    return Config.model_validate_json(CONFIG_PATH.read_text())


def load_config():
    """Return config.json as a Config instance.
    The tray seeds config.json before this process starts."""
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"Config file not found: {CONFIG_PATH}. Launch via run.bat -- "
            f"the tray seeds config.json from the Config model's defaults.")

    try:
        return read_config()
    except ValidationError as exc:
        raise RuntimeError(
            f"config.json is invalid: {exc}. Fix the file, or delete it "
            f"and relaunch to reseed it from its own defaults.") from exc


def load_vocabulary():
    """Return vocabulary.txt as a comma-separated hint string, "" when it has no terms.
    One term per line. '#' lines are skipped, so the shipped file can document itself."""
    if not VOCABULARY_PATH.exists():
        raise RuntimeError(
            f"Vocabulary file not found: {VOCABULARY_PATH}. Relaunch to "
            f"reseed it from {VOCABULARY_TEMPLATE_PATH} -- to use no custom "
            f"words, empty the file rather than deleting it.")

    with open(VOCABULARY_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    terms = [line.strip() for line in lines
             if line.strip() and not line.lstrip().startswith('#')]
    return ", ".join(terms)
