"""PTT daemon: captures audio on the configured trigger, transcribes, injects at cursor.
Launched by vdict_tray.py, which writes config.json first. Requires it to exist."""

import sys
import threading
import time

# Must precede the imports below -- vdict.daemon.audio is WASAPI-specific and
# the whole app is Windows-only regardless.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

from vdict import __version__
from vdict.daemon.audio import AudioCapture
from vdict.daemon.stt import STTEngine
from vdict.daemon.keyboard import KeyboardInjector, PTTListener

from vdict.common.config import load_config, load_vocabulary
from vdict.common.output import divider_line, log, write_error_log
from vdict.common.audio_io import write_timestamped_flac
from vdict.common.blocks import BlockTracker
from pathlib import Path
import os
import queue
import wave
import traceback
from datetime import datetime
from typing import NamedTuple
import numpy as np
import sounddevice as sd
import tomllib
import win32gui
import win32process
import win32api
import win32con

def get_window_context():
    """Return (hwnd, pid, title, process_name) for the foreground window.
    One GetForegroundWindow call -- the row and the block must agree on which window."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return 0, 0, "Unknown", "Unknown"
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, 
                False, pid)
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            process_name = os.path.basename(exe_path)
        except Exception:
            process_name = "Unknown"
            
        return hwnd, pid, title or "Unknown", process_name
    except Exception:
        return 0, 0, "Unknown", "Unknown"

class CaptureRow(NamedTuple):
    """One capture, one row. Field order matches the INSERT below."""

    start_time: datetime
    end_time: datetime
    inject_time: datetime | None
    file_timestamp: str | None
    audio_path: Path | None
    duration_sec: float
    sample_rate: int
    model: str
    compute_device: str
    compute_type: str
    transcript_text: str
    outcome: str
    app_version: str
    mode: str
    window_title: str
    process_name: str
    block_id: int
    speaker: str = ""


def _record_corpus_row(row):
    """Write one CaptureRow. Does nothing when corpus capture is off, and never raises --
    a database fault must not end a dictation session."""
    if not FLAC_CORPUS_CAPTURE_ENABLED:
        return
    try:
        from vdict.common.corpus_db import get_corpus_connection
        conn = get_corpus_connection()
        try:
            conn.execute("""
                INSERT INTO captures (
                    start_time, end_time, inject_time, file_timestamp, audio_path,
                    duration_sec, sample_rate, model, compute_device, compute_type,
                    transcript_text, outcome, app_version, mode, window_title,
                    process_name, block_id, speaker
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.start_time.isoformat(), row.end_time.isoformat(),
                row.inject_time.isoformat() if row.inject_time else "",
                row.file_timestamp or "",
                str(row.audio_path) if row.audio_path else "",
                row.duration_sec, row.sample_rate, row.model,
                row.compute_device, row.compute_type, row.transcript_text,
                row.outcome, row.app_version, row.mode, row.window_title,
                row.process_name, row.block_id, row.speaker
            ))
            conn.commit()
        finally:
            conn.close()
    except Exception as db_e:
        log("error", f"Failed to record capture to database: {db_e}")
        write_error_log("Database write failed", traceback.format_exc())


# 0.4 seconds at 16kHz. Shorter recordings are treated as accidental clicks.
MIN_RECORDING_SAMPLES = 6400

_dev_flags_path = Path(__file__).parent.parent / "dev-flags.toml"
if _dev_flags_path.exists():
    with open(_dev_flags_path, "rb") as _f:
        _dev_flags = tomllib.load(_f)
        FLAC_CORPUS_CAPTURE_ENABLED = _dev_flags.get("capture_corpus", False)
else:
    FLAC_CORPUS_CAPTURE_ENABLED = False

FLAC_CORPUS_DIR = Path(__file__).parent.parent / "userdata" / "voice_recordings_PRIVATE"


def _load_tone(filename):
    """Read a WAV file into (sample_rate, float32 samples -1.0 to 1.0)."""
    with wave.open(filename, "rb") as wav_file:
        rate = wav_file.getframerate()
        raw_bytes = wav_file.readframes(wav_file.getnframes())
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return rate, samples


SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "vdict", "sounds")
_high_rate, TONE_HIGH = _load_tone(os.path.join(SOUNDS_DIR, "high.wav"))
_low_rate, TONE_LOW = _load_tone(os.path.join(SOUNDS_DIR, "low.wav"))
_double_rate, TONE_LOW_DOUBLE = _load_tone(os.path.join(SOUNDS_DIR, "low_double.wav"))
assert _high_rate == _low_rate == _double_rate
TONE_SAMPLE_RATE = _high_rate

_output_stream = None
_tone_queue = queue.Queue()
_current_tone = None
_current_tone_pos = 0


