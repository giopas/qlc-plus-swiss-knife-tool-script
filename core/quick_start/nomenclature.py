"""
core/quick_start/nomenclature.py
================================
Function-naming conventions as data (WORKPLAN principle 7).

A profile is a small JSON file (see ``profiles/nomenclature/``)::

    {
      "id": "prefix",
      "format": "{group}{effect} · {name}",
      "groups":  {"A": "all fixtures", "F": "front four", ...},   # legend
      "effects": {"S": "static colour", "D": "dynamic", ...},     # legend
      "category_group": {"all": "A"},
      "effect_letters": {"static": "S", "dynamic": "D", "pulse": "P",
                         "movement": "M", "matrix": "M", "fx": "*"},
      "prefix_captions": true
    }

The generator asks for a name with a *category* (``all``, ``moving_heads``,
``color_fixtures`` …) and an *effect kind* (``static``, ``dynamic``,
``pulse``, ``matrix``, ``fx``, ``utility``); the profile turns that into a
letter pair.  A category or kind the profile doesn't map gets **no prefix**
(e.g. PANIC RESET, BLACKOUT, or "Moving Heads" when the profile has no
letter for that group) — better no prefix than a wrong one.  The built-in
``plain`` profile keeps names unchanged.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "profiles", "nomenclature")



def user_dir() -> str:
    """Your own naming profiles (v2.7.0: from the community library)."""
    return os.environ.get("QSK_NOMENCLATURE") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "nomenclature")


def _dirs():
    return [(PROFILE_DIR, True), (user_dir(), False)]


# Effect kinds the generator uses (for documentation / UI)
EFFECT_KINDS = ("static", "dynamic", "pulse", "movement", "matrix", "fx", "utility")


class Nomenclature:
    def __init__(self, profile: Optional[dict] = None):
        p = dict(profile or {})
        self.id: str = p.get("id", "plain")
        self.label: str = p.get("label", self.id)
        self.format: str = p.get("format", "{name}")
        self.groups: Dict[str, str] = dict(p.get("groups") or {})
        self.effects: Dict[str, str] = dict(p.get("effects") or {})
        self.category_group: Dict[str, str] = dict(p.get("category_group") or {})
        self.effect_letters: Dict[str, str] = dict(p.get("effect_letters") or {})
        self.prefix_captions: bool = bool(p.get("prefix_captions", False))
        # Groups defined in Quick Start ("group:Front") get the first letter
        # of their name unless category_group maps them explicitly.
        self.auto_group_letter: bool = bool(p.get("auto_group_letter", False))

    @property
    def is_plain(self) -> bool:
        return self.format.strip() == "{name}"

    def name(self, base: str, category: str = "all", kind: str = "static") -> str:
        """Function name for *base* in the given category / effect kind."""
        if self.is_plain:
            return base
        group = self.category_group.get(category)
        if not group and category.startswith("group:") and self.auto_group_letter:
            gname = category.split(":", 1)[1]
            group = self.category_group.get(gname) or next(
                (ch.upper() for ch in gname if ch.isalnum()), None)
        effect = self.effect_letters.get(kind)
        if not group or not effect:
            return base
        try:
            return self.format.format(group=group, effect=effect, name=base)
        except (KeyError, IndexError, ValueError):
            return base

    def caption(self, base: str, category: str = "all", kind: str = "static") -> str:
        return self.name(base, category, kind) if self.prefix_captions else base

    def prefix_of(self, name: str) -> str:
        """The rendered prefix of a generated *name* ("AS · " of "AS · Red"),
        or "" when the name carries none."""
        if self.is_plain or "{name}" not in self.format:
            return ""
        head = self.format.split("{name}")[0]
        if not head:
            return ""
        groups = "|".join(re.escape(g) for g in sorted(set(self.category_group.values()), key=len, reverse=True)) or "(?!)"
        if self.auto_group_letter:
            groups = f"(?:{groups}|[A-Z0-9])"
        effects = "|".join(re.escape(e) for e in sorted(set(self.effect_letters.values()), key=len, reverse=True)) or "(?!)"
        pat = re.escape(head).replace(re.escape("{group}"), f"(?:{groups})") \
                             .replace(re.escape("{effect}"), f"(?:{effects})")
        m = re.match(pat, name)
        return m.group(0) if m else ""

    def legend(self) -> List[str]:
        """Human-readable legend lines (for docs / a VC label panel)."""
        out = []
        if self.groups:
            out.append("1st letter (group): " +
                       " · ".join(f"{k} {v}" for k, v in self.groups.items()))
        if self.effects:
            out.append("2nd letter (effect): " +
                       " · ".join(f"{k} {v}" for k, v in self.effects.items()))
        return out

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "format": self.format,
                "groups": self.groups, "effects": self.effects,
                "category_group": self.category_group,
                "prefix_captions": self.prefix_captions}


def list_profiles() -> List[dict]:
    """[{id, label, description, builtin}] — the built-in profiles (plain first),
    then your own (``~/.qlc_swiss_knife/nomenclature/``)."""
    out = []
    for folder, builtin in _dirs():
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                        p = json.load(fh)
                except (OSError, ValueError):
                    continue
                pid = p.get("id", fn[:-5])
                if not builtin and any(o["id"] == pid for o in out):
                    continue                      # a built-in id is never shadowed
                out.append({"id": pid, "label": p.get("label", fn[:-5]),
                            "description": p.get("description", ""), "builtin": builtin})
    out.sort(key=lambda p: (p["id"] != "plain", not p["builtin"], p["id"]))
    return out


def load_profile(ref: Optional[str] = None) -> Nomenclature:
    """Load a profile by built-in id, or by path to a JSON file.

    ``None``/empty → plain.  Unknown ids raise ``ValueError``.
    """
    if not ref or ref == "plain":
        ref = "plain"
    if ref.endswith(".json") and os.path.isfile(ref):
        path = ref
    else:
        base = os.path.basename(ref)
        path = next((q for q in (os.path.join(f, f"{base}.json") for f, _b in _dirs()) if os.path.isfile(q)),
                    os.path.join(PROFILE_DIR, f"{base}.json"))
    if not os.path.isfile(path):
        raise ValueError(f"Unknown nomenclature profile: {ref}")
    with open(path, encoding="utf-8") as fh:
        return Nomenclature(json.load(fh))
