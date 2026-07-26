"""Vulture false positives. Every entry is required by something vulture cannot see."""

# sounddevice InputStream callback signature -- PortAudio passes all four args.
frames

# pystray invokes MenuItem callbacks as fn(icon, item).
item

# Tk calls this hook itself when a callback raises. We assign, Tk reads.
_.report_callback_exception

# DANGEROUS TO "FIX". The mutex handle must stay referenced for the life of the
# process. Drop the reference and it is garbage-collected, the mutex releases,
# and single-instance detection silently stops working.
mutex
