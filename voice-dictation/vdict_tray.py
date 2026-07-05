#!/usr/bin/env python3
"""Voice Dictation - System Tray Wrapper (Chunk 2b: Capture and display output)"""

import sys
import subprocess
import threading
import queue
import tkinter as tk
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
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)
        
        # Handle window close (hide, don't exit)
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Start hidden
        self.window.withdraw()
        
        self.icon = self.create_tray_icon()
    
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
                self.text.insert(tk.END, line + "\n")
                self.text.see(tk.END)
                self.text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        
        # Schedule next update
        self.window.after(100, self._update_output)
    
    def show_window(self, icon=None, item=None):
        """Show output window"""
        self.window.deiconify()
        self.window.lift()
    
    def hide_window(self):
        """Hide output window"""
        self.window.withdraw()
    
    def exit_app(self, icon=None, item=None):
        """Exit application and kill subprocess"""
        print("Stopping vdict.py...")
        if self.process:
            self.process.terminate()
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


if __name__ == "__main__":
    # Single-instance check using Windows mutex
    mutex = win32event.CreateMutex(None, False, "VoiceDictationTrayMutex")
    if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("Voice Dictation is already running")
        sys.exit(1)
    
    app = VoiceDictationTray()
    app.run()
