"""The output window: the text widget and everything that reads or writes it.
Wired -- app builds it and registers the fault handlers its dispatch calls."""

import queue
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import filedialog, scrolledtext

from vdict.common import output
from vdict.tray import transcript
from vdict.tray.log import error_log, install_screen, output_queue

# CategorySpec.color -> the Tk tag that renders it. "none" has no entry --
# absent from this map means the widget's default foreground.
COLOR_TAGS = {"dim": "sys_dim", "yellow": "sys_yellow", "red": "sys_red"}

# Console text size, in points. Tk scales points by screen DPI on its own, so
# these never go through scale().
FONT_DEFAULT = 12
FONT_MIN = 7
FONT_MAX = 32

# SWALLOW's first real caller -- no Settings/UI integration yet either.
transcript_only_mode = False


def _swallow_set():
    """Categories currently suppressed from window display."""
    return {"rec", "done"} if transcript_only_mode else set()


class Console:
    """The output window's text widget, its category dispatch, its key bindings."""

    def __init__(self, root, icon, handlers):
        """root owns the window, icon delivers toasts, and handlers maps a
        box category to what app wants raised for it."""
        self.root = root
        self.icon = icon
        self.handlers = handlers
        self.font_size = FONT_DEFAULT
        self._loading = False

        # Monospace is not negotiable: the daemon prints aligned [n] counters and
        # a loading animation whose dots need a consistent advance width.

        # inactiveselectbackground defaults to empty, drawing no selection at
        # all -- and a disabled widget never focuses, so that is its only state.
        self.text = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, font=("Consolas", self.font_size),
            bg="#1e1e1e", fg="#d4d4d4",
            selectbackground="#264f78", inactiveselectbackground="#264f78")
        self.text.tag_configure(
            "sys_dim", foreground="#707070")  # Map ANSI dim gray
        self.text.tag_configure("sys_yellow", foreground="#FFFF00")
        self.text.tag_configure("sys_red", foreground="#FF0000")
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.config(state=tk.DISABLED)

        install_screen(self._write_error)

        self.context_menu = tk.Menu(self.text, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy)
        self.text.bind("<Button-3>", self._show_context_menu)

        # Bound to the window, not the text widget. The widget is disabled and
        # so never takes focus.
        root.bind("<Control-MouseWheel>", self._zoom_wheel)
        root.bind("<Control-Key-0>", self.reset_font)

        # Tk's accelerator= only draws the shortcut text on the menu item; the
        # key itself has to be bound separately or the label is a lie.
        root.bind("<Control-Key-c>", lambda e: self.copy())
        root.bind("<Control-Key-a>", lambda e: self.select_all())
        root.bind("<Control-Key-plus>", lambda e: self.zoom_step(1))
        root.bind("<Control-Key-equal>", lambda e: self.zoom_step(1))
        root.bind("<Control-Key-minus>", lambda e: self.zoom_step(-1))

    def _write_error(self, context, text):
        """error_log's screen half, installed at construction.
        log.py guards the call -- raising here never undoes its disk write."""
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, f"\n{context}\n{text}\n")
        self.text.see(tk.END)
        self.text.config(state=tk.DISABLED)

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

    def copy(self):
        """Copy selected text to clipboard"""
        try:
            self.text.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def select_all(self):
        """Select the entire log"""
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        return "break"

    def copy_all(self):
        """Copy the entire log to the clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.text.get("1.0", tk.END).rstrip("\n"))

    def clear(self):
        """Empty the log"""
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)

    def save_log_as(self):
        """Write the console log to a text file.
        UTF-8 is required: transcripts carry curly quotes and em-dashes."""
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Console Log",
            defaultextension=".txt",
            initialfile="voice_dictation_log_%s.txt"
                        % datetime.now().strftime("%Y-%m-%d"),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return  # User cancelled the dialog
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.text.get("1.0", tk.END).rstrip("\n") + "\n")

    def set_font_size(self, size):
        """Apply a console text size, clamped to a legible range"""
        self.font_size = max(FONT_MIN, min(FONT_MAX, size))
        self.text.config(font=("Consolas", self.font_size))

    def zoom_step(self, direction):
        """Change the console text size by one step"""
        self.set_font_size(self.font_size + direction)
        return "break"

    def _zoom_wheel(self, event):
        """Ctrl+scroll to resize the console text"""
        return self.zoom_step(1 if event.delta > 0 else -1)

    def reset_font(self, event=None):
        """Ctrl+0 to return to the default size"""
        self.set_font_size(FONT_DEFAULT)
        return "break"

    def set_loading(self, loading):
        """Tell the console a model load is running, so the dots animate."""
        self._loading = loading

    def _animate_dots(self):
        """Append gray dots to the console while loading"""
        if self._loading:
            self.text.config(state=tk.NORMAL)
            self.text.insert(tk.END, ".", "sys_dim")
            self.text.see(tk.END)
            self.text.config(state=tk.DISABLED)
            self.root.after(1000, self._animate_dots)

    def drain(self):  # noqa: C901, PLR0912 -- dies with the Qt port, this function goes
        """One pass over whatever's currently queued -- dispatch each item by
        category. Called on the tick, and again from the exit-check gap."""
        try:
            while True:
                category, text = output_queue.get_nowait()
                self.text.config(state=tk.NORMAL)
                spec = output.CATEGORIES[category] if category is not None else None
                tags = (COLOR_TAGS[spec.color],) if spec and spec.color in COLOR_TAGS else ()
                swallow = _swallow_set()

                if self._loading and category != "loading":
                    self.text.insert(tk.END, "\n")
                    if category == "ready":
                        self._loading = False

                if category == "loading":
                    if category not in swallow:
                        self.text.insert(tk.END, text, *tags)
                    self._loading = True
                    self.root.after(1000, self._animate_dots)
                elif category not in swallow:
                    if spec and spec.marker:
                        body = f"[{spec.marker}]" + (f" {text}" if text else "")
                    else:
                        body = text
                    # Blank line only when DONE is swallowed too -- bookended,
                    # the markers already separate consecutive transcripts.
                    trailer = "\n\n" if category == "transcript" and "done" in swallow else "\n"
                    self.text.insert(tk.END, body + trailer, *tags)

                if category == "transcript" and transcript.ENABLED:
                    transcript.write(text)
                    transcript.write("")

                if spec and spec.toast and self.root.state() != 'normal':
                    self.icon.notify(text, "Voice Dictation")

                if spec and spec.box:
                    handler = self.handlers.get(category)
                    if handler:
                        handler(text)

                self.text.see(tk.END)
                self.text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        except Exception:
            error_log("Output update error", traceback.format_exc())
