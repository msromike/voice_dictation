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
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from datetime import datetime
import webbrowser
import json
import re
from pathlib import Path
from PIL.IcoImagePlugin import IcoImageFile
import pystray
import win32event
import win32api
import ctypes

# Safe to import at module level only because vdict/__init__.py is bare and
# config.py pulls in nothing heavier than json and pathlib. Keep it that way.
from vdict.config import VOCABULARY_PATH, EXIT_NO_MICROPHONE

try:
    # Tell Windows this app handles its own DPI scaling to fix Tkinter blur
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# Win32 GetLastError value returned when the single-instance mutex exists.
ERROR_ALREADY_EXISTS = 183

# GetSystemMetrics index for the tray/small-icon edge length.
SM_CXSMICON = 49

CONFIG_PATH = Path(__file__).parent / "config.json"
CONFIG_TEMPLATE_PATH = Path(__file__).parent / "config.default.json"

# Shared by the tray, the Desktop shortcut and the Startup shortcut.
ICON_PATH = Path(__file__).parent.parent / "images" / "vdict.ico"

# Repo root, beside vocabulary.txt. Created at import so the log is writable
# before anything can fail.
LOG_DIR = Path(__file__).parent.parent / "logs"
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


def load_settings():
    """Read config.json, seeding from config.default.json on first run. Defaults live
    there and nowhere else. Unparseable JSON is replaced wholesale, never merged."""
    if not CONFIG_PATH.exists():
        if not CONFIG_TEMPLATE_PATH.exists():
            raise RuntimeError(
                f"Missing {CONFIG_TEMPLATE_PATH.name} -- the install is "
                f"incomplete. Re-clone the repository or restore that file.")
        shutil.copyfile(CONFIG_TEMPLATE_PATH, CONFIG_PATH)

    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        shutil.copyfile(CONFIG_TEMPLATE_PATH, CONFIG_PATH)
        with open(CONFIG_PATH, "r") as f:
            return json.load(f), str(exc)


