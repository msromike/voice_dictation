#!/usr/bin/env python3
"""Voice Dictation - System Tray Wrapper (Chunk 2b: Capture and display output)"""

import sys
import subprocess
import threading
import traceback
import queue
import tkinter as tk
import re
from tkinter import scrolledtext
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
import win32event
import win32api


class VoiceDictationTray:
    """System tray wrapper for vdict.py"""
    
    def __init__(self):
        self.process = None
        self.output_queue = queue.Queue()
        self._exit_reported = False
        
        # Create output window
        self.window = tk.Tk()
        self.window.title("Voice Dictation Output")
        self.window.geometry("900x600")
        
        # Text area with scrollbar
        self.text = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            font=("Consolas", 12),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.text.tag_configure("sys_dim", foreground="#707070") # Map ANSI dim gray
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)
        
        # Create context menu for copying text
        self.context_menu = tk.Menu(self.text, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_text)
        self.text.bind("<Button-3>", self._show_context_menu)
        
        # Make the 'X' close button completely inert
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        
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
        
        # Start thread to read output
        reader_thread = threading.Thread(target=self._read_output, daemon=True)
        reader_thread.start()
    
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
                
                if is_dim:
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
            if self.process and not self._exit_reported:
                exit_code = self.process.poll()
                if exit_code is not None:
                    self._exit_reported = True
                    self.text.config(state=tk.NORMAL)
                    self.text.insert(tk.END, f"\n[vdict.py exited with code {exit_code}]\n")
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
    
    def hide_window(self):
        """Hide output window"""
        self.window.withdraw()
        
    def _on_unmap(self, event):
        """Intercept minimize event to hide to tray"""
        if event.widget == self.window and self.window.state() == 'iconic':
            self.hide_window()
    
    def exit_app(self, icon=None, item=None):
        """Exit application and kill subprocess"""
        print("Stopping vdict.py...")
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.icon.stop()
        try:
            self.window.quit()
        except:
            pass
    
    def run(self):
        """Run the tray application"""
        # Start vdict.py subprocess
        self.start_vdict()
        
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
            print("Voice Dictation is already running")
            sys.exit(1)

        app = VoiceDictationTray()
        app.run()
    except Exception:
        _log_startup_crash()
        raise
