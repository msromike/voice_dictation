"""The session block, printed once per daemon start. Leaf -- Settings needs
_format_bind and DEVICE_LABELS too, and a leaf is the only tier both import."""

import glob
import os

from vdict.tray.log import log

# config.json stt.device -> display name. Settings and the session block share it.
DEVICE_LABELS = {"cpu": "CPU", "cuda": "GPU (CUDA)"}


# The session block is label/value, no tags. Scrolling lines below it
# keep [TAG] instead -- greppable, and they split into columns in a spreadsheet.
def _summary_line(label, value):
    """One aligned label/value line of the session block. Consolas makes the padding line up."""
    return f"{label + ':':<10}{value}"


def _human_size(size):
    """Format a byte count the way Explorer does -- binary steps, decimal labels"""
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _model_size_on_disk(model_name):
    """Bytes the cached model occupies, or None when it has not been downloaded.
    Skips symlinks: HuggingFace either hardcopies snapshots or links them to blobs, never both."""
    cache = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface"), "hub")
    found = glob.glob(os.path.join(cache, f"models--*whisper-{model_name}"))
    if not found:
        return None

    total = 0
    for root, _dirs, files in os.walk(found[0]):
        for name in files:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                total += os.path.getsize(path)
    return total


def format_bind(val):
    """Turn a config.json ptt.button value into a display name.
    "key:f13" -> "F13", "x2" -> "Mouse Side (X2)", "" -> "Not set"."""
    if not val:
        return "Not set"
    if val.startswith("key:"):
        return val[4:].replace('_', ' ').title()
    if val in ["left", "right", "middle"]:
        return f"Mouse {val.capitalize()}"
    if val in ["x1", "x2", "side"]:
        return f"Mouse Side ({val.upper()})"
    return val.title()


def _hotkey_line(hotkey_name, hotkey_failed, does, purpose):
    """A session-block hotkey value, and whether it reads as a fault. does and purpose
    are the same action two ways: "shows this window", "show this window"."""
    if hotkey_failed:
        return (f"{hotkey_name} is unavailable -- another application or "
                f"Windows already uses it. Pick a different one in Settings."), True
    if hotkey_name is None:
        return f"None set. Assign one in Settings to {purpose}.", False
    return f"{hotkey_name} {does}.", False


def log_session_block(pid, config, hotkeys):
    """The session block, after every start and every Save. pid is None when a Save
    reloaded the running engine, so its first line says Updated, not Started."""
    ptt, stt = config.ptt, config.stt
    first = (("Started", f"vdict_daemon.py (PID {pid})") if pid is not None
             else ("Updated", "settings applied, model kept loaded."))

    size = _model_size_on_disk(stt.model)
    model = stt.model if size is None else f"{stt.model} ({_human_size(size)})"
    (window_name, window_taken), (paste_name, paste_taken) = (
        hotkeys["window"], hotkeys["paste"])
    window_value, window_fault = _hotkey_line(
        window_name, window_taken, "shows this window from anywhere",
        "show this window from anywhere")
    paste_value, paste_fault = _hotkey_line(
        paste_name, paste_taken, "pastes your last dictation where you are typing",
        "paste your last dictation where you are typing")

    # The block owns its own blank line, so a restart is still separated
    # from the run above it with no startup header in between.
    log("block", "")
    for label, value, category in (
            (*first, "block"),
            ("Mode", "Hold button down to dictate." if ptt.mode == "hold"
                     else "Press button once to toggle dictation.", "block"),
            ("Trigger", format_bind(ptt.button), "block"),
            ("Enter", format_bind(ptt.enter_button or ""), "block"),
            ("Hotkey", window_value, "error" if window_fault else "block"),
            ("Paste", paste_value, "error" if paste_fault else "block"),
            ("Compute", DEVICE_LABELS[stt.device], "block"),
            ("Model", model, "block")):
        log(category, _summary_line(label, value))
