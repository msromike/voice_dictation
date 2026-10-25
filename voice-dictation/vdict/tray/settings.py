"""The Settings dialog. Wired -- only app imports it. It reads its widgets into
a Config and hands that to on_save; writing, closing and restarting are app's."""

import tkinter as tk
from typing import Literal, cast

from vdict.common.config import HotkeyConfig, load_settings
from vdict.tray import hotkey, hotkey_capture
from vdict.tray.dpi import scale
from vdict.tray.geometry import POS, manage
from vdict.tray.ptt_capture import PTTCapture
from vdict.tray.session import DEVICE_LABELS, format_bind
from vdict import __version__

# config.json audio.device's empty-string value, shown as a real option here.
DEFAULT_MIC_LABEL = "System Default"

# The live dialog, so several entry points cannot stack windows. Private:
# nothing outside this module reaches for it.
_win = None


def close():
    """Destroy the dialog if one is open. app calls this after a save."""
    global _win
    if _win is not None:
        _win.destroy()
        _win = None


def _build_window(root):
    """Toplevel, its frame, and the title banner. Withdrawn until placement is set.
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

    from tkinter import ttk

    # Add a professional banner to stretch the window width and look clean
    title_label = tk.Label(main_frame, text="Voice Dictation Settings",
                           font=("Segoe UI", 12, "bold"))
    title_label.pack(pady=(0, scale(5)))

    separator = ttk.Separator(main_frame, orient='horizontal')
    separator.pack(fill='x', pady=(0, scale(15)))

    return settings_win, main_frame


def _build_microphone_row(parent, config):
    """Label and dropdown for the input device. Returns the picked Tk StringVar."""
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

    tk.Label(parent, text="Microphone:").pack()
    mic_var = tk.StringVar(
        value=saved_mic if saved_mic else DEFAULT_MIC_LABEL)
    tk.OptionMenu(
        parent, mic_var, DEFAULT_MIC_LABEL, *mic_names).pack(
        pady=(0, scale(15)))
    return mic_var


def _build_ptt_row(root, parent, config):
    """Button-trigger picker, Enter-button picker and recording-mode dropdown.
    Returns (button_var, enter_var, mode_var); enter_var is "" when unset."""
    tk.Label(parent, text="PTT Button Trigger:").pack()
    button_var = tk.StringVar(value=config.ptt.button)
    enter_var = tk.StringVar(value=config.ptt.enter_button or "")
    button_display_var = tk.StringVar(value=format_bind(button_var.get()))
    enter_display_var = tk.StringVar(value=format_bind(enter_var.get()))

    bind_btn = tk.Button(
        parent,
        textvariable=button_display_var,
        width=20,
        command=lambda: PTTCapture(
            root, button_var, button_display_var, bind_btn, taken=enter_var).start()
    )
    bind_btn.pack(pady=(0, scale(15)))

    # Swallowed like the trigger and replaced by a real Enter, so a dictation
    # can be sent without reaching for the keyboard.
    tk.Label(parent, text="Mouse Button for Enter:").pack()
    enter_row = tk.Frame(parent)
    enter_row.pack(pady=(0, scale(15)))
    enter_btn = tk.Button(
        enter_row,
        textvariable=enter_display_var,
        width=20,
        command=lambda: PTTCapture(
            root, enter_var, enter_display_var, enter_btn,
            taken=button_var, mouse_only=True).start()
    )
    enter_btn.pack(side=tk.LEFT)

    def clear_enter():
        enter_var.set("")
        enter_display_var.set(format_bind(""))
    tk.Button(enter_row, text="Clear", command=clear_enter).pack(
        side=tk.LEFT, padx=(scale(5), 0))

    tk.Label(parent, text="PTT Recording Mode:").pack()
    mode_var = tk.StringVar(value=config.ptt.mode.capitalize())
    tk.OptionMenu(
        parent, mode_var, "Toggle", "Hold").pack(pady=(0, scale(15)))
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
    tk.Label(parent, text="AI Model Size:").pack()
    ai_model_var = tk.StringVar(value=config.stt.model)
    tk.OptionMenu(parent,
                  ai_model_var,
                  "tiny.en",
                  "base.en",
                  "small.en",
                  "medium.en",
                  "large-v3").pack(pady=(0,
                                         scale(15)))

    tk.Label(parent, text="Compute Device:").pack()
    device_var = tk.StringVar(value=DEVICE_LABELS[config.stt.device])

    dev_menu = tk.OptionMenu(parent, device_var, "CPU", "GPU (CUDA)")
    if not _has_cuda():
        # Hardware Fallback: Disable GPU option if no CUDA device exists
        dev_menu["menu"].entryconfigure("GPU (CUDA)", state="disabled")
        if device_var.get() == "GPU (CUDA)":
            device_var.set("CPU")
    dev_menu.pack(pady=(0, scale(15)))
    return ai_model_var, device_var


def _build_beeps_row(parent, config, on_beep_volume):
    """Two beep-volume sliders, 0 to 100; 0 is off. Returns (start_var, stop_var).
    The start beep is the high tone, every other beep the low one."""
    start_var = tk.IntVar(value=config.audio.start_volume)
    stop_var = tk.IntVar(value=config.audio.stop_volume)
    for text, tone, var in (("Start Beep Volume:", "start", start_var),
                            ("Stop & Alert Beep Volume:", "stop", stop_var)):
        tk.Label(parent, text=text).pack()
        slider = tk.Scale(parent, from_=0, to=100, orient=tk.HORIZONTAL,
                          variable=var, length=scale(200))
        slider.pack(pady=(0, scale(10)))
        # Letting go saves the level and plays it -- live like a fader, no Save needed.
        slider.bind("<ButtonRelease-1>",
                    lambda _e, t=tone, v=var: on_beep_volume(t, v.get()))
    return start_var, stop_var


def _build_console_boot_row(parent, config):
    """"Show output window on startup" checkbox. Returns the Tk BooleanVar."""
    open_console_var = tk.BooleanVar(value=config.ui.open_console_on_boot)
    tk.Checkbutton(
        parent, text="Show Output Window on Startup", variable=open_console_var).pack(
        pady=(0, scale(15)))
    return open_console_var


def _build_hotkey_rows(parent):
    """Label and picker for each global hotkey. Returns the two mutable bindings the
    captures write into and Save reads back: (output window, paste last)."""
    cfg, _ = load_settings()
    window = cfg.hotkey.model_dump()
    paste = cfg.paste_hotkey.model_dump()

    for label, binding, taken, verb in (
            ("Output Window Hotkey:", window, paste, "raise this window"),
            ("Paste Last Dictation Hotkey:", paste, window,
             "paste your last dictation")):
        tk.Label(parent, text=label).pack()
        display = tk.StringVar(value=binding["name"] or "None")
        btn = tk.Button(parent, textvariable=display, width=20)
        btn.config(command=lambda b=btn, d=display, bd=binding, t=taken, v=verb:
                   hotkey_capture.capture(b, d, bd, t, v))
        btn.pack(pady=(0, scale(15)))
    return window, paste


def _rebind_on_close(event, settings_win, register_hotkeys):
    """Settings is gone -- put both hotkeys back from whatever is on disk now.
    Saved or abandoned, disk already holds the right answer."""
    # <Destroy> fires for every descendant; the guard keeps this to one call.
    if event.widget is not settings_win:
        return
    # Silent. A Save reprints the session block anyway, and closing
    # without saving changed nothing on disk to announce.
    cfg, _ = load_settings()
    hotkey.unregister_all()
    register_hotkeys(cfg)


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

    mic_var = _build_microphone_row(main_frame, config)
    button_var, enter_var, mode_var = _build_ptt_row(
        root, main_frame, config)
    ai_model_var, device_var = _build_model_row(main_frame, config)
    start_volume_var, stop_volume_var = _build_beeps_row(
        main_frame, config, on_beep_volume)
    open_console_var = _build_console_boot_row(main_frame, config)
    hotkey_binding, paste_binding = _build_hotkey_rows(main_frame)

    def save():
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
    tk.Button(main_frame, text="Save", command=save).pack(
        pady=(scale(5), 0))

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
