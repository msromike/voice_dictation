#!/usr/bin/env python3
"""Voice Dictation - System Tray Wrapper (Chunk 2b: Capture and display output)"""
import sys

# Must precede the imports below -- win32event raises ImportError elsewhere.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

__version__ = "1.0.0"

import subprocess
import threading
import traceback
import queue
import shutil
import os
import glob
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from datetime import datetime
import webbrowser
import re
from pathlib import Path
from typing import cast, Literal
from PIL.IcoImagePlugin import IcoImageFile
import pystray
import win32event
import win32api
import win32con
import win32gui
import ctypes
from pydantic import ValidationError

from vdict.config import (
    Config, CONFIG_PATH, HotkeyConfig, Pos, VOCABULARY_PATH, VOCABULARY_TEMPLATE_PATH,
    EXIT_NO_MICROPHONE)
from vdict import hotkey

try:
    # Tell Windows this app handles its own DPI scaling to fix Tkinter blur
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# Win32 GetLastError value returned when the single-instance mutex exists.
ERROR_ALREADY_EXISTS = 183

# GetSystemMetrics index for the tray/small-icon edge length.
SM_CXSMICON = 49

# Shared by the tray, the Desktop shortcut and the Startup shortcut.
ICON_PATH = Path(__file__).parent.parent / "images" / "vdict.ico"

# Created at import so the log is writable before anything can fail.
LOG_DIR = Path(__file__).parent.parent / "userdata" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_PATH = LOG_DIR / "tray_error.log"

# Single source for the project URL -- it appears in the console banner, the
# About box, and the Help menu.
PROJECT_URL = "https://github.com/msromike/voice_dictation"

# Console text size, in points. Tk scales points by screen DPI on its own, so
# these are not multiplied by dpi_scale anywhere.
CONSOLE_FONT_DEFAULT = 12
CONSOLE_FONT_MIN = 7
CONSOLE_FONT_MAX = 32

# Single source, so the boot-time seed and the File > Vocabulary seed
# can never drift into two different wordings.
VOCABULARY_RESET_MESSAGE = (
    "[VOCABULARY RESET] vocabulary.txt not found -- restored from template.")


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


def _log_error(context, exc):
    """Append a caught exception to the error log.
    For errors raised inside the console handler, where reporting to it would loop."""
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("%s: %s: %s\n" % (context, type(exc).__name__, exc))
        traceback.print_exc(file=f)


def _geometry_origin(geometry):
    """Pull (x, y) out of a Tk geometry string such as "900x600+120+80".
    Returns None before a window is placed, when Tk emits no origin."""
    match = re.search(r'([+-]\d+)([+-]\d+)$', geometry)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


# config.json stt.device -> display name. Settings and the session block share it.
DEVICE_LABELS = {"cpu": "CPU", "cuda": "GPU (CUDA)"}

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


def _dim(text):
    """Wrap a line in the ANSI dim code the output window maps to gray"""
    return f"\033[90m{text}\033[0m"


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


def _format_bind(val):
    """Turn a config.json ptt.button value into a display name.
    "key:f13" -> "F13", "x2" -> "Mouse Side (X2)"."""
    if val.startswith("key:"):
        return val[4:].replace('_', ' ').title()
    if val in ["left", "right", "middle"]:
        return f"Mouse {val.capitalize()}"
    if val in ["x1", "x2", "side"]:
        return f"Mouse Side ({val.upper()})"
    return val.title()


def _is_on_screen(x, y):
    """True when (x, y) lands on the desktop spanning every attached monitor.
    The 100/60 margin keeps the title bar grabbable rather than flush to an edge."""
    metric = ctypes.windll.user32.GetSystemMetrics
    virtual_x, virtual_y = metric(76), metric(77)
    virtual_w, virtual_h = metric(78), metric(79)
    return (virtual_x <= x <= virtual_x + virtual_w - 100
            and virtual_y <= y <= virtual_y + virtual_h - 60)