def _output_callback(outdata, frames, _time_info, status):
    """Fills outdata in place -- called by PortAudio's own real-time
    thread whenever it needs more data. Never blocks."""
    global _current_tone, _current_tone_pos
    if status:
        log("note", f"Output stream status: {status}")

    filled = 0
    while filled < frames:
        if _current_tone is None:
            try:
                _current_tone = _tone_queue.get_nowait()
                _current_tone_pos = 0
            except queue.Empty:
                outdata[filled:] = 0.0
                return

        remaining = len(_current_tone) - _current_tone_pos
        take = min(remaining, frames - filled)
        outdata[filled:filled + take] = (
            _current_tone[_current_tone_pos:_current_tone_pos + take])
        _current_tone_pos += take
        filled += take

        if _current_tone_pos >= len(_current_tone):
            _current_tone = None


def _resolve_output_device():
    """WASAPI's own default output endpoint. No retry -- an output device
    disappearing mid-session is not the microphone's recovery problem."""
    wasapi = next(
        (i for i, api in enumerate(sd.query_hostapis())
         if api["name"] == "Windows WASAPI"), None)
    if wasapi is None:
        log("error", "Windows WASAPI audio backend not available.")
        sys.exit(1)
    default_id = sd.query_hostapis(wasapi)["default_output_device"]
    if default_id < 0:
        log("error", "No default WASAPI output device found.")
        sys.exit(1)
    return default_id


# The start beep is the high tone; every other beep is a low one.
_TONES = {
    "start": TONE_HIGH,
    "stop": TONE_LOW,
    "ready": TONE_LOW_DOUBLE,
    "timeout": TONE_LOW_DOUBLE,
    "too_short": TONE_LOW_DOUBLE,
}


def play_tone(tone_type, volume):
    """Play the requested tone 100% asynchronously. volume is a Settings slider, 0-100;
    the tone files peak at 1.0, so 100 never clips."""
    # x^4 spans about 60 dB and reaches silence at 0 by itself -- the power-law
    # volume curve from dr-lex.be/info-stuff/volumecontrols.html.
    if volume:
        _tone_queue.put((_TONES[tone_type] * (volume / 100) ** 4).reshape(-1, 1))


def _read_commands(session):
    """Own thread. One command per line from the tray: "beep <tone> <volume>" plays on
    the dictation stream; "paste" repeats the last dictation; "reload" re-reads config."""
    for line in sys.stdin:
        command, *args = line.split()
        if command == "beep":
            play_tone(args[0], int(args[1]))
        elif command == "paste":
            # Straight to the clipboard thread: it pastes even mid-recording.
            if session.last_text is None:
                log("note", "Nothing dictated yet -- nothing to paste.")
            else:
                session.keyboard.paste_async(session.last_text)
        elif command == "reload":
            session.inbox.put("reload")


