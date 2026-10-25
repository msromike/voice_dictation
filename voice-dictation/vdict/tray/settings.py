"""The Settings dialog. Wired -- only app imports it. It reads its widgets into
a Config and hands that to on_save; writing, closing and restarting are app's."""

import tkinter as tk
import winsound
from pathlib import Path
from tkinter import messagebox
from typing import Literal, cast

from vdict.common.config import HotkeyConfig, load_settings
from vdict.tray import hotkey, hotkey_capture
from vdict.tray.dpi import scale
from vdict.tray.geometry import POS, manage
from vdict.tray.log import log
from vdict.tray.ptt_capture import PTTCapture
from vdict.tray.session import DEVICE_LABELS, format_bind
from vdict import __version__

# The daemon's alert beep, played here when there is no daemon to play it.
ALERT_BEEP_PATH = Path(__file__).parent.parent / "sounds" / "low_double.wav"

# config.json audio.device's empty-string value, shown as a real option here.
DEFAULT_MIC_LABEL = "System Default"

# The live dialog, so several entry points cannot stack windows. Private:
# nothing outside this module reaches for it.
_win = None

# The PTT button's blank spacer image. Tk holds no Python reference to an
# image, so without this one it is collected and the spacer vanishes.
_arrow_space = None


def close():
    """Destroy the dialog if one is open. app calls this after a save."""
    global _win
    if _win is not None:
        _win.destroy()
        _win = None


def _build_window(root):
    """Toplevel and its frame. Withdrawn until placement is set.
    Returns (settings_win, main_frame)."""
    settings_win = tk.Toplevel(root)
    settings_win.withdraw()  # Hide immediately to prevent position flash
    settings_win.title("Settings")
    settings_win.resizable(False, False)
    settings_win.attributes("-topmost", True)

    # Create an inner frame for clean, scaled outer padding
    main_frame = tk.Frame(
        settings_win, padx=scale(20), pady=scale(10))
    main_frame.pack(fill=tk.BOTH, expand=True)
    return settings_win, main_frame


def _section(parent, title):
    """A titled box whose rows put the label left of its control."""
    box = tk.LabelFrame(parent, text=title, padx=scale(10), pady=scale(2))
    box.pack(fill=tk.X, pady=(0, scale(6)))
    _columns(box)
    return box


def _columns(frame):
    """One label width and one control width in every box, so all controls match.
    Column 2 holds the Clear and Reset buttons, one width for both."""
    frame.grid_columnconfigure(0, minsize=scale(160))
    frame.grid_columnconfigure(1, minsize=scale(125))
    frame.grid_columnconfigure(2, minsize=scale(40))


def _row(section, text, widget, label_sticky="w"):
    """Grid text and widget as the section's next row. Returns the row index."""
    row = section.grid_size()[1]
    tk.Label(section, text=text).grid(
        row=row, column=0, sticky=label_sticky, padx=(0, scale(10)), pady=scale(1))
    widget.grid(row=row, column=1, sticky="ew", pady=scale(1))
    return row


def _build_microphone_row(parent, config):
    """Dropdown for the input device. Returns the picked Tk StringVar."""
    import sounddevice as sd

    # Enumerate WASAPI only. The legacy PortAudio backends list each mic
    # again, add default-device aliases, and truncate names to 31 chars.
    wasapi = next((i for i, api in enumerate(sd.query_hostapis())
                   if api['name'] == 'Windows WASAPI'), None)
    if wasapi is None:
        raise RuntimeError(
            "Windows WASAPI audio backend not available. The sounddevice "
            "install is incomplete -- rerun vdict_install.bat.")

    mic_names = [dev['name'] for dev in sd.query_devices()
                 if dev['hostapi'] == wasapi
                 and dev['max_input_channels'] > 0]

    saved_mic = config.audio.device
    # Keep a configured-but-currently-absent device (unplugged headset) in
    # the list rather than silently snapping to something else.
    if saved_mic and saved_mic not in mic_names:
        mic_names.append(saved_mic)

    mic_var = tk.StringVar(
        value=saved_mic if saved_mic else DEFAULT_MIC_LABEL)
    _row(parent, "Microphone:",
         tk.OptionMenu(parent, mic_var, DEFAULT_MIC_LABEL, *mic_names))
    return mic_var


