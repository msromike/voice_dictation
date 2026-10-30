"""PTT trigger monitoring and text injection at the cursor."""

import ctypes
import queue
import struct
import threading
import time
from datetime import datetime

import pyautogui
import pywintypes
import win32api
import win32clipboard
import win32con
import win32event
import win32gui
from pynput import mouse, keyboard

from vdict.common.output import log

# pyautogui waits 0.1s after every call it makes. The paste receipt arrives while
# we pump messages, so that wait would only delay the restore.
pyautogui.PAUSE = 0

# Private instances: the types declared here stay out of other modules' ctypes.windll.
# Undeclared, ctypes returns a 32-bit int and cuts a 64-bit handle in half.
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.restype = ctypes.c_void_p
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
GMEM_MOVEABLE = 0x0002

# Windows' clipboard-history monitor asks for the text the instant it is announced,
# which would fire the receipt before any paste. MEASURED: this flag stops it.
_EXCLUDE_FORMAT = win32clipboard.RegisterClipboardFormat(
    "ExcludeClipboardContentFromMonitorProcessing")

# GDI handles. GetClipboardData hands back a handle that cannot be set back, and
# MEASURED: Windows re-synthesizes CF_BITMAP from the restored CF_DIB anyway.
_SKIP_FORMATS = frozenset({2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E})

# Nothing asked for the text: no text field focused, or an elevated window that
# ignores synthetic keys. A backstop, not a tuning constant -- the receipt ends the wait.
_RECEIPT_TIMEOUT = 1.0

# Chrome reads the text, then re-checks the clipboard and drops the paste if it changed.
# 100 ms is the "feels instant" limit -- raise it only if Chrome drops a paste.
_RESTORE_GRACE = 0.1

# A budget, not a condition -- Windows has no event for the clipboard lock being
# released. WinForms Clipboard.SetDataObject's defaults: 10 tries, 100 ms apart.
CLIPBOARD_RETRIES = 10
CLIPBOARD_RETRY_DELAY = 0.1

# pynput key events carry no modifier state, and its Controller.modifiers holds
# only keys this app synthesised. Windows reports the physical state directly.
MODIFIER_VKS = (win32con.VK_SHIFT, win32con.VK_CONTROL, win32con.VK_MENU)

# config.json name -> pynput button. "side" is x2: browsers hook middle-click,
# not that. Left is absent on purpose -- it would record on every click.
BUTTON_MAP = {
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
    "side": mouse.Button.x2,
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
}


# Low-level hook values win32con does not define (pynput/mouse/_win32.py:159-160).
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

# Hook message -> (button name, pressed). X buttons say which one in mouseData.
_MOUSE_MESSAGES = {
    win32con.WM_RBUTTONDOWN: ("right", True),
    win32con.WM_RBUTTONUP: ("right", False),
    win32con.WM_MBUTTONDOWN: ("middle", True),
    win32con.WM_MBUTTONUP: ("middle", False),
    WM_XBUTTONDOWN: (None, True),
    WM_XBUTTONUP: (None, False),
}

# Swallowing a modifier would break every shortcut that uses it. Bound to PTT,
# these still trigger it but reach Windows too.
_MODIFIER_VKS = frozenset({0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C})


def _modifier_held():
    """True while Shift, Ctrl or Alt is physically down."""
    return any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in MODIFIER_VKS)


# Hook vk -> pyautogui name. The low-level hook reports left/right codes; the
# generic three are here in case a driver sends them.
_MODIFIER_NAMES = {
    0xA0: "shiftleft", 0xA1: "shiftright", 0xA2: "ctrlleft", 0xA3: "ctrlright",
    0xA4: "altleft", 0xA5: "altright", 0x5B: "winleft", 0x5C: "winright",
    0x10: "shift", 0x11: "ctrl", 0x12: "alt"}
_CTRL_VKS = frozenset({0xA2, 0xA3, 0x11})

# Modifiers under the user's fingers right now, from the hook's physical (not
# injected) events. GetAsyncKeyState can't say: it believes our own fake key-ups.
_physical_down = set()


def _track_modifier(msg, vk):
    """Hook thread. Keeps _physical_down honest; a set add or discard, nothing slower."""
    if msg in (win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN):
        _physical_down.add(vk)
    else:
        _physical_down.discard(vk)


def _send_ctrl_v():
    """Ctrl+V as the target sees it, whatever the fingers hold. A held Shift would make it
    Ctrl+Shift+V -- the hotkey itself, and 'paste as plain text' to browsers."""
    held = {vk: name for vk, name in _MODIFIER_NAMES.items() if vk in _physical_down}
    lifted = {vk: name for vk, name in held.items() if vk not in _CTRL_VKS}
    ctrl_held = len(held) > len(lifted)
    for name in lifted.values():
        pyautogui.keyUp(name)
    if not ctrl_held:
        pyautogui.keyDown("ctrl")
    pyautogui.press("v")
    if not ctrl_held:
        pyautogui.keyUp("ctrl")
    # Put back only what is still physically down, so a finger lifted meanwhile
    # does not leave its key stuck. What AutoHotkey's Send does around a hotkey.
    for vk, name in lifted.items():
        if vk in _physical_down:
            pyautogui.keyDown(name)


