"""Make the console streams safe for the app's own messages (v2.8.6).

The packaged Windows app (and any Windows console set to cp1252) cannot print
characters such as ``⚡`` or ``⚠`` — ``UnicodeEncodeError`` killed the start of
the first Windows package.  A windowed app may also have no stdout at all.
``make_stdio_safe()`` switches both streams to UTF-8 that never raises, and
gives a missing stream somewhere to write to.
"""
import os
import sys


def make_stdio_safe() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:                       # windowed app without a console
            try:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
            except OSError:
                pass
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
