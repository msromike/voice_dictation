"""Vulture false positives. Every entry is required by something vulture cannot see."""

# sounddevice InputStream callback signature -- PortAudio passes all four args.
frames

# pystray invokes MenuItem callbacks as fn(icon, item).
item

# Tk calls this hook itself when a callback raises. We assign, Tk reads.
_.report_callback_exception

# DANGEROUS TO "FIX". The mutex handle must stay referenced for the process
# lifetime, or it is collected, the mutex releases, and single-instance dies.
mutex

# Pydantic's own metaclass reads this class attribute internally to configure
# the model (e.g. validate_assignment=True) -- never read by our code directly.
model_config

# geometry.py's registry reaches these UiConfig fields by name. Delete both
# lines when the Qt port deletes geometry.py and drops the fields.
settings_pos
console_geometry