def _build_ptt_rows(root, recording, shortcuts, config):
    """PTT button and mode go in recording, the Enter button in shortcuts.
    Returns (button_var, enter_var, mode_var); enter_var is "" when unset."""
    button_var = tk.StringVar(value=config.ptt.button)
    enter_var = tk.StringVar(value=config.ptt.enter_button or "")
    button_display_var = tk.StringVar(value=format_bind(button_var.get()))
    enter_display_var = tk.StringVar(value=format_bind(enter_var.get()))

    mode_var = tk.StringVar(value=config.ptt.mode.capitalize())
    _row(recording, "PTT mode:",
         tk.OptionMenu(recording, mode_var, "Toggle", "Hold"))

    # A blank image where a dropdown's arrow would be, so the text centers
    # under the PTT mode dropdown's text.
    global _arrow_space
    _arrow_space = tk.PhotoImage(width=scale(27), height=1)
    bind_btn = tk.Button(
        recording,
        textvariable=button_display_var,
        image=_arrow_space,
        compound=tk.RIGHT,
        command=lambda: PTTCapture(
            root, button_var, button_display_var, bind_btn, taken=enter_var).start()
    )
    row = _row(recording, "PTT button:", bind_btn)

    # Safe to clear: Save refuses an empty PTT button.
    def clear_ptt():
        button_var.set("")
        button_display_var.set(format_bind(""))
    tk.Button(recording, text="Clear", command=clear_ptt).grid(
        row=row, column=2, sticky="ew", padx=(scale(5), 0))

    # Swallowed like the trigger and replaced by a real Enter, so a dictation
    # can be sent without reaching for the keyboard.
    enter_btn = tk.Button(
        shortcuts,
        textvariable=enter_display_var,
        command=lambda: PTTCapture(
            root, enter_var, enter_display_var, enter_btn,
            taken=button_var, mouse_only=True).start()
    )
    row = _row(shortcuts, "Mouse button for Enter:", enter_btn)

    def clear_enter():
        enter_var.set("")
        enter_display_var.set(format_bind(""))
    tk.Button(shortcuts, text="Clear", command=clear_enter).grid(
        row=row, column=2, sticky="ew", padx=(scale(5), 0))
    return button_var, enter_var, mode_var


def _has_cuda():
    """Whether ctranslate2 can see a CUDA device, with nvidia's DLLs on PATH.
    ctranslate2 stays imported here -- it is heavy and tray startup must not pay."""
    try:
        import glob
        import os
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


def _build_model_row(parent, config):
    """Model-size and compute-device pickers. Returns (ai_model_var, device_var)."""
    device_var = tk.StringVar(value=DEVICE_LABELS[config.stt.device])

    dev_menu = tk.OptionMenu(parent, device_var, "CPU", "GPU (CUDA)")
    if not _has_cuda():
        # Hardware Fallback: Disable GPU option if no CUDA device exists
        dev_menu["menu"].entryconfigure("GPU (CUDA)", state="disabled")
        if device_var.get() == "GPU (CUDA)":
            device_var.set("CPU")
    _row(parent, "Compute device:", dev_menu)

    ai_model_var = tk.StringVar(value=config.stt.model)
    _row(parent, "Model size:",
         tk.OptionMenu(parent,
                       ai_model_var,
                       "tiny.en",
                       "base.en",
                       "small.en",
                       "medium.en",
                       "large-v3"))
    return ai_model_var, device_var