class _PTTCapture:
    """One push-to-talk rebind. Every exit routes through end(), the only place
    the button is re-enabled and the global hooks are dropped."""

    def __init__(self, tray, btn_var, disp_var, tk_btn):
        """Hold the widgets the capture writes back into, and the face to restore"""
        self.tray = tray
        self.btn_var = btn_var
        self.disp_var = disp_var
        self.tk_btn = tk_btn
        self.previous = disp_var.get()
        self.listeners = []
        self.done = False

    def start(self):
        """Disable the button and listen for one key or mouse press.
        pynput is imported here so the tray's own startup never loads it."""
        from pynput import keyboard, mouse

        self.disp_var.set("Press any key...")
        self.tk_btn.config(state="disabled")
        self.listeners = [keyboard.Listener(on_press=self._on_key),
                          mouse.Listener(on_click=self._on_click)]
        # Closing Settings mid-capture would leave both global hooks running
        # with no window behind them.
        self.tk_btn.bind("<Destroy>", self._unhook, add="+")
        for listener in self.listeners:
            listener.start()

    def _unhook(self, _event=None):
        """Drop both global hooks and mark the capture over. Also the <Destroy>
        handler, so a widget Tk has already torn down ends the capture too."""
        self.done = True
        for listener in self.listeners:
            listener.stop()

    def end(self, display):
        """The only way a capture ends. Restores the face, re-enables, unhooks."""
        if self.done:
            return
        self.disp_var.set(display)
        self.tk_btn.config(state="normal")
        self._unhook()

    def accept(self, val, disp):
        """Write the binding back and close the capture"""
        if self.done:
            return
        self.btn_var.set(val)
        self.end(disp)

    def reject(self, title, body):
        """Close the capture unchanged, then say why"""
        # Guarded: closing Settings is itself a left-click, which the listener
        # would otherwise reject into a dialog over a destroyed parent.
        if self.done:
            return
        self.end(self.previous)
        messagebox.showwarning(title, body, parent=self.tray.settings_win)

    def failed(self, exc):
        """Nothing about the key was usable. All three surfaces say so."""
        if self.done:
            return
        _log_error("PTT rebind", exc)
        self.tray.output_queue.put("Error: could not bind that key")
        self.reject("Cannot bind that key", "Could not bind that key.")

    def _on_key(self, key):
        """pynput thread. Marshals to Tk rather than touching widgets here."""
        try:
            name = getattr(key, "name", None)
            if name == "esc":
                # Cancels. Settings closes on Escape too, from its own binding.
                self.tray.window.after(0, lambda: self.end(self.previous))
                return False
            if name is None:
                val, disp = f"key:{key.char}", key.char.upper()
            else:
                val, disp = f"key:{name}", name.replace("_", " ").title()
            self.tray.window.after(0, lambda: self.accept(val, disp))
        except Exception as exc:
            # Bind exc as a default: Python clears the name leaving the block.
            self.tray.window.after(0, lambda e=exc: self.failed(e))
        return False

    def _on_click(self, x, y, button, pressed):
        """Only BUTTON_MAP binds; anything else is ignored and the capture stays
        open. Left especially -- it is how the dialog itself is operated."""
        from vdict.keyboard import BUTTON_MAP

        if not pressed or button.name not in BUTTON_MAP:
            return None
        disp = (f"Mouse Side ({button.name.upper()})"
                if button.name in ("x1", "x2")
                else f"Mouse {button.name.capitalize()}")
        self.tray.window.after(0, lambda: self.accept(button.name, disp))
        return False


