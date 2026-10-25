"""System-wide hotkey registration. RegisterHotKey only, never a keyboard hook.
A hook never satisfies "received the last input event", so SetForegroundWindow then fails."""

import threading

import win32api
import win32con
import win32gui

# RegisterHotKey ids must fall in 0x0000-0xBFFF. One id per hotkey.
OUTPUT_WINDOW = 1
PASTE_LAST = 2

_CMD_REGISTER = win32con.WM_APP + 1
_CMD_UNREGISTER = win32con.WM_APP + 2

_lock = threading.Lock()
_queue_ready = threading.Event()
_replied = threading.Event()

_thread = None
_thread_id = None
_callbacks = {}
_registered = set()
_result = False


def register(hotkey_id, mods, vk, callback):
    """Claim a system-wide hotkey, returning True on success and False when it is taken.
    Callable from any thread. callback runs on the owning thread, not the caller's."""
    with _lock:
        _start()
        _callbacks[hotkey_id] = callback
        # A thread message carries two numbers, so the id rides above the modifiers.
        return _command(_CMD_REGISTER,
                        (hotkey_id << 16) | mods | win32con.MOD_NOREPEAT, vk)


def unregister_all():
    """Release every hotkey held. Does nothing when none is."""
    with _lock:
        if _thread is None:
            return
        _command(_CMD_UNREGISTER, 0, 0)


def _start():
    """Launch the owning thread on first use and wait for its message queue to exist."""
    global _thread
    if _thread is not None:
        return
    _thread = threading.Thread(target=_pump, daemon=True)
    _thread.start()
    _queue_ready.wait()


def _command(cmd, wparam, lparam):
    """Hand a command to the owning thread and block until it writes the result.
    PostThreadMessage returns once the message is queued, not once it is handled."""
    _replied.clear()
    win32api.PostThreadMessage(_thread_id, cmd, wparam, lparam)
    _replied.wait()
    return _result


def _pump():
    """Register, unregister and receive WM_HOTKEY, all on this one thread.
    Windows only lets the thread that registered a hotkey release it."""
    global _thread_id, _result
    _thread_id = win32api.GetCurrentThreadId()

    # PostThreadMessage fails against a thread that has not created a queue yet.
    # NULL hwnd means this thread's own queue; the stub types the parameter int.
    win32gui.PeekMessage(None, 0, 0, win32con.PM_NOREMOVE)  # pyright: ignore[reportArgumentType]
    _queue_ready.set()

    # Not PumpMessages: it dispatches to a window procedure, and a thread
    # message has no window, so WM_HOTKEY would be swallowed.
    while True:
        msg = win32gui.GetMessage(None, 0, 0)[1]  # pyright: ignore[reportArgumentType]
        if msg[1] == win32con.WM_HOTKEY:
            _callbacks[msg[2]]()  # WM_HOTKEY's wParam is the id
        elif msg[1] == _CMD_REGISTER:
            _result = _claim(msg[2] >> 16, msg[2] & 0xFFFF, msg[3])
            _replied.set()
        elif msg[1] == _CMD_UNREGISTER:
            _release_all()
            _result = True
            _replied.set()


def _claim(hotkey_id, mods, vk):
    """Owning thread only. False when Windows or another process already holds the combination.
    Callers release first; claiming over a live registration collides on the id and fails."""
    try:
        win32gui.RegisterHotKey(None, hotkey_id, mods, vk)
    except win32gui.error:
        return False
    _registered.add(hotkey_id)
    return True


def _release_all():
    """Owning thread only. UnregisterHotKey raises for an id not registered."""
    for hotkey_id in _registered:
        win32gui.UnregisterHotKey(None, hotkey_id)
    _registered.clear()
