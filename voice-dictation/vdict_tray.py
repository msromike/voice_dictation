#!/usr/bin/env python3
"""Voice Dictation - System Tray Wrapper (Chunk 2b: Capture and display output)"""
import sys

__version__ = "1.0.0"

import subprocess
import threading
import traceback
import queue
import tkinter as tk
from tkinter import scrolledtext, messagebox
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
import win32event
import win32api
import ctypes

try:
    # Tell Windows this app handles its own DPI scaling to fix Tkinter blur
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


DEFAULT_CONFIG = {
    "audio": {
        "device": "",
        "sample_rate": 16000,
        "feedback": True
    },
    "ptt": {
        "button": "key:ctrl_r",
        "mode": "hold"
    },
    "keyboard": {
        "preserve_clipboard": True
    },
    "stt": {
        "model": "base.en",
        "device": "cpu",
        "prompt_file": "prompts/dev.txt"
    },
    "ui": {
        "open_console_on_boot": True,
        "first_run": True
    }
}


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

        # Text area with scrollbar
        self.text = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            font=("Consolas", 12),
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

        # Start hidden
        self.window.withdraw()

        self.icon = self.create_tray_icon()

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
        """Create system tray icon with microphone image"""
        # Create simple microphone icon
        img = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(img)

        # Draw microphone shape
        draw.ellipse([20, 10, 44, 35], fill='black')  # Mic head
        draw.rectangle([28, 30, 36, 45], fill='black')  # Mic body
        draw.line([22, 50, 42, 50], fill='black', width=3)  # Base
        draw.line([32, 45, 32, 50], fill='black', width=3)  # Stand

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
        import os
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        self.process = subprocess.Popen(
            [sys.executable, str(vdict_path)],
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        print(f"Started vdict.py (PID: {self.process.pid})")
        
        # Inject welcome banner into the console output queue
        banner = [
            "\033[97m============================================================",
            " Welcome to Voice Dictation",
            " github.com/msromike/voice_dictation | MIT License",
            "============================================================",
            " Settings, console access, and app controls live in your ",
            " system tray (microphone icon in the bottom right corner).",
            "============================================================\033[0m",
            ""
        ]
        for line in banner:
            self.output_queue.put(line)

        self.notified_slow_boot = False

        self.is_loading_model = False

        # Start thread to read output
        reader_thread = threading.Thread(target=self._read_output, daemon=True)
        reader_thread.start()

    def _animate_dots(self):
        """Append gray dots to the console while loading"""
        if getattr(self, 'is_loading_model', False):
            self.text.config(state=tk.NORMAL)
            self.text.insert(tk.END, ".", "sys_dim")
            self.text.see(tk.END)
            self.text.config(state=tk.DISABLED)
            self.window.after(1000, self._animate_dots)

    def _read_output(self):
        """Read subprocess output and queue it"""
        for line in self.process.stdout:
            self.output_queue.put(line.rstrip())

    def _update_output(self):
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
                            
                elif "Voice Dictation READY" in clean_line:
                    if getattr(self, 'is_loading_model', False):
                        # Close the dotted line
                        self.text.insert(tk.END, "\n")
                        self.is_loading_model = False
                        
                    if getattr(self, 'notified_slow_boot', False):
                        if hasattr(self, 'icon') and self.icon:
                            self.icon.notify(
                                "Model download complete. Voice Dictation is ready!", "Ready")
                        self.notified_slow_boot = False

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
            print(f"Output update error: {e}")

        try:
            if self.process and not getattr(self, '_exit_reported', False):
                exit_code = self.process.poll()
                if exit_code is not None:
                    self._exit_reported = True
                    if exit_code == 2:
                        messagebox.showerror("No Microphone Detected", "Voice Dictation could not find a valid microphone.\n\nPlease plug in a microphone and restart the app.", parent=self.window)
                        self._force_quit()
                        return
                    self.text.config(state=tk.NORMAL)
                    self.text.insert(
                        tk.END, f"\n[vdict.py exited with code {exit_code}]\n")
                    self.text.see(tk.END)
                    self.text.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Exit-check error: {e}")
        finally:
            # Always reschedule, even if a widget update failed, so the log
            # window can't silently freeze forever on one bad update
            self.window.after(100, self._update_output)

    def show_window(self, icon=None, item=None):
        """Show output window"""
        self.window.deiconify()
        self.window.lift()

    def open_settings(self, icon=None, item=None):
        """Open settings dialog to configure PTT mode and audio"""
        settings_win = tk.Toplevel(self.window)
        settings_win.withdraw()  # Hide immediately to prevent position flash
        settings_win.title("Settings")
        settings_win.resizable(False, False)
        settings_win.attributes("-topmost", True)

        # Load config
        config_path = Path(__file__).parent / "config.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            config = DEFAULT_CONFIG

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
        title_label = tk.Label(main_frame, text="Voice Dictation Settings", font=("Segoe UI", 12, "bold"))
        title_label.pack(pady=(0, int(5 * self.dpi_scale)))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill='x', pady=(0, int(15 * self.dpi_scale)))

        # 1. PTT Config
        tk.Label(main_frame, text="PTT Button Trigger:").pack()
        button_var = tk.StringVar(
            value=config.get("ptt", {}).get("button", "key:ctrl_r"))
            
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
        mode_var = tk.StringVar(
            value=config.get(
                "ptt", {}).get(
                "mode", "toggle").capitalize())
        tk.OptionMenu(
            main_frame, mode_var, "Toggle", "Hold").pack(
            pady=(
                0, int(
                    15 * self.dpi_scale)))

        # 2. AI Model & Compute
        tk.Label(main_frame, text="AI Model Size:").pack()
        ai_model_var = tk.StringVar(
            value=config.get(
                "stt", {}).get(
                "model", "small.en"))
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
        current_dev = config.get("stt", {}).get("device", "cpu")
        device_var = tk.StringVar(value=device_mapping.get(current_dev, "CPU"))

        dev_menu = tk.OptionMenu(main_frame, device_var, "CPU", "GPU (CUDA)")
        if not has_cuda:
            # Hardware Fallback: Disable GPU option if no CUDA device exists
            dev_menu["menu"].entryconfigure("GPU (CUDA)", state="disabled")
            if device_var.get() == "GPU (CUDA)":
                device_var.set("CPU")
        dev_menu.pack(pady=(0, int(15 * self.dpi_scale)))

        # 3. Audio Beeps
        audio_var = tk.BooleanVar(
            value=config.get("audio", {}).get("feedback", True))
        tk.Checkbutton(
            main_frame, text="Enable Audio Beeps", variable=audio_var).pack(
            pady=(0, int(15 * self.dpi_scale)))
            
        # 4. Open Console on Boot
        open_console_var = tk.BooleanVar(
            value=config.get("ui", {}).get("open_console_on_boot", True))
        tk.Checkbutton(
            main_frame, text="Show Console on Startup", variable=open_console_var).pack(
            pady=(0, int(15 * self.dpi_scale)))

        def _get_pos():
            geom = settings_win.geometry()
            match = re.search(r'\+?(-?\d+)\+?(-?\d+)$', geom)
            if match:
                return int(match.group(1)), int(match.group(2))
            return settings_win.winfo_x(), settings_win.winfo_y()

        def save_and_restart():
            config.setdefault("ptt", {})["button"] = button_var.get()
            config.setdefault("ptt", {})["mode"] = mode_var.get().lower()
            config.setdefault("audio", {})["feedback"] = audio_var.get()
            config.setdefault("stt", {})["model"] = ai_model_var.get()
            config.setdefault("stt", {})["device"] = reverse_device_mapping.get(
                device_var.get(), "cpu")

            x, y = _get_pos()
            config.setdefault("ui", {})["settings_pos"] = {"x": x, "y": y}
            config.setdefault("ui", {})["open_console_on_boot"] = open_console_var.get()

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            settings_win.destroy()

            # Restart subprocess
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.start_vdict()

        def on_close():
            x, y = _get_pos()
            config.setdefault("ui", {})["settings_pos"] = {"x": x, "y": y}
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            settings_win.destroy()

        settings_win.protocol("WM_DELETE_WINDOW", on_close)
        tk.Button(main_frame, text="Save & Restart", command=save_and_restart).pack(
            pady=(int(5 * self.dpi_scale), 0))

        # Version Watermark
        version_label = tk.Label(main_frame, text=f"v{__version__}", fg="gray", font=("Arial", int(7 * self.dpi_scale)))
        version_label.pack(side=tk.BOTTOM, anchor="e")

        # Force Tkinter to calculate required layout dimensions
        settings_win.update_idletasks()

        # Set geometry (remembered or bottom right)
        saved_pos = config.get("ui", {}).get("settings_pos")
        if saved_pos:
            x, y = saved_pos.get("x", 0), saved_pos.get("y", 0)
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

    def hide_window(self):
        """Hide output window"""
        self.window.withdraw()

    def _on_unmap(self, event):
        """Intercept minimize event to hide to tray"""
        if event.widget == self.window and self.window.state() == 'iconic':
            self.hide_window()

    def exit_app(self, icon=None, item=None):
        """Exit application and kill subprocess"""
        if not messagebox.askokcancel("Close Voice Dictation", "Click OK to exit Voice Dictation.", parent=self.window):
            return
            
        self._force_quit()

    def _force_quit(self):
        """Hard exit without prompting"""
        print("Stopping vdict.py...")
        if getattr(self, 'process', None):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.icon.stop()
        try:
            self.window.quit()
        except BaseException:
            pass

    def run(self):
        """Run the tray application"""
        config_path = Path(__file__).parent / "config.json"
        
        # Self-healing config generation
        if not config_path.exists():
            with open(config_path, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)

        # Start vdict.py subprocess
        self.start_vdict()

        # Check if we should open console on boot
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            config = DEFAULT_CONFIG
            
        if config.get("ui", {}).get("open_console_on_boot", True):
            # Open it (will happen every time until user disables it in Settings)
            self.show_window()
            
        if config.get("ui", {}).get("first_run", True):
            # Pop settings menu on first run as an implicit tutorial
            self.window.after(500, self.open_settings)
            
            # Disable first_run flag
            config.setdefault("ui", {})["first_run"] = False
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

        # Start periodic output update
        self.window.after(100, self._update_output)

        # Run tray icon in background thread
        icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        icon_thread.start()

        # Run tkinter mainloop in main thread
        self.window.mainloop()


def _log_startup_crash():
    """Write an unhandled startup exception to a log file next to this
    script -- a console-less launch (e.g. Windows startup shortcut) would
    otherwise swallow the traceback invisibly."""
    log_path = Path(__file__).parent / "tray_error.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        traceback.print_exc(file=f)


if __name__ == "__main__":
    try:
        # Single-instance check using Windows mutex
        mutex = win32event.CreateMutex(None, False, "VoiceDictationTrayMutex")
        if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Voice Dictation", "Voice Dictation is already running in your system tray.")
            sys.exit(1)

        app = VoiceDictationTray()
        app.run()
    except Exception:
        _log_startup_crash()
        raise
