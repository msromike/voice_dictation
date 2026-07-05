"""
Module: keyboard.py
Purpose: Keyboard event injection and PTT button monitoring

Responsibilities:
  - Listen for middle mouse button (or other PTT trigger)
  - Inject transcribed text at cursor position
  - Platform-specific keyboard/mouse event handling
"""

import threading
from pynput import mouse


class PTTListener:
    """Push-to-talk button listener (middle mouse button)"""
    
    def __init__(self, button="middle", debug=False):
        """
        Initialize PTT listener
        
        Args:
            button: Mouse button to monitor ("middle", "side", etc.)
            debug: Print debug messages for all mouse events
        """
        self.button_name = button
        self.pressed = False
        self.debug = debug
        
        # Threading events for blocking waits
        self.press_event = threading.Event()
        self.release_event = threading.Event()
        
        # Map button name to pynput button
        self.button = mouse.Button.middle if button == "middle" else mouse.Button.middle
        
        # Start mouse listener in background thread
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()
        
        if self.debug:
            print(f"[DEBUG] PTTListener started, monitoring: {self.button_name}")
    
    def _on_click(self, x, y, button, pressed):
        """
        Internal callback for mouse events (runs in background thread)
        
        Args:
            x, y: Mouse position (unused)
            button: Mouse button that triggered event
            pressed: True if pressed, False if released
        """
        if self.debug:
            print(f"[DEBUG] Mouse event: button={button}, pressed={pressed}, target={self.button}")
        
        if button == self.button:
            self.pressed = pressed
            if pressed:
                if self.debug:
                    print(f"[DEBUG] Target button PRESSED - setting event")
                self.press_event.set()
                self.release_event.clear()
            else:
                if self.debug:
                    print(f"[DEBUG] Target button RELEASED - setting event")
                self.release_event.set()
                self.press_event.clear()
    
    def wait_for_press(self):
        """
        Block until PTT button is pressed
        
        Returns:
            bool: True when button pressed
        """
        while not self.press_event.wait(timeout=0.1):
            pass  # Loop allows KeyboardInterrupt to be raised
        return True
    
    def wait_for_release(self):
        """Block until PTT button is released"""
        while not self.release_event.wait(timeout=0.1):
            pass  # Loop allows KeyboardInterrupt to be raised
    
    def is_pressed(self):
        """Check if PTT button is currently pressed"""
        return self.pressed
    
    def stop(self):
        """Stop mouse listener (cleanup)"""
        self.listener.stop()


class KeyboardInjector:
    """Text injection at cursor position via clipboard"""
    
    def __init__(self):
        """Initialize keyboard injector"""
        try:
            import pyperclip
            import pyautogui
            import time
            self.pyperclip = pyperclip
            self.pyautogui = pyautogui
            self.time = time
        except ImportError as e:
            raise RuntimeError(f"Missing dependency: {e}. Install: pip install pyperclip pyautogui")
    
    def inject(self, text):
        """
        Inject text at current cursor position
        
        Uses clipboard method with save/restore:
        1. Save current clipboard
        2. Put text in clipboard
        3. Paste (Ctrl+V)
        4. Restore original clipboard after delay
        
        Args:
            text: Text to paste at cursor (space is appended for separation)
        """
        if not text or not text.strip():
            return  # Skip empty text
        
        # Save current clipboard
        try:
            old_clipboard = self.pyperclip.paste()
        except:
            old_clipboard = ""  # Clipboard empty or inaccessible
        
        # Add space after text for separation, then paste
        self.pyperclip.copy(text + " ")
        self.pyautogui.hotkey('ctrl', 'v')
        
        # Wait for paste to complete, then restore clipboard
        self.time.sleep(0.05)  # 50ms delay
        self.pyperclip.copy(old_clipboard)
