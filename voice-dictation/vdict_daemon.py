"""PTT daemon: captures audio on the configured trigger, transcribes, injects at cursor.
Launched by vdict_tray.py, which writes config.json first. Requires it to exist."""

import sys
import threading

# Must precede the imports below -- vdict.daemon.audio is WASAPI-specific and
# the whole app is Windows-only regardless.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

from vdict import __version__
from vdict.daemon.audio import AudioCapture
from vdict.daemon.stt import STTEngine
from vdict.daemon.keyboard import KeyboardInjector, PTTListener
import win32event

from vdict.common.config import RELOAD_EVENT_NAME, load_config, load_vocabulary
from vdict.common.output import log, write_error_log
from vdict.common.audio_io import write_timestamped_flac
from vdict.common.blocks import BlockTracker
from pathlib import Path
import wave
import os
import queue
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


TONE_VOLUME_HIGH = 0.22275
TONE_VOLUME_LOW = 0.18225


def play_tone(tone_type, enabled=True, volume=1.0):
    """Play the requested tone 100% asynchronously. enabled silences every
    tone -- ready still reaches the console line and its tray toast."""
    if not enabled:
        return
    if tone_type in ("timeout", "ready"):
        tone, reference_volume = TONE_LOW_DOUBLE, TONE_VOLUME_LOW
    elif tone_type == "start":
        tone, reference_volume = TONE_HIGH, TONE_VOLUME_HIGH
    elif tone_type == "stop":
        tone, reference_volume = TONE_LOW, TONE_VOLUME_LOW
    elif tone_type == "too_short":
        tone, reference_volume = TONE_LOW_DOUBLE, TONE_VOLUME_LOW
    else:
        return
    scaled = (tone * (reference_volume * volume)).reshape(-1, 1)
    _tone_queue.put(scaled)


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
        # Held from trigger press until the paste lands; the Enter button waits on it.
        self.busy = threading.Lock()
        self.reload_event = win32event.CreateEvent(
            None, False, False, RELOAD_EVENT_NAME)  # pyright: ignore[reportArgumentType]
        self.ptt = self._make_listener(config)
        self.prompt = load_vocabulary()

    def _make_listener(self, config):
        """The trigger listener for this config. Built at start and on every reload."""
        return PTTListener(
            button=config.ptt.button, enter_button=config.ptt.enter_button,
            on_enter=self.blocks.close, on_enter_button=self._enter_button)

    def _reload_if_asked(self):
        """Between captures only. A save that leaves the model alone lands here
        instead of a restart, so the model stays loaded."""
        if win32event.WaitForSingleObject(self.reload_event, 0) != win32event.WAIT_OBJECT_0:
            return
        config = load_config()
        self.ptt.stop()
        self.config = config
        # A missing mic exits here with a mic-fault, the same path as at startup.
        self.audio = AudioCapture(required_device=config.audio.device)
        self.ptt = self._make_listener(config)
        self.prompt = load_vocabulary()

    def _enter_button(self):
        """Hook thread: hand off at once. The Enter waits for an in-flight
        dictation to paste, so it never sends a message without it."""
        threading.Thread(target=self._send_enter, daemon=True).start()

    def _send_enter(self):
        """Fires the moment no dictation is between trigger and paste."""
        with self.busy:
            self.keyboard.press_enter()

    def stop(self):
        """Stop the trigger listener."""
        self.ptt.stop()

    def _capture(self):
        """Record until the trigger releases, or toggle mode times out at 120s.
        Returns (samples, started, ended, timed_out)."""
        feedback = self.config.audio.feedback
        toggle = self.config.ptt.mode == "toggle"
        if toggle:
            self.ptt.wait_for_release()

        # play_tone() doesn't block -- swapping these two calls wouldn't
        # reduce tone bleed into the recording, it would capture the whole tone.
        play_tone("start", enabled=feedback)
        log("rec", "")
        # Stamped before the stream opens, so start_time runs ahead of the first
        # sample -- about 50ms, and about 600ms on the first capture after launch.
        started = datetime.now()
        self.audio.start_capture()

        timed_out = False
        if toggle and not self.ptt.wait_for_press(timeout_secs=120.0):
            timed_out = True
            play_tone("timeout", enabled=feedback)
            log("note", "Timeout reached.")
        else:
            self.ptt.wait_for_release()

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
            play_tone("too_short", enabled=self.config.audio.feedback)
            log("note", "Not transcribed -- hold the button at least 0.4s.")
            return "", "too-short", None

        play_tone("stop", enabled=self.config.audio.feedback)
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
        self.keyboard.inject(text)
        return text, "success", datetime.now()

    def run_once(self):
        """One capture, from trigger to row. Every outcome writes exactly one row."""
        # Wakes every 0.1s to check for saved settings; nothing depends on the period.
        while not self.ptt.wait_for_press(timeout_secs=0.1):
            self._reload_if_asked()

        with self.busy:
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

    # Closes the session block. Dashes, not the startup header's equals signs --
    # this divides sections, it does not open the log. Blank line after.
    log("ready", f"Voice Dictation v{__version__} READY")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("block", f" {timestamp} ".center(60, "-"))
    log("block", "")
    play_tone("ready", enabled=config.audio.feedback)

    try:
        while True:
            session.run_once()
    except KeyboardInterrupt:
        print("\n\n\033[90mStopped\033[0m")
        session.stop()


if __name__ == "__main__":
    main()