def save_settings(config):
    """Write config.json back to disk"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


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


def _is_on_screen(x, y):
    """True when (x, y) lands on the desktop spanning every attached monitor.
    The 100/60 margin keeps the title bar grabbable rather than flush to an edge."""
    metric = ctypes.windll.user32.GetSystemMetrics
    virtual_x, virtual_y = metric(76), metric(77)
    virtual_w, virtual_h = metric(78), metric(79)
    return (virtual_x <= x <= virtual_x + virtual_w - 100
            and virtual_y <= y <= virtual_y + virtual_h - 60)


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
                f"{summary}\n\nDetails written to logs\\tray_error.log",
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

    def _open_vocabulary(self):
        """Open vocabulary.txt in the user's default .txt handler"""
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

        # Disable Python output buffering for immediate capture
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

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
        # Inject welcome banner into the console output queue
        banner = [
            "\033[97m============================================================",
            " Welcome to Voice Dictation",
            f" {PROJECT_URL} | MIT License",
            "============================================================\033[0m",
            ""
        ]
        for line in banner:
            self.output_queue.put(line)

        # Into the console, not stdout, which pythonw discards.
        self.output_queue.put(
            f"\033[90mStarted vdict.py (PID: {self.process.pid})\033[0m")

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

        saved_mic = config["audio"]["device"]
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
        button_var = tk.StringVar(value=config["ptt"]["button"])
            
        def _format_bind(val):
            if val.startswith("key:"):
                return val[4:].replace('_', ' ').title()
            if val in ["left", "right", "middle"]:
                return f"Mouse {val.capitalize()}"
            if val in ["x1", "x2", "side"]:
                return f"Mouse Side ({val.upper()})"
            return val.title()
            
        button_display_var = tk.StringVar(value=_format_bind(button_var.get()))
        
        bind_btn = tk.Button(
            main_frame, 
            textvariable=button_display_var, 
            width=20,
            command=lambda: self._rebind_key(button_var, button_display_var, bind_btn)
        )
        bind_btn.pack(pady=(0, int(15 * self.dpi_scale)))

        tk.Label(main_frame, text="PTT Recording Mode:").pack()
        mode_var = tk.StringVar(value=config["ptt"]["mode"].capitalize())
        tk.OptionMenu(
            main_frame, mode_var, "Toggle", "Hold").pack(
            pady=(
                0, int(
                    15 * self.dpi_scale)))

        # 3. AI Model & Compute
        tk.Label(main_frame, text="AI Model Size:").pack()
        ai_model_var = tk.StringVar(value=config["stt"]["model"])
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
        device_mapping = {"cpu": "CPU", "cuda": "GPU (CUDA)"}
        reverse_device_mapping = {"CPU": "cpu", "GPU (CUDA)": "cuda"}
        device_var = tk.StringVar(value=device_mapping[config["stt"]["device"]])

        dev_menu = tk.OptionMenu(main_frame, device_var, "CPU", "GPU (CUDA)")
        if not has_cuda:
            # Hardware Fallback: Disable GPU option if no CUDA device exists
            dev_menu["menu"].entryconfigure("GPU (CUDA)", state="disabled")
            if device_var.get() == "GPU (CUDA)":
                device_var.set("CPU")
        dev_menu.pack(pady=(0, int(15 * self.dpi_scale)))

        # 4. Audio Beeps
        audio_var = tk.BooleanVar(value=config["audio"]["feedback"])
        tk.Checkbutton(
            main_frame, text="Enable Audio Beeps", variable=audio_var).pack(
            pady=(0, int(15 * self.dpi_scale)))
            
        # 5. Open Console on Boot
        open_console_var = tk.BooleanVar(value=config["ui"]["open_console_on_boot"])
        tk.Checkbutton(
            main_frame, text="Show Output on Startup", variable=open_console_var).pack(
            pady=(0, int(15 * self.dpi_scale)))

        def _get_pos():
            geom = settings_win.geometry()
            match = re.search(r'\+?(-?\d+)\+?(-?\d+)$', geom)
            if match:
                return int(match.group(1)), int(match.group(2))
            return settings_win.winfo_x(), settings_win.winfo_y()

        def save_and_restart():
            mic = mic_var.get()
            config["audio"]["device"] = "" if mic == DEFAULT_MIC_LABEL else mic
            config["ptt"]["button"] = button_var.get()
            config["ptt"]["mode"] = mode_var.get().lower()
            config["audio"]["feedback"] = audio_var.get()
            config["stt"]["model"] = ai_model_var.get()
            config["stt"]["device"] = reverse_device_mapping[device_var.get()]

            x, y = _get_pos()
            config["ui"]["settings_pos"] = {"x": x, "y": y}
            config["ui"]["open_console_on_boot"] = open_console_var.get()

            save_settings(config)

            settings_win.destroy()
            self.restart_daemon()

        def on_close():
            x, y = _get_pos()
            config["ui"]["settings_pos"] = {"x": x, "y": y}
            save_settings(config)
            settings_win.destroy()

        settings_win.protocol("WM_DELETE_WINDOW", on_close)
        tk.Button(main_frame, text="Save & Restart", command=save_and_restart).pack(
            pady=(int(5 * self.dpi_scale), 0))

        # Tk already scales point sizes by DPI. Do not multiply by dpi_scale.
        version_label = tk.Label(main_frame, text=f"v{__version__}", fg="gray", font=("Arial", 7))
        version_label.pack(side=tk.BOTTOM, anchor="e")

        # Force Tkinter to calculate required layout dimensions
        settings_win.update_idletasks()

        # Fall back to the default corner if the remembered spot is no longer on
        # any attached display. Same guard as the console.
        saved_pos = config["ui"]["settings_pos"]
        if saved_pos and _is_on_screen(saved_pos["x"], saved_pos["y"]):
            x, y = saved_pos["x"], saved_pos["y"]
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

    def _rebind_key(self, btn_var, disp_var, tk_btn):
        """Temporary keycatcher listener for settings UI"""
        disp_var.set("Press any key...")
        tk_btn.config(state="disabled")

        listeners = []

        def _finish_bind(val, disp):
            btn_var.set(val)
            disp_var.set(disp)
            tk_btn.config(state="normal")
            for lst in listeners:
                lst.stop()

        def on_k_press(key):
            try:
                if hasattr(key, 'name'):
                    val = f"key:{key.name}"
                    disp = key.name.replace('_', ' ').title()
                else:
                    val = f"key:{key.char}"
                    disp = key.char.upper()
                self.window.after(0, lambda: _finish_bind(val, disp))
                return False
            except Exception:
                return False

        def on_m_click(x, y, button, pressed):
            if pressed:
                val = button.name
                disp = f"Mouse {button.name.capitalize()}"
                if val in ['x1', 'x2']:
                    disp = f"Mouse Side ({val.upper()})"
                self.window.after(0, lambda: _finish_bind(val, disp))
                return False

        from pynput import mouse, keyboard
        k_listener = keyboard.Listener(on_press=on_k_press)
        m_listener = mouse.Listener(on_click=on_m_click)
        listeners.extend([k_listener, m_listener])
        k_listener.start()
        m_listener.start()

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
            config["ui"]["console_geometry"] = self._last_geometry
        config["ui"]["console_font_size"] = self.console_font_size
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

    def _force_quit(self):
        """Hard exit without prompting"""
        self._save_console_state()
        self._stop_daemon()
        self.icon.stop()
        try:
            self.window.quit()
        except BaseException:
            pass

    def run(self):
        """Run the tray application"""
        # Seeds config.json from config.default.json when absent. Must run
        # before start_vdict(), because the daemon reads config.json itself.
        config, reset_reason = load_settings()

        # Restore the console's size and position, ignoring a geometry whose
        # origin is no longer on any attached display.
        saved_geometry = config["ui"]["console_geometry"]
        if saved_geometry:
            origin = _geometry_origin(saved_geometry)
            if origin and _is_on_screen(*origin):
                self.window.geometry(saved_geometry)

        self._set_console_font_size(config["ui"]["console_font_size"])

        # Start vdict.py subprocess
        self.start_vdict()

        # Queued after start_vdict so it lands under the welcome banner
        if reset_reason:
            self.output_queue.put(
                f"[SETTINGS RESET] config.json could not be read "
                f"({reset_reason}).")
            self.output_queue.put(
                "[SETTINGS RESET] Default settings have been restored. Open "
                "Settings from the tray icon to reconfigure.")
            self.output_queue.put("")

        if config["ui"]["open_console_on_boot"]:
            # Open it (will happen every time until user disables it in Settings)
            self.show_window()

        if config["ui"]["first_run"]:
            # Pop settings menu on first run as an implicit tutorial
            self.window.after(500, self.open_settings)

            # Disable first_run flag
            config["ui"]["first_run"] = False
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