def _key_vk(bind):
    """config.json key binding -> the virtual-key code the low-level hook reports.
    "vk:166" is a key with no pynput name and no character of its own."""
    if bind.startswith("vk:"):
        return int(bind[len("vk:"):])
    name = bind[len("key:"):]
    key = getattr(keyboard.Key, name, None)
    if key is not None:
        return key.value.vk
    if len(name) == 1 and win32api.VkKeyScan(name) != -1:
        return win32api.VkKeyScan(name) & 0xFF
    raise ValueError(f"Unsupported PTT key: '{name}'")


def _mouse_name(name, what):
    """config.json mouse name -> the hook's name for it ("side" is x2)."""
    if name not in BUTTON_MAP:
        raise ValueError(f"Unsupported {what}: '{name}'. Supported: {list(BUTTON_MAP)}")
    return BUTTON_MAP[name].name


def _bind(name, what):
    """config.json binding -> (vk, mouse name). Exactly one is set."""
    if name.startswith(("key:", "vk:")):
        return _key_vk(name), None
    return None, _mouse_name(name, what)


class PTTListener:
    """Push-to-talk trigger listener (configurable mouse button or keyboard key)"""

    def __init__(self, button="middle", *, enter_button=None, on_enter, inbox, trace=None):
        """Swallow the PTT trigger and the optional Enter key or button. on_enter(hwnd)
        fires on every unmodified Enter; "press", "release" and "enter" go on inbox."""
        self.pressed = False
        # A held Enter key auto-repeats; only its first down is an Enter.
        self.enter_down = False
        self.on_enter = on_enter
        self.inbox = inbox
        # trace_ptt in dev-flags.toml: a queue that gets every raw PTT and Enter
        # event, injected ones too. None when the flag is off.
        self.trace = trace

        self.ptt_vk, self.ptt_mouse = _bind(button, "PTT button")
        self.enter_vk, self.enter_mouse = (
            (None, None) if enter_button is None else _bind(enter_button, "Enter button"))

        # Always on, whatever the PTT is -- Enter closes a dictation block.
        self.key_listener = keyboard.Listener(
            on_press=self._on_key_press, win32_event_filter=self._key_filter)
        self.mouse_listener = None
        if self.ptt_mouse or self.enter_mouse:
            self.mouse_listener = mouse.Listener(win32_event_filter=self._mouse_filter)

        self.key_listener.start()
        if self.mouse_listener is not None:
            self.mouse_listener.start()

    def _set_pressed(self, pressed):
        """PTT state change. Hook thread -- nothing slower than a queue put,
        or Windows drops the hook."""
        if pressed == self.pressed:
            return  # key auto-repeat
        self.pressed = pressed
        self.inbox.put("press" if pressed else "release")

    def _trace(self, source, down, data, scan):
        """Hook thread. One raw event onto the trace queue, read before the state
        changes, so a down while already down is marked as a repeat."""
        assert self.trace is not None
        held = self.pressed if source == "ptt" else self.enter_down
        self.trace.put((datetime.now().isoformat(), data.time, source,
                        "down" if down else "up", int(down and held), data.flags,
                        scan, data.dwExtraInfo))

    def _key_filter(self, msg, data):
        """Inside Windows' keyboard hook. Takes the PTT and Enter keys; every other key,
        and every key this app sends itself, passes through untouched."""
        down = msg in (win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN)
        source = ("ptt" if data.vkCode == self.ptt_vk
                  else "enter" if data.vkCode == self.enter_vk else None)
        if source and self.trace is not None:
            self._trace(source, down, data, data.scanCode)
        if data.flags & LLKHF_INJECTED:
            return True
        if data.vkCode in _MODIFIER_NAMES:
            _track_modifier(msg, data.vkCode)
        if source == "ptt":
            self._set_pressed(down)
        elif source == "enter":
            if down and not self.enter_down:
                self.inbox.put("enter")
            self.enter_down = down
        else:
            return True
        if data.vkCode not in _MODIFIER_VKS:
            # Raises; the hook returns 1 and no program sees the key (win32.py:306).
            self.key_listener.suppress_event()  # pyright: ignore[reportAttributeAccessIssue]
        return True

    def _mouse_filter(self, msg, data):
        """Inside Windows' mouse hook. Takes the PTT and Enter buttons, press and
        release both, so the program under the cursor never sees either."""
        if msg not in _MOUSE_MESSAGES:
            return True
        name, pressed = _MOUSE_MESSAGES[msg]
        if name is None:
            name = "x1" if data.mouseData >> 16 == 1 else "x2"
        source = ("ptt" if name == self.ptt_mouse
                  else "enter" if name == self.enter_mouse else None)
        if source and self.trace is not None:
            self._trace(source, pressed, data, None)
        if data.flags & LLMHF_INJECTED:
            return True
        if name == self.ptt_mouse:
            self._set_pressed(pressed)
        elif name == self.enter_mouse:
            if pressed:
                self.inbox.put("enter")
        else:
            return True
        self.mouse_listener.suppress_event()  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]

    def _on_key_press(self, key):
        """Internal callback for keyboard press events (runs in background thread)"""
        if key == keyboard.Key.enter and not _modifier_held():
            self.on_enter(win32gui.GetForegroundWindow())

    def stop(self):
        """Stop both listeners (cleanup)"""
        self.key_listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()


