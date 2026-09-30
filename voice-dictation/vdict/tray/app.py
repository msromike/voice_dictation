"""The orchestrator: the Tk root, the wiring, the tick, and shutdown.
Wired -- the only module that imports a wired module."""

import threading
import tkinter as tk
import traceback
from tkinter import messagebox

import ctypes
import win32gui

from vdict.common import output
from vdict.common.config import (
    VOCABULARY_RESET_MESSAGE, load_settings, reseed_vocabulary_if_missing,
    save_settings)
from vdict.tray import daemon_proc, faults, hotkey, icon, menu, settings
from vdict.tray.console import Console
from vdict.tray.const import (
    ICON_PATH, MB_ICONERROR, MIC_FAULT_FLAG_PATH, PROJECT_URL)
from vdict.tray.dpi import scale
from vdict.tray.geometry import GEOMETRY, manage, save_all, set_flush
from vdict.tray.log import error_log, log
from vdict.tray.session import log_session_block


class App:
    """System tray wrapper for vdict_daemon.py"""

    def __init__(self):

        # Create output window
        self.window = tk.Tk()
        self.window.title("Voice Dictation Output")
        self.window.iconbitmap(str(ICON_PATH))
        main_w, main_h = scale(900), scale(600)
        self.window.geometry(f"{main_w}x{main_h}")

        # Icon first: the console needs it to raise toasts.
        self.icon = icon.create(self.show_window, self.open_settings,
                                self.exit_app)
        faults.install(self.window, self.open_settings, self._force_quit,
                       daemon_proc.set_fault_shown)
        self.console = Console(self.window, self.icon, {
            "mic-fault": faults.show_mic_fault,
            "model-fault": faults.show_model_fault})
        daemon_proc.install(self.console.set_loading, self.console.drain)

        menu.build(self.window, {
            "save_log_as": self.console.save_log_as,
            "open_settings": self.open_settings,
            "hide_window": self.hide_window,
            "exit_app": self.exit_app,
            "copy": self.console.copy,
            "select_all": self.console.select_all,
            "copy_all": self.console.copy_all,
            "clear": self.console.clear,
            "zoom_step": self.console.zoom_step,
            "reset_font": self.console.reset_font})

        # Map the 'X' close button to completely exit the app
        self.window.protocol("WM_DELETE_WINDOW", self.exit_app)

        # Intercept the '_' minimize button to hide to tray
        self.window.bind("<Unmap>", self._on_unmap)

        set_flush(self._save_state)
        self.window.bind("<F1>", menu.open_docs)

        # Start hidden
        self.window.withdraw()

        # Tk routes callback exceptions here, and its default prints to stderr,
        # which goes nowhere under pythonw.exe.
        self.window.report_callback_exception = self._report_callback_exception

    def _report_callback_exception(self, exc_type, exc_value, exc_tb):
        """Log a Tkinter callback error, then exit -- something inside Tk's own
        callback dispatch already failed, so Tk itself could be broken too."""
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        error_log("Tk callback", text)

        summary = f"{exc_type.__name__}: {exc_value}"
        if len(summary) > 120:  # display truncation, not a contract
            summary = summary[:117] + "..."

        # Native, not messagebox.showerror -- a Tk-based modal risks failing
        # recursively in exactly the case this handler exists to report.
        try:
            ctypes.windll.user32.MessageBoxW(
                None, f"{summary}\n\nDetails written to {output.ERROR_LOG_PATH}",
                "Voice Dictation error", MB_ICONERROR)
        except Exception:
            pass

        self._force_quit()

    def _tick(self):
        """One 100ms pass: drain the console, then check the subprocess.
        Core-arch deletes the second call and this becomes console-only."""
        self.console.drain()
        daemon_proc.poll()
        self.window.after(100, self._tick)

    def _log_session_block(self, pid):
        """What daemon_proc calls once the subprocess is up. Hotkey state and
        config are app's, so the subprocess never learns about either."""
        config, _ = load_settings()
        log_session_block(pid, config, self.hotkey_name, self.hotkey_failed)

    def show_window(self, icon=None, item=None):
        """Show output window"""
        self.window.deiconify()
        self.window.lift()

    def open_settings(self, icon=None, item=None):
        """Open the Settings dialog. Signature keeps icon/item for pystray."""
        return settings.open_settings(self.window, self._on_settings_save,
                                      self._register_hotkey)

    def _on_settings_save(self, config):
        """What Settings hands back. The dialog reads its widgets and stops --
        writing, closing and restarting are all here."""
        save_settings(config)
        settings.close()
        daemon_proc.restart(self._log_session_block)

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
        log("note", f"{self.hotkey_name} raised the output window")

    def _save_state(self):
        """Persist every tracked window's geometry and the console's text size.
        Flushed at hide, at exit, and when a tracked window is destroyed."""
        config, _ = load_settings()
        save_all(config)
        config.ui.console_font_size = self.console.font_size
        save_settings(config)

    def hide_window(self):
        """Hide output window"""
        self._save_state()
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

    def _run_shutdown_steps(self):
        """Best-effort housekeeping before exit -- one failure never blocks
        the rest (toast, disk, console each try); returns whether anything failed."""
        steps = (
            (self._save_state,
             "Console position/size/font not saved -- next launch uses the "
             "last saved state."),
            (daemon_proc.stop,
             "Daemon may still be running -- check Task Manager for an "
             "orphaned vdict_daemon.py process."),
            (self.icon.stop,
             "Tray icon may linger in the notification area until Explorer "
             "refreshes."))
        any_failed = False
        for step, meaning in steps:
            try:
                step()
            except Exception:
                any_failed = True
                # The line below is the sentence; the traceback stays on disk.
                error_log("Shutdown step", traceback.format_exc(), screen=False)
                try:
                    log("error", f"{step.__name__}: {meaning}")
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
        # run before the daemon starts, because it reads config.json itself.
        config, reset_reason = load_settings()

        # Seeds vocabulary.txt from the tracked template when absent -- same
        # ordering reason. Logging is deferred below, under the banner too.
        vocabulary_reseeded = reseed_vocabulary_if_missing()

        # Nothing saved leaves __init__'s default size in place.
        manage(self.window, config, "console_geometry", GEOMETRY)

        self.console.set_font_size(config.ui.console_font_size)

        # Startup header. Once per app launch -- the daemon start must never print
        # it, since a restart re-greeting the user reads as a wiped log.
        log("header", "=" * 60)
        log("header", " Welcome to Voice Dictation")
        log("header", f" {PROJECT_URL} | MIT License")
        log("header", "=" * 60)

        # Before the daemon starts, so the session block has a true Hotkey line.
        self._register_hotkey(config.hotkey)
        if MIC_FAULT_FLAG_PATH.exists():
            reason = MIC_FAULT_FLAG_PATH.read_text()
            MIC_FAULT_FLAG_PATH.unlink()
            log("note", f"Settings reopened -- {reason}")
            self.open_settings()
        else:
            daemon_proc.start(self._log_session_block)

        # Queued after the daemon start, which already queued the session block
        # itself -- these land after both, not right under the banner.
        if vocabulary_reseeded:
            log("note", VOCABULARY_RESET_MESSAGE)
        if reset_reason:
            for line in reset_reason:
                log("note", line)
            log("note", "Config Reset. Open Settings from the tray icon to "
                              "reconfigure.")
            log("block", "")

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
        self.window.after(100, self._tick)

        # Run tray icon in background thread
        icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        icon_thread.start()

        # Run tkinter mainloop in main thread
        self.window.mainloop()
