"""The vdict_daemon.py subprocess: start, stop, restart, its stdout reader and
its exit poll. No Tk here -- app owns the tick that calls poll()."""

import os
import subprocess
import sys
import threading
import traceback
from collections.abc import Callable
from pathlib import Path

import win32event

from vdict.common import output
from vdict.common.config import RELOAD_EVENT_NAME
from vdict.tray.log import error_log, log

# THREE .parent steps from vdict/tray/ to reach voice-dictation/, where
# vdict_daemon.py lives. Two lands in vdict/ and Popen raises.
_DAEMON_DIR = Path(__file__).parent.parent.parent
_DAEMON_PATH = _DAEMON_DIR / "vdict_daemon.py"

# Declared, deliberately unbound -- reaching either before install() is a bug.
_set_loading: Callable[[bool], None]
_drain: Callable[[], None]

_process = None
_reader_thread = None
_exit_reported = False
_fault_shown = False


def install(set_loading, drain):
    """Hand in the two console edges. The subprocess never reaches the console
    itself -- that is the edge that closed the measured import cycle."""
    global _set_loading, _drain
    _set_loading, _drain = set_loading, drain


def set_fault_shown(shown):
    """faults.py sets this through app. A fault already told the user what
    happened, so the exit poll stays quiet rather than reporting it twice."""
    global _fault_shown
    _fault_shown = shown


def _read_output(stdout):
    """Read subprocess output and queue it"""
    for line in stdout:
        log(*output.parse(line.rstrip()))


def start(on_started):
    """Start vdict_daemon.py and capture its output.
    on_started(pid) runs once it is up -- app prints the session block there."""
    global _process, _reader_thread, _exit_reported, _fault_shown

    # Set here, not inside the daemon: these are read at import time, and an
    # import inside the daemon can always beat code that runs after it.
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"          # immediate capture, no buffering
    env["PYTHONIOENCODING"] = "utf-8"      # transcripts carry curly quotes/em-dashes
    env["HF_HUB_VERBOSITY"] = "error"      # no third-party chatter in our window
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"

    # Clear the previous run's exit report, or a daemon that dies again
    # after a Save would fail silently.
    _exit_reported = False
    _fault_shown = False

    _process = subprocess.Popen(
        [sys.executable, str(_DAEMON_PATH)],
        cwd=_DAEMON_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env=env
    )
    # Into the console, not stdout, which pythonw discards. The banner is
    # NOT here: it greets once from run(), never again on a restart.
    on_started(_process.pid)

    _set_loading(False)

    # Start thread to read output
    _reader_thread = threading.Thread(
        target=_read_output, args=(_process.stdout,), daemon=True)
    _reader_thread.start()


def stop():
    """Terminate the daemon, escalating to kill if it will not exit.
    The single definition of how the daemon dies. Shutdown and restart both use it."""
    if _process is None:
        return
    _process.terminate()
    try:
        _process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _process.kill()
        _process.wait()


def restart(on_started):
    """Swap the running daemon for a fresh one.
    Internal only -- there is no user-facing restart command."""
    stop()
    start(on_started)


def reload(on_started):
    """Have the running daemon re-read config.json, model kept loaded. A daemon
    that has exited -- a mic fault, say -- is started instead."""
    if _process is None or _process.poll() is not None:
        start(on_started)
        return
    signal_reload()
    on_started(None)  # nothing started -- the block says Updated
    # No startup follows to close the block, so the line that would comes from here.
    log("block", output.divider_line())
    log("block", "")


def signal_reload():
    """The running daemon re-reads config.json between captures. Nothing printed."""
    win32event.SetEvent(win32event.CreateEvent(
        None, False, False, RELOAD_EVENT_NAME))  # pyright: ignore[reportArgumentType]


def preview_beep(tone_type, volume):
    """Ask the running daemon to play one beep, through its own stream and device.
    A daemon that is down plays nothing -- there is no other sound path to fall back on."""
    if _process is None or _process.poll() is not None:
        return
    try:
        _process.stdin.write(f"{tone_type} {volume}\n")  # pyright: ignore[reportOptionalMemberAccess]
        _process.stdin.flush()  # pyright: ignore[reportOptionalMemberAccess]
    except OSError:
        pass  # exited between the poll and the write; poll() reports it


def poll():
    """Report the daemon's exit once, if it has exited. Called on app's tick."""
    global _exit_reported
    try:
        if _process and not _exit_reported:
            exit_code = _process.poll()
            if exit_code is not None:
                _exit_reported = True
                if _reader_thread is not None:
                    _reader_thread.join(timeout=0.5)
                # Drain again after the join so the daemon's last lines land
                # above the exit line rather than after it.
                _drain()
                if not _fault_shown:
                    log("error", f"vdict_daemon.py exited with code {exit_code}")
    except Exception:
        error_log("Exit-check error", traceback.format_exc())
