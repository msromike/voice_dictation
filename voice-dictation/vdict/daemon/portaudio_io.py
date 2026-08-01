"""The one place that touches sounddevice directly. reinit() must be called
from the thread that first imported this module -- COM apartment affinity."""

import sounddevice as sd


def _wasapi_index():
    for i, api in enumerate(sd.query_hostapis()):
        if api["name"] == "Windows WASAPI":
            return i
    return None


def reinit():
    """Tear down and reinitialize PortAudio in place."""
    sd._terminate()
    sd._initialize()


def enumerate_inputs():
    """Return [(index, name), ...] for current WASAPI input devices."""
    wasapi = _wasapi_index()
    if wasapi is None:
        return []
    return [
        (idx, d["name"])
        for idx, d in enumerate(sd.query_devices())
        if d["hostapi"] == wasapi and d["max_input_channels"] > 0
    ]


def resolve_by_name(name):
    """Return (index, device_name) for the exact WASAPI input match, or
    None. Exact, not substring -- the caller always saves the full name."""
    for idx, device_name in enumerate_inputs():
        if name == device_name:
            return idx, device_name
    return None


def open_probe(device_id):
    """Open, start and immediately close a stream on device_id. Raises on
    failure."""
    stream = sd.InputStream(
        device=device_id,
        samplerate=16000,
        channels=1,
        dtype="float32",
        extra_settings=sd.WasapiSettings(auto_convert=True),
    )
    stream.start()
    stream.stop()
    stream.close()


def start_hold(device_id, on_status=None):
    """Open and start a stream on device_id; caller stops it later via
    stop_hold(). on_status gets any non-empty callback status, live."""

    def callback(indata, frames, time_info, status):
        if status and on_status:
            on_status(status)

    stream = sd.InputStream(
        device=device_id,
        samplerate=16000,
        channels=1,
        dtype="float32",
        callback=callback,
        extra_settings=sd.WasapiSettings(auto_convert=True),
    )
    stream.start()
    return stream


def stop_hold(stream):
    """Read final state, then stop and close. Returns (exception_or_None,
    stream.active just before stopping)."""
    active = stream.active
    error = None
    try:
        stream.stop()
        stream.close()
    except Exception as e:
        error = e
    return error, active
