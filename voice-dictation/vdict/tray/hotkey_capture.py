"""Capturing and naming one output-window hotkey combination.
Leaf -- imports only hotkey.py, itself a leaf."""

import ctypes
from tkinter import messagebox

import win32con

from vdict.tray import hotkey

# Tk event.state bits, measured on Windows. Alt is bit 17, NOT the X11 Mod1
# 0x0008 you would guess from Ctrl landing on its X11 value.
TK_SHIFT, TK_CTRL, TK_ALT = 0x0001, 0x0004, 0x20000

# Held modifiers auto-repeat, so these can never be taken as the captured key.
MODIFIER_KEYSYMS = frozenset((
    "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Win_L", "Win_R", "Super_L", "Super_R"))

VK_F1, VK_F24 = 0x70, 0x87

# Windows names these as their numpad twins unless lParam bit 24 is set.
EXTENDED_VKS = frozenset((0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                          0x2D, 0x2E, 0x90, 0xA3, 0xA5))

# Pause has no scan code through MAPVK_VK_TO_VSC; its real one is the
# multi-byte E1 1D 45 sequence, so Windows cannot name it.
VK_NAMES = {0x13: "Pause"}


def _windows_key_name(vk):
    """The keycap label Windows gives this key on the layout in use.
    Empty for keys no keycap carries. Windows holds every layout, so no table can."""
    user32 = ctypes.windll.user32
    lparam = (user32.MapVirtualKeyW(vk, 0) & 0xFF) << 16
    if vk in EXTENDED_VKS:
        lparam |= 1 << 24
    buf = ctypes.create_unicode_buffer(64)
    return buf.value if user32.GetKeyNameTextW(lparam, buf, 64) else ""


def _vk_name(vk):
    """Display name for a virtual-key code, asked of Windows rather than tabulated.
    F-keys are derived -- a scan code exists but no layout carries a keycap for them."""
    if VK_F1 <= vk <= VK_F24:
        return f"F{vk - VK_F1 + 1}"
    return _windows_key_name(vk) or VK_NAMES.get(vk, f"0x{vk:02X}")


def _combo_name(mods, vk):
    """Render a modifier mask and virtual key as "Ctrl+Alt+Shift+K" """
    parts = [name for bit, name in ((win32con.MOD_CONTROL, "Ctrl"),
                                    (win32con.MOD_ALT, "Alt"),
                                    (win32con.MOD_SHIFT, "Shift")) if mods & bit]
    parts.append(_vk_name(vk))
    return "+".join(parts)


def _state_to_mods(state):
    """Tk event.state -> the fsModifiers mask RegisterHotKey expects"""
    mods = 0
    for bit, mod in ((TK_CTRL, win32con.MOD_CONTROL),
                     (TK_ALT, win32con.MOD_ALT),
                     (TK_SHIFT, win32con.MOD_SHIFT)):
        if state & bit:
            mods |= mod
    return mods


def _confirm_bare_key(parent, name):
    """Warn before binding a key with no modifier.
    Nobody should end up here without knowing what they gave up."""
    return messagebox.askokcancel(
        "No modifier key -- Alt, Ctrl or Shift",
        f"You are binding {name} on its own.\n\n"
        f"Pressing {name} anywhere in Windows will raise this window. "
        f"Whatever {name} normally does, it stops doing.\n\n"
        f"Bind {name} anyway?",
        # The buttons cannot be relabelled, so the verb lives in the question
        # and Cancel takes the default, making Enter the safe answer.
        default=messagebox.CANCEL,
        icon=messagebox.WARNING,
        parent=parent)


def capture(btn, display, binding):
    """Take one combination from the picker button itself.
    Binding on the button, not the dialog, is what lets Escape mean two things."""
    previous, previous_text = dict(binding), display.get()
    display.set("Press a combination...")
    btn.focus_set()

    # A live hotkey is swallowed by Windows before Tk sees it, so the
    # combination in use could never be rebound. _rebind_on_close puts it back.
    hotkey.unregister()

    def restore():
        """Every abandoned capture puts the old binding back on the face"""
        binding.update(previous)
        display.set(previous_text)

    def on_key(event):
        # Modifiers auto-repeat while held, so they can never end a capture.
        if event.keysym in MODIFIER_KEYSYMS:
            return "break"

        # Unbind BEFORE anything that runs a nested event loop. The warning
        # below is modal, and a live binding could re-enter this handler.
        btn.unbind("<KeyPress>")

        # "break" keeps this Escape off settings_win, whose own binding
        # closes the dialog. That is the second Escape.
        if event.keysym == "Escape":
            restore()
            return "break"

        # keycode and state are read out before the modal opens, so the
        # accept path needs no binding once the dialog returns.
        mods = _state_to_mods(event.state)
        name = _combo_name(mods, event.keycode)
        # The dialog the button lives in, rather than threaded-in state.
        if mods == 0 and not _confirm_bare_key(btn.winfo_toplevel(), name):
            restore()
            return "break"

        binding.update(modifiers=mods, vk=event.keycode, name=name)
        display.set(name)
        return "break"

    # "break" also stops Tab, Return and space reaching the dialog's widgets.
    btn.bind("<KeyPress>", on_key)