def _dropfiles(paths):
    """CF_HDROP reads back as a tuple of paths; writing it needs the struct rebuilt.
    20-byte header, then the paths UTF-16 and double-null terminated."""
    header = struct.pack("<Lllll", 20, 0, 0, 0, 1)
    return header + ("".join(p + "\0" for p in paths) + "\0").encode("utf-16-le")


def _payload(fmt, data):
    """GetClipboardData's return -> the bytes Windows stores. pywin32 decodes the
    text formats and drops their terminator; every other format comes back raw."""
    if fmt == win32con.CF_UNICODETEXT:
        return data.encode("utf-16-le", "surrogatepass") + b"\0\0"
    if fmt in (win32con.CF_TEXT, win32con.CF_OEMTEXT):
        return data + b"\0"
    if fmt == win32con.CF_HDROP:
        return _dropfiles(data)
    return data


def _set_global(fmt, blob):
    """SetClipboardData with our own copy of blob. pywin32's version reads digit-only
    data as a handle and the heap kills the process (crash dumps, 2026-10-26)."""
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, max(len(blob), 1))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        error = ctypes.WinError(ctypes.get_last_error())
        _kernel32.GlobalFree(handle)
        raise error
    ctypes.memmove(ptr, blob, len(blob))
    _kernel32.GlobalUnlock(handle)
    # Success hands the block to Windows, which frees it at the next EmptyClipboard.
    if not _user32.SetClipboardData(fmt, handle):
        error = ctypes.WinError(ctypes.get_last_error())
        _kernel32.GlobalFree(handle)
        raise error


