"""Loads config.json and vocabulary.txt. The daemon's load_config raises on any
problem; the tray's load_settings heals per field instead."""

import json
import shutil
from pathlib import Path
from typing import Literal, cast

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
    # Reached by NAME, not by attribute, from vdict/tray/geometry.py's registry.
    # Renaming either one silently stops that window persisting its geometry.
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
            f"Config file not found: {CONFIG_PATH}. Launch via vdict_run.bat -- "
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


# Single source, so the boot-time seed and the File > Vocabulary seed
# can never drift into two different wordings.
VOCABULARY_RESET_MESSAGE = "vocabulary.txt not found -- restored from template."


def reseed_vocabulary_if_missing():
    """Restore vocabulary.txt from the template if it is absent.
    Returns whether a reseed happened -- callers decide when to log it."""
    if VOCABULARY_PATH.exists():
        return False
    shutil.copyfile(VOCABULARY_TEMPLATE_PATH, VOCABULARY_PATH)
    return True


def _summarize_config_error(exc):
    """A short, human-readable reason for a config problem -- not pydantic's
    full dump, when that's what raised."""
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        return f"{loc}: {first['msg']}" if loc else first["msg"]
    return str(exc)


def _delete_at_path(d, loc):
    """Delete the value at the deepest reachable point along a pydantic
    error's loc -- a wrong-type section resets there, not deeper."""
    node = d
    for depth, key in enumerate(loc):
        if not isinstance(node, dict) or key not in node:
            return
        if depth == len(loc) - 1 or not isinstance(node[key], dict):
            del node[key]
            return
        node = node[key]


def _wholesale_reset_message(exc):
    """Complete, display-ready line for a full reset -- everything changed
    here, not just one field, so name the whole file, not individual ones."""
    detail = _summarize_config_error(exc)
    return (f"config.json could not be read ({detail}) -- "
            "default settings have been restored.")


# loc -> a name worth telling the user about, one per line, never grouped.
# Absent means app-managed state (position/size/font/first-run) -- silent.
FIELD_LABELS: dict[tuple[str, ...], str] = {
    ("audio", "device"): "Microphone",
    ("audio", "feedback"): "Audio beeps",
    ("ptt", "button"): "Push-to-talk button",
    ("ptt", "mode"): "Push-to-talk mode",
    ("stt", "model"): "Whisper model",
    ("stt", "device"): "Compute device",
    ("hotkey", "modifiers"): "Output window hotkey",
    ("hotkey", "vk"): "Output window hotkey",
    ("hotkey", "name"): "Output window hotkey",
    ("ui", "open_console_on_boot"): "Show output on startup",
}


def _format_value(config, loc):
    """The value at loc, read off the healed Config, for display.
    "" -> System Default, None -> Not set; everything else uppercased."""
    node = config
    for key in loc:
        node = getattr(node, key)
    if node == "":
        return "SYSTEM DEFAULT"
    if node is None:
        return "NOT SET"
    return str(node).upper()


def load_settings():
    """Read config.json, seeding from the Config model's own defaults. A bad
    field resets to its own default and is named; unparseable JSON resets all."""
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w") as f:
            f.write(Config().model_dump_json(indent=2))
        return Config(), None

    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        with open(CONFIG_PATH, "w") as f:
            f.write(Config().model_dump_json(indent=2))
        return Config(), [_wholesale_reset_message(exc)]

    try:
        return Config.model_validate(raw), None
    except ValidationError as exc:
        healed = []
        for error in exc.errors():
            _delete_at_path(raw, error["loc"])
            # This schema has no list fields, so loc is always all-str --
            # narrower than pydantic's own general tuple[int | str, ...].
            loc = cast(tuple[str, ...], error["loc"])
            label = FIELD_LABELS.get(loc)
            if label and label not in [h[0] for h in healed]:
                healed.append((label, loc))

        try:
            config = Config.model_validate(raw)
        except ValidationError as exc2:
            with open(CONFIG_PATH, "w") as f:
                f.write(Config().model_dump_json(indent=2))
            return Config(), [_wholesale_reset_message(exc2)]

        with open(CONFIG_PATH, "w") as f:
            f.write(config.model_dump_json(indent=2))
        lines = [f"{label} - {_format_value(config, loc)}" for label, loc in healed]
        return config, lines


def save_settings(config):
    """Write config.json back to disk"""
    with open(CONFIG_PATH, "w") as f:
        f.write(Config.model_validate(config).model_dump_json(indent=2))
