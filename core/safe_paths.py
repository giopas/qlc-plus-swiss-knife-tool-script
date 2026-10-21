"""core/safe_paths.py — limits for the few routes that write to a path the page names (3.9.7).

Swiss Knife writes a new ``_vN.qxw`` and never overwrites a show (principle 1), but a few
side files are saved where the user chose: the setlist text files.  The Origin and Host checks
in ``app.py`` keep other web pages from calling those routes; this is the second lock: a text
export can only be a text file, so a request can never replace a program, a script, a
settings file or a show.
"""
import os
from typing import Iterable

TEXT_EXTS = (".txt", ".csv", ".tsv", ".md", ".text")


class UnsafePath(ValueError):
    """The path is not somewhere a text export may be written."""


def check_text_save_path(path: str, exts: Iterable[str] = TEXT_EXTS) -> str:
    """The absolute path, if a text file may be written there; else :class:`UnsafePath`.

    Allowed: an absolute path whose folder exists, whose name is not hidden (no dot file), whose
    extension is one of *exts* (or none), and that is not an existing folder or special file."""
    p = str(path or "").strip()
    if not p or "\x00" in p:
        raise UnsafePath("No path given.")
    p = os.path.abspath(os.path.expanduser(p))
    name = os.path.basename(p)
    if not name or name.startswith("."):
        raise UnsafePath("Choose a file name that does not start with a dot.")
    ext = os.path.splitext(name)[1].lower()
    if ext and ext not in tuple(exts):
        raise UnsafePath("A text export must end in " + ", ".join(exts) + ".")
    if not os.path.isdir(os.path.dirname(p)):
        raise UnsafePath("The folder does not exist.")
    if os.path.lexists(p) and (os.path.islink(p) or not os.path.isfile(p)):
        raise UnsafePath("That name is not an ordinary file.")
    return p