class KeyboardInjector:
    """Text injection at the cursor via the clipboard, with the clipboard put back.
    Every clipboard call runs on this object's own thread; callers queue pastes."""

    def __init__(self):
        """Starts the clipboard thread and waits for its window to exist, so the
        first paste has somewhere for the receipt to go."""
        self._text = ""
        self._served = threading.Event()
        self._queue = queue.Queue()
        # Set after every put. The clipboard thread waits on it and on the window's
        # messages in one call, so the thread answers Windows while idle too.
        self._wake = win32event.CreateEvent(None, False, False, None)
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait()

    def _run(self):
        """The clipboard thread. The window is made here because WM_RENDERFORMAT goes
        to the thread that created it, and only while that thread pumps."""
        # The stubs declare both as read-only properties (_win32typing.pyi:2477,
        # :2479); assigning them is how pywin32 registers a window class.
        cls = win32gui.WNDCLASS()
        cls.lpszClassName = "VdictClipboardOwner"  # pyright: ignore[reportAttributeAccessIssue]
        cls.lpfnWndProc = self._wndproc  # pyright: ignore[reportAttributeAccessIssue]
        atom = win32gui.RegisterClass(cls)
        self._hwnd = win32gui.CreateWindow(atom, "vdict", 0, 0, 0, 0, 0, 0, 0, 0, None)
        self._ready.set()
        while True:
            # MEASURED: this window owns the restored clipboard, and an owner that is
            # not pumping stalls every other app's copy 5 s. So the idle wait pumps.
            win32event.MsgWaitForMultipleObjects(
                [self._wake], False, win32event.INFINITE, win32con.QS_ALLINPUT)
            win32gui.PumpWaitingMessages()
            self._drain()

    def _drain(self):
        """Every queued paste, in order. A done-signal, when there is one, is set
        after the clipboard is back."""
        while True:
            try:
                text, done = self._queue.get_nowait()
            except queue.Empty:
                return
            self._paste(text)
            if done is not None:
                done.set()

    def _submit(self, text, done):
        """Any thread. The put is what carries the paste; the event is what wakes."""
        self._queue.put((text, done))
        win32event.SetEvent(self._wake)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """WM_RENDERFORMAT is the paste receipt -- a target is asking for the text.
        Never opens the clipboard here: the asking app holds it open."""
        if msg == win32con.WM_RENDERFORMAT:
            win32clipboard.SetClipboardText(self._text, win32con.CF_UNICODETEXT)
            self._served.set()
            return 0
        if msg == win32con.WM_RENDERALLFORMATS:
            if _user32.OpenClipboard(hwnd):
                win32clipboard.SetClipboardText(self._text, win32con.CF_UNICODETEXT)
                _user32.CloseClipboard()
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _open_clipboard(self):
        """Another app can hold the clipboard open for a moment at a time."""
        for _ in range(CLIPBOARD_RETRIES):
            try:
                win32clipboard.OpenClipboard(self._hwnd)
                return True
            except pywintypes.error:
                time.sleep(CLIPBOARD_RETRY_DELAY)
        return False

    def _snapshot(self):
        """Every readable format, in the order Windows hands them back -- that order
        is what a target uses to pick one, so the restore keeps it."""
        if not self._open_clipboard():
            log("note", "Clipboard busy -- it was not saved this time.")
            return None
        items = []
        try:
            fmt = win32clipboard.EnumClipboardFormats(0)
            while fmt:
                if fmt not in _SKIP_FORMATS:
                    try:
                        data = win32clipboard.GetClipboardData(fmt)
                    except Exception:
                        data = None  # a format that will not read is one we cannot restore
                    # None is no memory behind it. Restoring it would promise the format,
                    # and _wndproc would answer that promise with dictation text.
                    if data is not None:
                        items.append((fmt, data))
                fmt = win32clipboard.EnumClipboardFormats(fmt)
        finally:
            win32clipboard.CloseClipboard()
        return items

    def _restore(self, items):
        """Writes the saved formats back in their original order."""
        if not self._open_clipboard():
            log("note", "Clipboard busy -- it was not restored this time.")
            return
        try:
            win32clipboard.EmptyClipboard()
            for fmt, data in items:
                try:
                    _set_global(fmt, _payload(fmt, data))
                except OSError as e:
                    log("note", f"Clipboard format {fmt} not restored: {e}")
        finally:
            win32clipboard.CloseClipboard()

    def _announce(self):
        """Claims the clipboard with a promise of text rather than the text itself.
        The target asking for it is what tells us the paste landed."""
        if not self._open_clipboard():
            return False
        try:
            win32clipboard.EmptyClipboard()
            _user32.SetClipboardData(win32con.CF_UNICODETEXT, None)
            _set_global(_EXCLUDE_FORMAT, b"\0\0\0\0")
        finally:
            win32clipboard.CloseClipboard()
        return True

    def _await_receipt(self):
        """Pumps until the target asks for the text, or the backstop runs out.
        QS_ALLINPUT covers sent messages, which is what WM_RENDERFORMAT is."""
        deadline = time.monotonic() + _RECEIPT_TIMEOUT
        while not self._served.is_set():
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return
            rc = win32event.MsgWaitForMultipleObjects(
                [], False, remaining_ms, win32con.QS_ALLINPUT)
            if rc == win32event.WAIT_OBJECT_0:
                win32gui.PumpWaitingMessages()

    def _pump_for(self, seconds):
        """Answers Windows for the given time. The clipboard owner must keep pumping
        while it waits, or every other app's copy stalls."""
        deadline = time.monotonic() + seconds
        while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
            rc = win32event.MsgWaitForMultipleObjects(
                [], False, remaining_ms, win32con.QS_ALLINPUT)
            if rc == win32event.WAIT_OBJECT_0:
                win32gui.PumpWaitingMessages()

    def _paste(self, text):
        """Clipboard thread. Pastes text at the cursor, then restores the clipboard
        a grace after the target takes it -- or after the backstop, if nothing asks."""
        items = self._snapshot()
        self._text = text + " "
        self._served.clear()
        if not self._announce():
            log("note", "Clipboard busy -- nothing pasted. The text is in this window.")
            return

        _send_ctrl_v()
        self._await_receipt()
        if self._served.is_set():
            self._pump_for(_RESTORE_GRACE)

        if items is not None:
            self._restore(items)

    def inject(self, text):
        """Any thread. Pastes text at the cursor and returns once the clipboard is
        back, so what follows -- a corpus row, a deferred Enter -- comes after it."""
        if not text or not text.strip():
            return
        done = threading.Event()
        self._submit(text, done)
        done.wait()

    def paste_async(self, text):
        """Any thread. Pastes text and returns at once -- the paste-last hotkey,
        which must land even while a recording holds the main thread."""
        self._submit(text, None)

    def press_enter(self):
        """A real Enter keystroke, for the Enter key or button."""
        pyautogui.press("enter")
