"""Script-function commands, legacy and QLC+ 5.3 forms.

QLC+ up to 5.2 saves a Script command as ``stopfunction:12`` (percent-encoded
in the file: ``stopfunction%3A12``).  QLC+ 5.3.0 reads that form, converts it
and saves it back as ECMAScript-style calls: ``Engine.stopFunction(12);``,
``Engine.startFunction(5);``, ``Engine.stopOnExit(false);``.

Every tool that reads or edits Script commands goes through this module so it
understands both forms.  New scripts are still written in the legacy form
(QLC+ 5.2 and 5.3 both open it); when an *existing* script is edited, the
commands that are added follow that script's own style.
"""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

_ANY = re.compile(
    r"(?:(?P<lv>start|stop)function:(?P<li>\d+)"
    r"|Engine\.(?P<ev>start|stop)Function\(\s*(?P<ei>\d+)\s*\))", re.I)


def decode(text: str | None) -> str:
    """The command as QLC+ shows it (commands never contain a literal ``%``)."""
    return unquote(text or "")


def is_engine(text: str | None) -> bool:
    """True when the command is in the 5.3 ``Engine.*`` form."""
    return decode(text).lstrip().startswith("Engine.")


def func_refs(text: str | None) -> list[tuple[str, str]]:
    """``[(verb, function id)]`` for every start/stop reference in a command."""
    out = []
    for m in _ANY.finditer(decode(text)):
        verb = (m.group("lv") or m.group("ev")).lower()
        out.append((verb, m.group("li") or m.group("ei")))
    return out


def func_ids(text: str | None) -> list[str]:
    """Function IDs referenced by a command (either form, start or stop)."""
    return [fid for _v, fid in func_refs(text)]


def is_start(text: str | None) -> bool:
    return any(v == "start" for v, _ in func_refs(text))


def is_stop(text: str | None) -> bool:
    return any(v == "stop" for v, _ in func_refs(text))


def uses_engine_style(commands) -> bool:
    """True when a script (iterable of ``<Command>`` elements) is in 5.3 style."""
    return any(is_engine(c.text) for c in commands)


def make(verb: str, fid, *, engine: bool = False, encoded: bool = True) -> str:
    """Build a start/stop command in the requested style."""
    verb = verb.lower()
    raw = f"Engine.{verb}Function({fid});" if engine else f"{verb}function:{fid}"
    return quote(raw, safe=".") if encoded else raw


def renumber(text: str | None, id_map: dict) -> str | None:
    """Rewrite the function IDs of a command through ``id_map``, keeping the
    command's form and its encoding.  Unmapped IDs are left alone."""
    if text is None:
        return None
    encoded = "%" in text
    raw = decode(text)

    def sub(m):
        if m.group("lv"):
            return f"{m.group('lv')}function:{id_map.get(m.group('li'), m.group('li'))}"
        return f"Engine.{m.group('ev')}Function({id_map.get(m.group('ei'), m.group('ei'))})"

    out = _ANY.sub(sub, raw)
    return quote(out, safe=".") if encoded else out
