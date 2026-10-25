"""One push-to-talk rebind, driven by global pynput hooks.
Leaf -- imports no vdict.tray module beyond log."""

import traceback
from tkinter import messagebox

from vdict.tray.log import error_log, log


def _same_button(a, b):
    """config.json spells mouse x2 two ways."""
    return {"side": "x2"}.get(a, a) == {"side": "x2"}.get(b, b)


class PTTCapture:
    """One push-to-talk rebind. Every exit routes through end(), the only place
    the button is re-enabled and the global hooks are dropped."""

    def __init__(self, root, btn_var, disp_var, tk_btn, *, taken, mouse_only=False):
        """Hold the widgets the capture writes back into, and the face to restore.
        taken is the other row's binding, which this one may not duplicate."""
        self.root = root
        self.btn_var = btn_var
        self.disp_var = disp_var
        self.tk_btn = tk_btn
        self.taken = taken
        self.mouse_only = mouse_only
        self.previous = disp_var.get()
        self.listeners = []
        self.done = False

    def start(self):
        """Disable the button and listen for one key or mouse press.
        pynput is deferred here, off the tray's startup path."""
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
        if _same_button(val, self.taken.get()):
            messagebox.showwarning(
                "Already bound", "That is already bound to the other row.",
                parent=self.tk_btn.winfo_toplevel())
            self.end(self.previous)
            return
        self.btn_var.set(val)
        self.end(disp)

    def failed(self, text):
        """Nothing about the key was usable. All three surfaces say so."""
        if self.done:
            return
        # The line below is the sentence; the traceback stays on disk.
        error_log("PTT rebind", text, screen=False)
        log("error", "Could not bind that key.")
        self.end(self.previous)

    def _on_key(self, key):
        """pynput thread. Marshals to Tk rather than touching widgets here."""
        try:
            name = getattr(key, "name", None)
            if name == "esc":
                # Cancels. Settings closes on Escape too, from its own binding.
                self.root.after(0, lambda: self.end(self.previous))
                return False
            if self.mouse_only:
                return None  # a keyboard already has an Enter key
            if name is None:
                val, disp = f"key:{key.char}", key.char.upper()
            else:
                val, disp = f"key:{name}", name.replace("_", " ").title()
            self.root.after(0, lambda: self.accept(val, disp))
        except Exception:
            # Format now, inside the except block -- sys.exc_info() is gone
            # by the time the deferred call below actually runs.
            text = traceback.format_exc()
            self.root.after(0, lambda t=text: self.failed(t))
        return False

    def _on_click(self, x, y, button, pressed):
        """Only BUTTON_MAP binds; anything else is ignored and the capture stays
        open. Left especially -- it is how the dialog itself is operated."""
        try:
            # Deferred for the same reason as start()'s pynput import.
            from vdict.daemon.keyboard import BUTTON_MAP

            if not pressed or button.name not in BUTTON_MAP:
                return None
            disp = (f"Mouse Side ({button.name.upper()})"
                    if button.name in ("x1", "x2")
                    else f"Mouse {button.name.capitalize()}")
            self.root.after(0, lambda: self.accept(button.name, disp))
        except Exception:
            # Format now, inside the except block -- sys.exc_info() is gone
            # by the time the deferred call below actually runs.
            text = traceback.format_exc()
            self.root.after(0, lambda t=text: self.failed(t))
        return False
