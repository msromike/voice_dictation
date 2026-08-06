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
        if size < 1024:  # noqa: PLR2004 -- the base of the unit, not a threshold
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
    "key:f13" -> "F13", "x2" -> "Mouse Side (X2)"."""
    if val.startswith("key:"):
        return val[4:].replace('_', ' ').title()
    if val in ["left", "right", "middle"]:
        return f"Mouse {val.capitalize()}"
    if val in ["x1", "x2", "side"]:
        return f"Mouse Side ({val.upper()})"
    return val.title()


def _hotkey_line(hotkey_name, hotkey_failed):
    """The session block's Hotkey value, and whether it reads as a fault"""
    if hotkey_failed:
        return (f"{hotkey_name} is unavailable -- another application or "
                f"Windows already uses it. Pick a different one in Settings."), True
    if hotkey_name is None:
        return ("None set. Assign one in Settings to show this window "
                "from anywhere."), False
    return f"{hotkey_name} shows this window from anywhere.", False


def log_session_block(pid, config, hotkey_name, hotkey_failed):
    """The session block. Called only by start_vdict, so first launch and every
    engine restart print the identical thing and cannot drift apart."""
    ptt, stt = config.ptt, config.stt

    size = _model_size_on_disk(stt.model)
    model = stt.model if size is None else f"{stt.model} ({_human_size(size)})"
    hotkey_value, is_fault = _hotkey_line(hotkey_name, hotkey_failed)

    # The block owns its own blank line, so a restart is still separated
    # from the run above it with no startup header in between.
    log("block", "")
    for label, value, category in (
            ("Started", f"vdict_daemon.py (PID {pid})", "block"),
            ("Mode", "Hold button down to dictate." if ptt.mode == "hold"
                     else "Press button once to toggle dictation.", "block"),
            ("Trigger", format_bind(ptt.button), "block"),
            ("Hotkey", hotkey_value, "error" if is_fault else "block"),
            ("Compute", DEVICE_LABELS[stt.device], "block"),
            ("Model", model, "block")):
        log(category, _summary_line(label, value))