class VoiceDictationTray:
    """System tray wrapper for vdict.py"""

    def __init__(self):
        self.process = None
        self.output_queue = queue.Queue()
        self._exit_reported = False

        try:
            self.dpi_scale = ctypes.windll.user32.GetDpiForSystem() / 96.0
        except Exception:
            self.dpi_scale = 1.0

        # Create output window
        self.window = tk.Tk()
        self.window.title("Voice Dictation Output")
        self.window.iconbitmap(str(ICON_PATH))
        main_w, main_h = int(900 * self.dpi_scale), int(600 * self.dpi_scale)
        self.window.geometry(f"{main_w}x{main_h}")

        self._build_menu()

        # Monospace is not negotiable: the daemon prints aligned [n] counters and
        # a loading animation whose dots need a consistent advance width.
        self.console_font_size = CONSOLE_FONT_DEFAULT
        self.text = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            font=("Consolas", self.console_font_size),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.text.tag_configure(
            "sys_dim", foreground="#707070")  # Map ANSI dim gray
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)

        # Create context menu for copying text
        self.context_menu = tk.Menu(self.text, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_text)
        self.text.bind("<Button-3>", self._show_context_menu)

        # Map the 'X' close button to completely exit the app
        self.window.protocol("WM_DELETE_WINDOW", self.exit_app)

        # Intercept the '_' minimize button to hide to tray
        self.window.bind("<Unmap>", self._on_unmap)

        # Track geometry as it changes, not at hide time. A minimized window
        # reports its icon position.
        self._last_geometry = None
        self.window.bind("<Configure>", self._remember_geometry)

        # Bind to the window, not the text widget. The widget is disabled and
        # so never takes focus.
        self.window.bind("<Control-MouseWheel>", self._zoom_console)
        self.window.bind("<Control-Key-0>", self._reset_console_font)

        # Tk's accelerator= only draws the shortcut text on the menu item; the
        # key itself has to be bound separately or the label is a lie.
        self.window.bind("<Control-Key-c>", lambda e: self._copy_text())
        self.window.bind("<Control-Key-a>", lambda e: self._select_all())
        self.window.bind("<Control-Key-plus>", lambda e: self._zoom_step(1))
        self.window.bind("<Control-Key-equal>", lambda e: self._zoom_step(1))
        self.window.bind("<Control-Key-minus>", lambda e: self._zoom_step(-1))
        self.window.bind("<F1>", self._open_docs)

        # Start hidden
        self.window.withdraw()

        self.icon = self.create_tray_icon()

        # Tk routes callback exceptions here, and its default prints to stderr,
        # which goes nowhere under pythonw.exe.
        self.window.report_callback_exception = self._report_callback_exception

    def _report_callback_exception(self, exc_type, exc_value, exc_tb):
        """Log a Tkinter callback error and raise a toast about it"""
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)

        summary = f"{exc_type.__name__}: {exc_value}"
        if len(summary) > 120:  # noqa: PLR2004 -- display truncation, not a contract
            summary = summary[:117] + "..."

        # Toasts get truncated and are suppressed under Focus Assist, so the
        # log above is the durable half -- this just tells them to go look.
        try:
            self.icon.notify(
                f"{summary}\n\nDetails written to {ERROR_LOG_PATH}",
                "Voice Dictation error")
        except Exception:
            pass

    def _build_menu(self):
        """Build the CUA-style menu bar.
        Mnemonics must stay unique within each menu."""
        menubar = tk.Menu(self.window)

        file_menu = tk.Menu(menubar, tearoff=0)
        # "Save As" takes A rather than S, the convention when Settings
        # already owns S in the same menu.
        file_menu.add_command(label="Save As...", underline=5,
                              command=self._save_log_as)
        file_menu.add_command(label="Vocabulary...", underline=0,
                              command=self._open_vocabulary)
        file_menu.add_separator()
        file_menu.add_command(label="Settings...", underline=0,
                              command=self.open_settings)
        file_menu.add_command(label="Hide to Tray", underline=0,
                              command=self.hide_window)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", underline=1, command=self.exit_app)
        menubar.add_cascade(label="File", underline=0, menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Copy", underline=0, accelerator="Ctrl+C",
                              command=self._copy_text)
        edit_menu.add_command(label="Select All", underline=0,
                              accelerator="Ctrl+A", command=self._select_all)
        edit_menu.add_command(label="Copy All", underline=5,
                              command=self._copy_all)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear", underline=1,
                              command=self._clear_console)
        menubar.add_cascade(label="Edit", underline=0, menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Zoom In", underline=5,
                              accelerator="Ctrl++",
                              command=lambda: self._zoom_step(1))
        view_menu.add_command(label="Zoom Out", underline=5,
                              accelerator="Ctrl+-",
                              command=lambda: self._zoom_step(-1))
        view_menu.add_command(label="Reset Zoom", underline=0,
                              accelerator="Ctrl+0",
                              command=self._reset_console_font)
        menubar.add_cascade(label="View", underline=0, menu=view_menu)

        # postcommand fires each time Help opens, so Error Log reflects
        # whether a log actually exists right now.
        help_menu = tk.Menu(menubar, tearoff=0,
                            postcommand=self._sync_help_menu)
        help_menu.add_command(label="Documentation", underline=0,
                              accelerator="F1", command=self._open_docs)
        help_menu.add_command(label="Error Log", underline=0,
                              command=self._open_error_log)
        help_menu.add_separator()
        help_menu.add_command(label="About", underline=0,
                              command=self._show_about)
        menubar.add_cascade(label="Help", underline=0, menu=help_menu)
        self._help_menu = help_menu

        self.window.config(menu=menubar)

    def _sync_help_menu(self):
        """Grey out Error Log when no log file exists."""
        self._help_menu.entryconfig(
            "Error Log",
            state=tk.NORMAL if ERROR_LOG_PATH.exists() else tk.DISABLED)

    def _open_error_log(self):
        """Open the error log in the default text editor"""
        os.startfile(ERROR_LOG_PATH)

    def _open_docs(self, event=None):
        """Open the project page in the default browser.
        Not the local README.md: Windows usually has no .md handler, so it opens raw."""
        webbrowser.open(PROJECT_URL)
        return "break"

    def _reseed_vocabulary_if_missing(self):
        """Restore vocabulary.txt from the template if it is absent.
        Returns whether a reseed happened -- callers decide when to log it."""
        if VOCABULARY_PATH.exists():
            return False
        shutil.copyfile(VOCABULARY_TEMPLATE_PATH, VOCABULARY_PATH)
        return True

    def _open_vocabulary(self):
        """Open vocabulary.txt in the user's default .txt handler.
        Reseeds from the template first if it was deleted -- nothing to validate."""
        if self._reseed_vocabulary_if_missing():
            self.output_queue.put(VOCABULARY_RESET_MESSAGE)
        os.startfile(VOCABULARY_PATH)

    def _save_log_as(self):
        """Write the console log to a text file.
        UTF-8 is required: transcripts carry curly quotes and em-dashes."""
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save Console Log",
            defaultextension=".txt",
            initialfile="voice_dictation_log_%s.txt"
                        % datetime.now().strftime("%Y-%m-%d"),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return  # User cancelled the dialog
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.text.get("1.0", tk.END).rstrip("\n") + "\n")

    def _select_all(self):
        """Select the entire log"""
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        return "break"

    def _copy_all(self):
        """Copy the entire log to the clipboard"""
        self.window.clipboard_clear()
        self.window.clipboard_append(self.text.get("1.0", tk.END).rstrip("\n"))

    def _clear_console(self):
        """Empty the log"""
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)

    def _show_about(self):
        """About dialog"""
        messagebox.showinfo(
            "About Voice Dictation",
            f"Voice Dictation v{__version__}\n\n"
            f"Offline push-to-talk speech to text.\n"
            f"{PROJECT_URL}\n\n"
            f"MIT License",
            parent=self.window)

    def _show_context_menu(self, event):
        """Display the right-click context menu"""
        # Gray out the Copy button if no text is selected
        if not self.text.tag_ranges("sel"):
            self.context_menu.entryconfig("Copy", state=tk.DISABLED)
        else:
            self.context_menu.entryconfig("Copy", state=tk.NORMAL)

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _copy_text(self):
        """Copy selected text to clipboard"""
        try:
            self.text.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def create_tray_icon(self):
        """Create system tray icon from the shared .ico"""
        wanted = ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON)
        with ICON_PATH.open("rb") as handle:
            icon = IcoImageFile(handle)
            # The .ico holds 16/32/48/256. Assigning .size selects a stored frame
            # rather than letting Windows rescale whichever one it opened.
            icon.size = min(icon.ico.sizes(), key=lambda s: abs(s[0] - wanted))
            img = icon.convert("RGBA")

        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Show Output", self.show_window, default=True),
            pystray.MenuItem("Settings...", self.open_settings),
            pystray.MenuItem("Exit", self.exit_app)
        )

        icon = pystray.Icon(
            "voice_dictation",
            img,
            "Voice Dictation",
            menu
        )

        return icon

    def start_vdict(self):
        """Start vdict.py as subprocess and capture output"""
        vdict_path = Path(__file__).parent / "vdict.py"

        # Set here, not inside the daemon: these are read at import time, and an
        # import inside the daemon can always beat code that runs after it.
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"          # immediate capture, no buffering
        env["HF_HUB_VERBOSITY"] = "error"      # no third-party chatter in our window
        env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"

        # Clear the previous run's exit report, or a daemon that dies again
        # after Save & Restart would fail silently.
        self._exit_reported = False

        self.process = subprocess.Popen(
            [sys.executable, str(vdict_path)],
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        # Into the console, not stdout, which pythonw discards. The banner is
        # NOT here: it greets once from run(), never again on a restart.
        self._log_session_block(self.process.pid)

        self.notified_slow_boot = False

        self.is_loading_model = False

        # Start thread to read output
        reader_thread = threading.Thread(
            target=self._read_output, args=(self.process.stdout,), daemon=True)
        reader_thread.start()

    def _animate_dots(self):
        """Append gray dots to the console while loading"""
        if getattr(self, 'is_loading_model', False):
            self.text.config(state=tk.NORMAL)
            self.text.insert(tk.END, ".", "sys_dim")
            self.text.see(tk.END)
            self.text.config(state=tk.DISABLED)
            self.window.after(1000, self._animate_dots)

    def _read_output(self, stdout):
        """Read subprocess output and queue it"""
        for line in stdout:
            self.output_queue.put(line.rstrip())

    # Dispatches on daemon output markers. Split by backlog B1.
    def _update_output(self):  # noqa: C901, PLR0912, PLR0915
        """Update text widget with queued output"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.text.config(state=tk.NORMAL)

                # Check for our hardcoded ANSI dim code
                is_dim = "\033[90m" in line

                # Strip all ANSI codes so they don't print as literal text
                clean_line = re.sub(r'\033\[[0-9;]*m', '', line)

                # Handle boot notification reset
                if "[SYSTEM] INITIATING DOWNLOAD" in clean_line:
                    self.notified_slow_boot = True
                    if hasattr(self, 'icon') and self.icon:
                        self.icon.notify(
                            "First-time setup: Downloading AI model. This may take a minute...",
                            "Downloading Model")
                            
                # Match both words; the version sits between them. Bare "READY"
                # is too loose -- transcribed speech flows through this stream.
                elif "Voice Dictation v" in clean_line and "READY" in clean_line:
                    if getattr(self, 'is_loading_model', False):
                        # Close the dotted line
                        self.text.insert(tk.END, "\n")
                        self.is_loading_model = False
                        
                    if getattr(self, 'notified_slow_boot', False):
                        if hasattr(self, 'icon') and self.icon:
                            self.icon.notify(
                                "Model download complete. Voice Dictation is ready!", "Ready")
                        self.notified_slow_boot = False

                # "Loading ..." is left unterminated so _animate_dots can append.
                # Close that run first, or the next line lands mid-dots.
                if (getattr(self, 'is_loading_model', False)
                        and not clean_line.startswith("Loading ")):
                    self.text.insert(tk.END, "\n")

                if is_dim:
                    if clean_line.startswith("Loading "):
                        self.text.insert(tk.END, clean_line, "sys_dim")
                        self.is_loading_model = True
                        self.window.after(1000, self._animate_dots)
                    else:
                        self.text.insert(tk.END, clean_line + "\n", "sys_dim")
                else:
                    self.text.insert(tk.END, clean_line + "\n")

                self.text.see(tk.END)
                self.text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        except Exception as e:
            _log_error("Output update error", e)

        try:
            if self.process and not getattr(self, '_exit_reported', False):
                exit_code = self.process.poll()
                if exit_code is not None:
                    self._exit_reported = True
                    if exit_code == EXIT_NO_MICROPHONE:
                        # Open Settings rather than exiting; the tray is the only
                        # way to pick another device.
                        self.open_settings()
                        messagebox.showerror(
                            "No Microphone Detected",
                            "Voice Dictation could not find the configured "
                            "microphone.\n\nPick a different one in the "
                            "Settings window and click Save & Restart, or "
                            "reconnect the device and click Save & Restart.",
                            parent=self.settings_win)
                        return
                    self.text.config(state=tk.NORMAL)
                    self.text.insert(
                        tk.END, f"\n[vdict.py exited with code {exit_code}]\n")
                    self.text.see(tk.END)
                    self.text.config(state=tk.DISABLED)
        except Exception as e:
            _log_error("Exit-check error", e)
        finally:
            # Always reschedule, even if a widget update failed, so the log
            # window can't silently freeze forever on one bad update
            self.window.after(100, self._update_output)

    def show_window(self, icon=None, item=None):
        """Show output window"""
        self.window.deiconify()
        self.window.lift()

    def _hotkey_line(self):
        """The session block's Hotkey value, and whether it reads as a fault"""
        if self.hotkey_failed:
            return (f"{self.hotkey_name} is unavailable -- another application or "
                    f"Windows already uses it. Pick a different one in Settings."), True
        if self.hotkey_name is None:
            return ("None set. Assign one in Settings to show this window "
                    "from anywhere."), False
        return f"{self.hotkey_name} shows this window from anywhere.", False

    def _log_session_block(self, pid):
        """The session block. Called only by start_vdict, so first launch and every
        engine restart print the identical thing and cannot drift apart."""
        config, _ = load_settings()
        ptt, stt = config.ptt, config.stt

        size = _model_size_on_disk(stt.model)
        model = stt.model if size is None else f"{stt.model} ({_human_size(size)})"
        hotkey_value, is_fault = self._hotkey_line()

        # The block owns its own blank line, so a restart is still separated
        # from the run above it with no startup header in between.
        self.output_queue.put("")
        for label, value, dim in (
                ("Started", f"vdict.py (PID {pid})", True),
                ("Mode", "Hold button down to dictate." if ptt.mode == "hold"
                         else "Press button once to toggle dictation.", True),
                ("Trigger", _format_bind(ptt.button), True),
                ("Hotkey", hotkey_value, not is_fault),
                ("Compute", DEVICE_LABELS[stt.device], True),
                ("Model", model, True)):
            line = _summary_line(label, value)
            self.output_queue.put(_dim(line) if dim else line)

    def _register_hotkey(self, cfg):
        """Claim the configured combination. Records what happened for the session block
        to report -- unset and already-taken are both states, never failures."""
        self.hotkey_name = cfg.name
        self.hotkey_failed = (
            cfg.vk is not None
            and not hotkey.register(cfg.modifiers, cfg.vk, self._on_hotkey))

    def _on_hotkey(self):
        """Runs on hotkey.py's owning thread, which must never touch Tk itself."""
        self.window.after(0, self._raise_window)

    def _raise_window(self):
        """Bring the output window up with keyboard focus. Nothing may precede these two
        calls -- the foreground grant Windows hands us on the keypress is momentary."""
        self.window.deiconify()
        win32gui.SetForegroundWindow(int(self.window.wm_frame(), 0))
        self.output_queue.put(
            f"\033[90m[HOTKEY] {self.hotkey_name} -- output window raised\033[0m")

    # Builds the whole dialog inline. Split by backlog B1; remove then.
    def open_settings(self, icon=None, item=None):  # noqa: C901, PLR0915
        """Open settings dialog to configure PTT mode and audio"""
        # Several independent paths reach this -- the tray menu, the first-run
        # tutorial, and missing-microphone recovery -- so never stack windows.
        existing = getattr(self, "settings_win", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    return
            except tk.TclError:
                pass  # Widget already torn down; fall through and rebuild

        settings_win = tk.Toplevel(self.window)
        self.settings_win = settings_win
        settings_win.withdraw()  # Hide immediately to prevent position flash
        settings_win.title("Settings")
        settings_win.resizable(False, False)
        settings_win.attributes("-topmost", True)

        config, _ = load_settings()

        # Create an inner frame for clean, scaled outer padding
        main_frame = tk.Frame(
            settings_win,
            padx=int(
                20 *
                self.dpi_scale),
            pady=int(
                10 *
                self.dpi_scale))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # UI Elements
        
        from tkinter import ttk
        
        # Add a professional banner to stretch the window width and look clean
        title_label = tk.Label(main_frame, text="Voice Dictation Settings",
                               font=("Segoe UI", 12, "bold"))
        title_label.pack(pady=(0, int(5 * self.dpi_scale)))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill='x', pady=(0, int(15 * self.dpi_scale)))

        # 1. Microphone
        import sounddevice as sd

        DEFAULT_MIC_LABEL = "System Default"

        # Enumerate WASAPI only. The legacy PortAudio backends list each mic
        # again, add default-device aliases, and truncate names to 31 chars.
        wasapi = next((i for i, api in enumerate(sd.query_hostapis())
                       if api['name'] == 'Windows WASAPI'), None)
        if wasapi is None:
            raise RuntimeError(
                "Windows WASAPI audio backend not available. The sounddevice "
                "install is incomplete -- rerun setup.bat.")

        mic_names = [dev['name'] for dev in sd.query_devices()
                     if dev['hostapi'] == wasapi
                     and dev['max_input_channels'] > 0]

        saved_mic = config.audio.device
        # Keep a configured-but-currently-absent device (unplugged headset) in
        # the list rather than silently snapping to something else.
        if saved_mic and saved_mic not in mic_names:
            mic_names.append(saved_mic)

        tk.Label(main_frame, text="Microphone:").pack()
        mic_var = tk.StringVar(
            value=saved_mic if saved_mic else DEFAULT_MIC_LABEL)
        tk.OptionMenu(
            main_frame, mic_var, DEFAULT_MIC_LABEL, *mic_names).pack(
            pady=(0, int(15 * self.dpi_scale)))

        # 2. PTT Config
        tk.Label(main_frame, text="PTT Button Trigger:").pack()
        button_var = tk.StringVar(value=config.ptt.button)
        button_display_var = tk.StringVar(value=_format_bind(button_var.get()))
        
        bind_btn = tk.Button(
            main_frame, 
            textvariable=button_display_var, 
            width=20,
            command=lambda: self._rebind_key(button_var, button_display_var, bind_btn)
        )
        bind_btn.pack(pady=(0, int(15 * self.dpi_scale)))

        tk.Label(main_frame, text="PTT Recording Mode:").pack()
        mode_var = tk.StringVar(value=config.ptt.mode.capitalize())
        tk.OptionMenu(
            main_frame, mode_var, "Toggle", "Hold").pack(
            pady=(
                0, int(
                    15 * self.dpi_scale)))

        # 3. AI Model & Compute
        tk.Label(main_frame, text="AI Model Size:").pack()
        ai_model_var = tk.StringVar(value=config.stt.model)
        tk.OptionMenu(main_frame,
                      ai_model_var,
                      "tiny.en",
                      "base.en",
                      "small.en",
                      "medium.en",
                      "large-v3").pack(pady=(0,
                                             int(15 * self.dpi_scale)))

        # Determine if CUDA is available for hardware fallback
        def _has_cuda():
            try:
                import os
                import glob
                import site
                
                old_path = os.environ.get("PATH", "")
                for sp in site.getsitepackages() + [site.getusersitepackages()]:
                    nvidia_bins = glob.glob(os.path.join(sp, "nvidia", "*", "bin"))
                    if nvidia_bins:
                        os.environ["PATH"] = ";".join(nvidia_bins) + ";" + old_path
                        break
                        
                import ctranslate2
                count = ctranslate2.get_cuda_device_count()
                os.environ["PATH"] = old_path
                return count > 0
            except Exception:
                return False

        has_cuda = _has_cuda()

        tk.Label(main_frame, text="Compute Device:").pack()
        reverse_device_mapping = {v: k for k, v in DEVICE_LABELS.items()}
        device_var = tk.StringVar(value=DEVICE_LABELS[config.stt.device])

        dev_menu = tk.OptionMenu(main_frame, device_var, "CPU", "GPU (CUDA)")
        if not has_cuda:
            # Hardware Fallback: Disable GPU option if no CUDA device exists
            dev_menu["menu"].entryconfigure("GPU (CUDA)", state="disabled")
            if device_var.get() == "GPU (CUDA)":
                device_var.set("CPU")
        dev_menu.pack(pady=(0, int(15 * self.dpi_scale)))

        # 4. Audio Beeps
        audio_var = tk.BooleanVar(value=config.audio.feedback)
        tk.Checkbutton(
            main_frame, text="Enable Audio Beeps", variable=audio_var).pack(
            pady=(0, int(15 * self.dpi_scale)))
            
        # 5. Open Console on Boot
        open_console_var = tk.BooleanVar(value=config.ui.open_console_on_boot)
        tk.Checkbutton(
            main_frame, text="Show Output Window on Startup", variable=open_console_var).pack(
            pady=(0, int(15 * self.dpi_scale)))

        # 6. Output window hotkey
        hotkey_binding = self._build_hotkey_row(main_frame)

        def _get_pos():
            geom = settings_win.geometry()
            match = re.search(r'\+?(-?\d+)\+?(-?\d+)$', geom)
            if match:
                return int(match.group(1)), int(match.group(2))
            return settings_win.winfo_x(), settings_win.winfo_y()

        def save_and_restart():
            mic = mic_var.get()
            config.audio.device = "" if mic == DEFAULT_MIC_LABEL else mic
            config.ptt.button = button_var.get()
            config.ptt.mode = cast(Literal["hold", "toggle"], mode_var.get().lower())
            config.audio.feedback = audio_var.get()
            config.stt.model = ai_model_var.get()
            config.stt.device = cast(
                Literal["cpu", "cuda"], reverse_device_mapping[device_var.get()])
            config.hotkey = HotkeyConfig(**hotkey_binding)

            x, y = _get_pos()
            config.ui.settings_pos = Pos(x=x, y=y)
            config.ui.open_console_on_boot = open_console_var.get()

            save_settings(config)

            settings_win.destroy()
            self.restart_daemon()

        def on_close():
            x, y = _get_pos()
            config.ui.settings_pos = Pos(x=x, y=y)
            save_settings(config)
            settings_win.destroy()

        settings_win.protocol("WM_DELETE_WINDOW", on_close)
        # Bound on the toplevel, so a capture in progress swallows Escape first.
        settings_win.bind("<Escape>", lambda e: on_close())
        # <Destroy>, not on_close: save_and_restart calls destroy() directly and
        # destroy() never fires the WM_DELETE_WINDOW handler.
        settings_win.bind("<Destroy>",
                          lambda e: self._rebind_on_close(e, settings_win), add="+")
        tk.Button(main_frame, text="Save & Restart", command=save_and_restart).pack(
            pady=(int(5 * self.dpi_scale), 0))

        # Tk already scales point sizes by DPI. Do not multiply by dpi_scale.
        version_label = tk.Label(main_frame, text=f"v{__version__}", fg="gray", font=("Arial", 7))
        version_label.pack(side=tk.BOTTOM, anchor="e")

        # Force Tkinter to calculate required layout dimensions
        settings_win.update_idletasks()

        # Fall back to the default corner if the remembered spot is no longer on
        # any attached display. Same guard as the console.
        saved_pos = config.ui.settings_pos
        if saved_pos and _is_on_screen(saved_pos.x, saved_pos.y):
            x, y = saved_pos.x, saved_pos.y
        else:
            # Default to bottom right using auto-calculated dimensions
            win_width = settings_win.winfo_reqwidth()
            win_height = settings_win.winfo_reqheight()
            screen_width = settings_win.winfo_screenwidth()
            screen_height = settings_win.winfo_screenheight()
            x = screen_width - win_width - int(20 * self.dpi_scale)
            y = screen_height - win_height - \
                int(60 * self.dpi_scale)  # Account for Windows taskbar

        # Apply absolute coordinates, allowing window to shrink-wrap width and
        # height naturally
        settings_win.geometry(f"+{x}+{y}")
        settings_win.deiconify()  # Show the window at the correct position

    def _build_hotkey_row(self, parent):
        """Label and picker button for the output-window hotkey.
        Returns the mutable binding the capture writes into and Save reads back."""
        cfg, _ = load_settings()
        binding = cfg.hotkey.model_dump()

        tk.Label(parent, text="Output Window Hotkey:").pack()
        display = tk.StringVar(value=binding["name"] or "None")
        btn = tk.Button(parent, textvariable=display, width=20)
        btn.config(command=lambda: self._capture_hotkey(btn, display, binding))
        btn.pack(pady=(0, int(15 * self.dpi_scale)))
        return binding

    def _rebind_on_close(self, event, settings_win):
        """Settings is gone -- put the hotkey back from whatever is on disk now.
        Saved or abandoned, disk already holds the right answer."""
        # <Destroy> fires for every descendant; the guard keeps this to one call.
        if event.widget is not settings_win:
            return
        # Silent. A Save & Restart reprints the session block anyway, and closing
        # without saving changed nothing on disk to announce.
        cfg, _ = load_settings()
        hotkey.unregister()
        self._register_hotkey(cfg.hotkey)

    def _confirm_bare_key(self, name):
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
            parent=self.settings_win)

    def _capture_hotkey(self, btn, display, binding):
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
            if mods == 0 and not self._confirm_bare_key(name):
                restore()
                return "break"

            binding.update(modifiers=mods, vk=event.keycode, name=name)
            display.set(name)
            return "break"

        # "break" also stops Tab, Return and space reaching the dialog's widgets.
        btn.bind("<KeyPress>", on_key)

    def _rebind_key(self, btn_var, disp_var, tk_btn):
        """Capture one push-to-talk trigger into the Settings button"""
        _PTTCapture(self, btn_var, disp_var, tk_btn).start()

    def _remember_geometry(self, event):
        """Cache the console's geometry while it is actually on screen"""
        if event.widget is self.window and self.window.state() == 'normal':
            self._last_geometry = self.window.geometry()

    def _set_console_font_size(self, size):
        """Apply a console text size, clamped to a legible range"""
        self.console_font_size = max(
            CONSOLE_FONT_MIN, min(CONSOLE_FONT_MAX, size))
        self.text.config(font=("Consolas", self.console_font_size))

    def _zoom_step(self, direction):
        """Change the console text size by one step"""
        self._set_console_font_size(self.console_font_size + direction)
        return "break"

    def _zoom_console(self, event):
        """Ctrl+scroll to resize the console text"""
        return self._zoom_step(1 if event.delta > 0 else -1)

    def _reset_console_font(self, event=None):
        """Ctrl+0 to return to the default size"""
        self._set_console_font_size(CONSOLE_FONT_DEFAULT)
        return "break"

    def _save_console_state(self):
        """Persist the console's size, position, and text size.
        Called on hide and exit only; zooming fires once per scroll notch."""
        config, _ = load_settings()
        if self._last_geometry:
            config.ui.console_geometry = self._last_geometry
        config.ui.console_font_size = self.console_font_size
        save_settings(config)

    def hide_window(self):
        """Hide output window"""
        self._save_console_state()
        self.window.withdraw()

    def _on_unmap(self, event):
        """Intercept minimize event to hide to tray"""
        if event.widget == self.window and self.window.state() == 'iconic':
            self.hide_window()

    def exit_app(self, icon=None, item=None):
        """Exit application and kill subprocess"""
        if not messagebox.askokcancel(
                "Close Voice Dictation", "Click OK to exit Voice Dictation.",
                parent=self.window):
            return
            
        self._force_quit()

    def _stop_daemon(self):
        """Terminate the daemon, escalating to kill if it will not exit.
        The single definition of how the daemon dies. Shutdown and restart both use it."""
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def restart_daemon(self):
        """Swap the running daemon for a fresh one.
        Internal only -- there is no user-facing restart command."""
        self._stop_daemon()
        self.start_vdict()

    def _run_shutdown_steps(self):
        """Best-effort housekeeping before exit -- one failure never blocks
        the rest (toast, disk, console each try); returns whether anything failed."""
        steps = (
            (self._save_console_state,
             "Console position/size/font not saved -- next launch uses the "
             "last saved state."),
            (self._stop_daemon,
             "Daemon may still be running -- check Task Manager for an "
             "orphaned vdict.py process."),
            (self.icon.stop,
             "Tray icon may linger in the notification area until Explorer "
             "refreshes."))
        any_failed = False
        for step, meaning in steps:
            try:
                step()
            except Exception as exc:
                any_failed = True
                self._report_callback_exception(type(exc), exc, exc.__traceback__)
                try:
                    self.output_queue.put(f"[SHUTDOWN ERROR] {step.__name__}: {meaning}")
                except Exception:
                    pass
        return any_failed

    def _force_quit(self):
        """Hard exit without prompting. Housekeeping is best-effort -- exit
        itself is never conditional on any of it succeeding."""
        if self._run_shutdown_steps():
            messagebox.showerror(
                "Voice Dictation",
                "Something went wrong while shutting down. Check the output "
                "window or the error log for details.\n\nClick OK to exit anyway.",
                parent=self.window)
        try:
            self.window.quit()
        except BaseException:
            pass

    def run(self):
        """Run the tray application"""
        # Seeds config.json from the Config model's defaults when absent. Must
        # run before start_vdict(), because the daemon reads config.json itself.
        config, reset_reason = load_settings()

        # Seeds vocabulary.txt from the tracked template when absent -- same
        # ordering reason. Logging is deferred below, under the banner too.
        vocabulary_reseeded = self._reseed_vocabulary_if_missing()

        # Restore the console's size and position, ignoring a geometry whose
        # origin is no longer on any attached display.
        saved_geometry = config.ui.console_geometry
        if saved_geometry:
            origin = _geometry_origin(saved_geometry)
            if origin and _is_on_screen(*origin):
                self.window.geometry(saved_geometry)

        self._set_console_font_size(config.ui.console_font_size)

        # Startup header. Once per app launch -- start_vdict must never print
        # it, since a restart re-greeting the user reads as a wiped log.
        for line in ("\033[97m" + "=" * 60,
                     " Welcome to Voice Dictation",
                     f" {PROJECT_URL} | MIT License",
                     "=" * 60 + "\033[0m"):
            self.output_queue.put(line)

        # Before start_vdict, so the session block has a true Hotkey line.
        self._register_hotkey(config.hotkey)
        self.start_vdict()

        # Queued after start_vdict, which already queued the session block
        # itself -- these land after both, not right under the banner.
        if vocabulary_reseeded:
            self.output_queue.put(VOCABULARY_RESET_MESSAGE)
        if reset_reason:
            for line in reset_reason:
                self.output_queue.put(f"[SETTINGS RESET] {line}")
            self.output_queue.put(
                "[SETTINGS RESET] Open Settings from the tray icon to "
                "reconfigure.")
            self.output_queue.put("")

        if config.ui.open_console_on_boot:
            # Open it (will happen every time until user disables it in Settings)
            self.show_window()

        if config.ui.first_run:
            # Pop settings menu on first run as an implicit tutorial
            self.window.after(500, self.open_settings)

            # Disable first_run flag
            config.ui.first_run = False
            save_settings(config)

        # Start periodic output update
        self.window.after(100, self._update_output)

        # Run tray icon in background thread
        icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        icon_thread.start()

        # Run tkinter mainloop in main thread
        self.window.mainloop()