def _build_beeps_row(parent, config, on_beep_volume):
    """Two beep-volume sliders, 0 to 100; 0 is off. Returns (start_var, stop_var).
    The start beep is the high tone, every other beep the low one."""
    start_var = tk.IntVar(value=config.audio.start_volume)
    stop_var = tk.IntVar(value=config.audio.stop_volume)
    for text, tone, var in (("Start beep volume:", "start", start_var),
                            ("Stop & alert beep volume:", "stop", stop_var)):
        slider = tk.Scale(parent, from_=0, to=100, orient=tk.HORIZONTAL,
                          variable=var)
        # Tk draws the number above the bar; the label sits down with the bar.
        _row(parent, text, slider, label_sticky="sw")
        # Letting go saves the level and plays it -- live like a fader, no Save needed.
        slider.bind("<ButtonRelease-1>",
                    lambda _e, t=tone, v=var: on_beep_volume(t, v.get()))
    return start_var, stop_var


def _build_console_boot_row(parent, config):
    """"Show output window on startup" checkbox. Returns the Tk BooleanVar."""
    open_console_var = tk.BooleanVar(value=config.ui.open_console_on_boot)
    tk.Checkbutton(
        parent, text="Show output window on startup", variable=open_console_var).grid(
        row=parent.grid_size()[1], column=0, columnspan=2, sticky="w", pady=scale(1))
    return open_console_var


def _build_hotkey_rows(parent):
    """Picker for each global hotkey. Returns the two mutable bindings the
    captures write into and Save reads back: (output window, paste last)."""
    cfg, _ = load_settings()
    window = cfg.hotkey.model_dump()
    paste = cfg.paste_hotkey.model_dump()

    for label, binding, taken, verb in (
            ("Paste last dictation:", paste, window,
             "paste your last dictation"),
            ("Raise output window:", window, paste, "raise this window")):
        display = tk.StringVar(value=binding["name"] or "None")
        btn = tk.Button(parent, textvariable=display)
        btn.config(command=lambda b=btn, d=display, bd=binding, t=taken, v=verb:
                   hotkey_capture.capture(b, d, bd, t, v))
        row = _row(parent, label, btn)
        # Unset is the shipped state, so Save writes it like any other binding.
        tk.Button(parent, text="Clear",
                  command=lambda d=display, bd=binding: (
                      bd.update(modifiers=None, vk=None, name=None), d.set("None"))
                  ).grid(row=row, column=2, sticky="ew", padx=(scale(5), 0))
    return window, paste


def _rebind_on_close(event, settings_win, register_hotkeys):
    """Settings is gone -- put both hotkeys back from whatever is on disk now.
    Saved or abandoned, disk already holds the right answer."""
    # <Destroy> fires for every descendant; the guard keeps this to one call.
    if event.widget is not settings_win:
        return
    # A Save reprints the session block anyway, and closing without saving
    # changed nothing on disk to announce -- unless that leaves no way to dictate.
    cfg, _ = load_settings()
    hotkey.unregister_all()
    register_hotkeys(cfg)
    if not cfg.ptt.button:
        log("note", "Settings closed with no PTT button -- dictation is off until you "
                    "choose one in Settings.")
        # Full file volume: with no daemon, the beep sliders have nothing to scale.
        winsound.PlaySound(str(ALERT_BEEP_PATH), winsound.SND_FILENAME | winsound.SND_ASYNC)


