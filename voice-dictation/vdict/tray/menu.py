"""The CUA menu bar, plus the Help items it owns outright. Wired -- only app
imports it. Every command that touches the console arrives as a callable."""

import os
import tkinter as tk
import webbrowser
from tkinter import messagebox

from vdict import __version__
from vdict.common import output
from vdict.common.config import (
    VOCABULARY_PATH, VOCABULARY_RESET_MESSAGE, reseed_vocabulary_if_missing)
from vdict.tray.const import PROJECT_URL
from vdict.tray.log import log

# Declared, deliberately unbound. _sync_help_menu only ever fires as the
# postcommand on the menu build() made, so reaching it first is a bug.
_help_menu: tk.Menu


def _sync_help_menu():
    """Grey out Error Log when no log file exists."""
    _help_menu.entryconfig(
        "Error Log",
        state=tk.NORMAL if output.ERROR_LOG_PATH.exists() else tk.DISABLED)


def _open_error_log():
    """Open the error log in the default text editor"""
    os.startfile(output.ERROR_LOG_PATH)


def open_docs(event=None):
    """Open the project page in the default browser.
    Not the local README.md: Windows usually has no .md handler, so it opens raw."""
    webbrowser.open(PROJECT_URL)
    return "break"


def _open_vocabulary():
    """Open vocabulary.txt in the user's default .txt handler.
    Reseeds from the template first if it was deleted -- nothing to validate."""
    if reseed_vocabulary_if_missing():
        log("note", VOCABULARY_RESET_MESSAGE)
    os.startfile(VOCABULARY_PATH)


def _show_about(root):
    """About dialog"""
    messagebox.showinfo(
        "About Voice Dictation",
        f"Voice Dictation v{__version__}\n\n"
        f"Offline push-to-talk dictation using Whisper.\n"
        f"{PROJECT_URL}\n\n"
        f"MIT License",
        parent=root)


def build(root, cb):
    """Build the CUA-style menu bar onto root.
    Mnemonics must stay unique within each menu."""
    global _help_menu
    menubar = tk.Menu(root)

    file_menu = tk.Menu(menubar, tearoff=0)
    # "Save As" takes A rather than S, the convention when Settings
    # already owns S in the same menu.
    file_menu.add_command(label="Save As...", underline=5,
                          command=cb["save_log_as"])
    file_menu.add_command(label="Vocabulary...", underline=0,
                          command=_open_vocabulary)
    file_menu.add_separator()
    file_menu.add_command(label="Settings...", underline=0,
                          command=cb["open_settings"])
    file_menu.add_command(label="Hide to Tray", underline=0,
                          command=cb["hide_window"])
    file_menu.add_separator()
    file_menu.add_command(label="Exit", underline=1, command=cb["exit_app"])
    menubar.add_cascade(label="File", underline=0, menu=file_menu)

    edit_menu = tk.Menu(menubar, tearoff=0)
    edit_menu.add_command(label="Copy", underline=0, accelerator="Ctrl+C",
                          command=cb["copy"])
    edit_menu.add_command(label="Select All", underline=0,
                          accelerator="Ctrl+A", command=cb["select_all"])
    edit_menu.add_command(label="Copy All", underline=5,
                          command=cb["copy_all"])
    edit_menu.add_separator()
    edit_menu.add_command(label="Clear", underline=1, command=cb["clear"])
    menubar.add_cascade(label="Edit", underline=0, menu=edit_menu)

    view_menu = tk.Menu(menubar, tearoff=0)
    view_menu.add_command(label="Zoom In", underline=5,
                          accelerator="Ctrl++",
                          command=lambda: cb["zoom_step"](1))
    view_menu.add_command(label="Zoom Out", underline=5,
                          accelerator="Ctrl+-",
                          command=lambda: cb["zoom_step"](-1))
    view_menu.add_command(label="Reset Zoom", underline=0,
                          accelerator="Ctrl+0", command=cb["reset_font"])
    menubar.add_cascade(label="View", underline=0, menu=view_menu)

    # postcommand fires each time Help opens, so Error Log reflects
    # whether a log actually exists right now.
    help_menu = tk.Menu(menubar, tearoff=0, postcommand=_sync_help_menu)
    help_menu.add_command(label="Documentation", underline=0,
                          accelerator="F1", command=open_docs)
    help_menu.add_command(label="Error Log", underline=0,
                          command=_open_error_log)
    help_menu.add_separator()
    help_menu.add_command(label="About", underline=0,
                          command=lambda: _show_about(root))
    menubar.add_cascade(label="Help", underline=0, menu=help_menu)
    _help_menu = help_menu

    root.config(menu=menubar)