def _log_startup_crash():
    """Write an unhandled startup exception to the error log and show it on screen"""
    summary = traceback.format_exc().strip().splitlines()[-1]

    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        traceback.print_exc(file=f)

    # Config has no fallbacks, so a malformed config.json lands here. There is
    # no console yet at this point, so the dialog is the only visible surface.
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Voice Dictation failed to start",
            f"{summary}\n\nFull details were written to:\n{ERROR_LOG_PATH}\n\n"
            f"If this mentions config.json, delete that file and relaunch "
            f"to restore the default settings.")
        root.destroy()
    except Exception:
        # Never let the error reporter mask the original traceback, which
        # the caller re-raises and the log above already captured.
        pass


if __name__ == "__main__":
    try:
        # Without an explicit AUMID, Windows taskbar groups this window under
        # pythonw.exe's identity and shows its icon instead of ours.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VoiceDictation.Tray")

        # Single-instance check using Windows mutex.
        # NULL security attributes is the documented default; the stub omits it.
        mutex = win32event.CreateMutex(
            None, False, "VoiceDictationTrayMutex")  # pyright: ignore[reportArgumentType]
        if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "Voice Dictation",
                "Voice Dictation is already running in your system tray.")
            sys.exit(1)

        app = VoiceDictationTray()
        app.run()
    except Exception:
        _log_startup_crash()
        raise