def open_settings(root, on_save, register_hotkeys, on_beep_volume):
    """Open the dialog, or raise the one already open and return it. on_save(config)
    owns writing and closing; on_beep_volume(tone, volume) saves one slider live."""
    global _win
    # Several independent paths reach this -- the tray menu, the first-run
    # tutorial, and missing-microphone recovery -- so never stack windows.
    if _win is not None:
        try:
            if _win.winfo_exists():
                _win.lift()
                return _win
        except tk.TclError:
            pass  # Widget already torn down; fall through and rebuild

    settings_win, main_frame = _build_window(root)
    _win = settings_win

    config, _ = load_settings()

    recording, engine, shortcuts, sounds = [
        _section(main_frame, title) for title in
        ("Recording", "Speech engine", "Shortcuts", "Sounds and startup")]

    mic_var = _build_microphone_row(recording, config)
    button_var, enter_var, mode_var = _build_ptt_rows(
        root, recording, shortcuts, config)
    ai_model_var, device_var = _build_model_row(engine, config)
    hotkey_binding, paste_binding = _build_hotkey_rows(shortcuts)
    start_volume_var, stop_volume_var = _build_beeps_row(
        sounds, config, on_beep_volume)
    open_console_var = _build_console_boot_row(sounds, config)

    def save():
        # Capturing the button is what proves this machine has it, so there is
        # no default to fall back on -- the person picks one before anything runs.
        if not button_var.get():
            messagebox.showinfo(
                "Choose your PTT button",
                "Pick the button you will hold while you talk.\n\n"
                "Click the PTT button box, then press the key or mouse "
                "button you want.",
                parent=settings_win)
            return

        # The console writes geometry and font to this file while Settings is
        # open -- re-read, never stamp onto the dialog's own copy.
        fresh, _ = load_settings()

        mic = mic_var.get()
        fresh.audio.device = "" if mic == DEFAULT_MIC_LABEL else mic
        fresh.ptt.button = button_var.get()
        fresh.ptt.enter_button = enter_var.get() or None
        fresh.ptt.mode = cast(Literal["hold", "toggle"], mode_var.get().lower())
        fresh.audio.start_volume = start_volume_var.get()
        fresh.audio.stop_volume = stop_volume_var.get()
        fresh.stt.model = ai_model_var.get()
        reverse_device_mapping = {v: k for k, v in DEVICE_LABELS.items()}
        fresh.stt.device = cast(
            Literal["cpu", "cuda"], reverse_device_mapping[device_var.get()])
        fresh.hotkey = HotkeyConfig(**hotkey_binding)
        fresh.paste_hotkey = HotkeyConfig(**paste_binding)

        fresh.ui.open_console_on_boot = open_console_var.get()

        # Reads its widgets and stops. app writes, closes and restarts.
        on_save(fresh)

    # Position is the registry's now, flushed at hide and exit -- closing
    # this dialog writes nothing of its own.
    settings_win.protocol("WM_DELETE_WINDOW", settings_win.destroy)
    # A hotkey capture returns "break" and this never fires; a PTT capture is a
    # pynput hook that cannot, so this fires and its done guard absorbs it.
    settings_win.bind("<Escape>", lambda e: settings_win.destroy())
    # <Destroy>, not the close protocol: a save destroys directly, and
    # destroy() never fires the WM_DELETE_WINDOW handler.
    settings_win.bind("<Destroy>",
                      lambda e: _rebind_on_close(e, settings_win, register_hotkeys),
                      add="+")
    # Same columns as the boxes, so Save sits under the controls at their width.
    save_row = tk.Frame(main_frame, padx=scale(10), bd=2)
    save_row.pack(fill=tk.X, pady=(scale(4), 0))
    _columns(save_row)
    tk.Button(save_row, text="Save", command=save).grid(
        row=0, column=1, sticky="ew", ipady=scale(3))

    # Tk already scales point sizes by DPI. Do not pass this through scale().
    version_label = tk.Label(main_frame, text=f"v{__version__}", fg="gray", font=("Arial", 7))
    version_label.pack(side=tk.BOTTOM, anchor="e")

    # Force Tkinter to calculate required layout dimensions
    settings_win.update_idletasks()

    if not manage(settings_win, config, "settings_pos", POS):
        # Never opened before: bottom right, clear of the taskbar.
        x = (settings_win.winfo_screenwidth()
             - settings_win.winfo_reqwidth() - scale(20))
        y = (settings_win.winfo_screenheight()
             - settings_win.winfo_reqheight() - scale(60))
        settings_win.geometry(f"+{x}+{y}")

    settings_win.deiconify()  # Show the window at the correct position
    settings_win.update_idletasks()
    settings_win.attributes("-topmost", False)
    settings_win.focus_force()
    return settings_win