class CaptureSession:
    """One push-to-talk cycle's worth of state. Built once, run_once() per capture."""

    def __init__(self, config, audio, stt, keyboard):
        """Own what a capture needs. The caller builds AudioCapture and STTEngine;
        the trigger listener and the block tracker belong to this object."""
        self.config = config
        self.audio = audio
        self.stt = stt
        self.keyboard = keyboard
        self.blocks = BlockTracker()
        # Every wait in the engine is a get on this. The session owns it because
        # the listener is rebuilt on reload and the inbox must outlive it.
        self.inbox = queue.Queue()
        # Enter and reload that arrived mid-dictation, handled once its paste lands.
        self.deferred = []
        self.ptt = self._make_listener(config)
        self.prompt = load_vocabulary()
        # What the paste-last hotkey pastes. Lives as long as this process.
        self.last_text = None

    def _make_listener(self, config):
        """The trigger listener for this config. Built at start and on every reload."""
        return PTTListener(
            button=config.ptt.button, enter_button=config.ptt.enter_button,
            on_enter=self.blocks.close, inbox=self.inbox)

    def _reload(self):
        """Between captures only. A save that leaves the model alone lands here
        instead of a restart, so the model stays loaded."""
        config = load_config()
        self.ptt.stop()
        self.config = config
        # A missing mic exits here with a mic-fault, the same path as at startup.
        self.audio = AudioCapture(required_device=config.audio.device)
        self.ptt = self._make_listener(config)
        self.prompt = load_vocabulary()

    def _await(self, kind, timeout=None):
        """Blocks until kind arrives: True. Enter and reload seen on the way are
        deferred; a stale press or release is dropped. False once timeout runs out."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                item = self.inbox.get(timeout=remaining)
            except queue.Empty:
                return False
            if item == kind:
                return True
            if item in ("enter", "reload"):
                self.deferred.append(item)

    def _handle(self, item):
        """One inbox item. A press whose button is already up again came in during a
        dictation and is dropped, as before; a release on its own is nothing to do."""
        if item == "press":
            if self.ptt.pressed:
                self._dictate()
        elif item == "enter":
            self.keyboard.press_enter()
        elif item == "reload":
            self._reload()

    def _drain_deferred(self):
        """Handles what arrived mid-dictation, in order. Runs after the paste landed --
        inject() returns only once the clipboard thread is done -- so Enter never beats it."""
        items, self.deferred = self.deferred, []
        for item in items:
            self._handle(item)

    def stop(self):
        """Stop the trigger listener."""
        self.ptt.stop()

    def _capture(self):
        """Record until the trigger releases, or toggle mode times out at 120s.
        Returns (samples, started, ended, timed_out)."""
        toggle = self.config.ptt.mode == "toggle"
        if toggle:
            self._await("release")

        # play_tone() doesn't block -- swapping these two calls wouldn't
        # reduce tone bleed into the recording, it would capture the whole tone.
        play_tone("start", self.config.audio.start_volume)
        log("rec", "")
        # Stamped before the stream opens, so start_time runs ahead of the first
        # sample -- about 50ms, and about 600ms on the first capture after launch.
        started = datetime.now()
        self.audio.start_capture()

        timed_out = False
        if toggle and not self._await("press", 120.0):
            timed_out = True
            play_tone("timeout", self.config.audio.stop_volume)
            log("note", "Timeout reached.")
        else:
            self._await("release")

        return self.audio.stop_capture(), started, datetime.now(), timed_out

    def _write_flac(self, audio_data):
        """Write the capture to the corpus directory. (None, None) when capture is off."""
        if not FLAC_CORPUS_CAPTURE_ENABLED:
            return None, None
        return write_timestamped_flac(FLAC_CORPUS_DIR, audio_data, self.audio.sample_rate)

    def _transcribe_and_inject(self, audio_data):
        """Returns (text, outcome, inject_time). Injects only on success."""
        # Short captures can make Whisper hallucinate plausible-but-false
        # text instead of returning empty -- see spike_notes.txt.
        if len(audio_data) < MIN_RECORDING_SAMPLES:
            play_tone("too_short", self.config.audio.stop_volume)
            log("note", "Not transcribed -- hold the button at least 0.4s.")
            return "", "too-short", None

        play_tone("stop", self.config.audio.stop_volume)
        try:
            text = self.stt.transcribe(audio_data, initial_prompt=self.prompt)
        except Exception as e:
            log("error", f"Transcription failed: {e}")
            write_error_log("Transcription failed", traceback.format_exc())
            return "", "error", None

        if not text:
            log("note", "No speech detected.")
            return "", "no-speech", None

        log("transcript", text)
        self.last_text = text
        self.keyboard.inject(text)
        return text, "success", datetime.now()

    def run_once(self):
        """One inbox item. A press is a capture, from trigger to row; Enter and
        reload arriving between captures are handled on the spot."""
        self._handle(self.inbox.get())

    def _dictate(self):
        """One capture, from trigger to row. Every outcome writes exactly one row."""
        hwnd, pid, win_title, proc_name = get_window_context()
        block_id = self.blocks.block_for(hwnd, pid)

        # Fire the GPU primer to wake up CUDA cores while user is talking
        self.stt.wake_gpu()

        audio_data, started, ended, timed_out = self._capture()
        audio_path, file_timestamp = self._write_flac(audio_data)

        text, outcome, inject_time = "", "timeout", None
        if not timed_out:
            text, outcome, inject_time = self._transcribe_and_inject(audio_data)

        _record_corpus_row(CaptureRow(
            start_time=started, end_time=ended, inject_time=inject_time,
            file_timestamp=file_timestamp, audio_path=audio_path,
            duration_sec=len(audio_data) / self.audio.sample_rate,
            sample_rate=self.audio.sample_rate,
            model=self.config.stt.model, compute_device=self.config.stt.device,
            compute_type=self.stt.compute_type, transcript_text=text,
            outcome=outcome, app_version=__version__, mode="dictation",
            window_title=win_title, process_name=proc_name, block_id=block_id))

        log("done", "")
        self._drain_deferred()


def main():
    """Main daemon loop"""
    config = load_config()

    if FLAC_CORPUS_CAPTURE_ENABLED:
        from vdict.common.corpus_db import init_db
        try:
            init_db()
        except Exception as e:
            log("error", f"Failed to initialize corpus database: {e}")

    # Initialize components
    audio = AudioCapture(
        required_device=config.audio.device
    )

    stt = STTEngine(
        model_name=config.stt.model,
        device=config.stt.device
    )

    log("loading", "Loading model")
    stt.load()

    keyboard = KeyboardInjector()

    session = CaptureSession(config, audio, stt, keyboard)

    global _output_stream
    _output_stream = sd.OutputStream(
        samplerate=TONE_SAMPLE_RATE,
        device=_resolve_output_device(),
        channels=1,
        dtype="float32",
        callback=_output_callback,
        extra_settings=sd.WasapiSettings(auto_convert=True))
    _output_stream.start()
    threading.Thread(target=_read_commands, args=(session,), daemon=True).start()

    log("ready", f"Voice Dictation v{__version__} READY")
    log("block", divider_line())
    log("block", "")
    play_tone("ready", config.audio.stop_volume)

    try:
        while True:
            session.run_once()
    except KeyboardInterrupt:
        print("\n\n\033[90mStopped\033[0m")
        session.stop()


if __name__ == "__main__":
    main()
