"""3.10.0: the new interface sentences exist in all seven languages."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("it", "fr", "de", "es", "pt", "ja", "zh")
KEYS = [
    "Make a click track",
    "Makes a click-track sound file at this BPM, as long as the parts, next to the show.",
    "✓ Click track saved: {0}",
    "Show the picture of this Show",
    "Picture",
    "Grid step in pixels",
    "while moving",
    "Resizing — x:{0} y:{1} w:{2} h:{3} (grid {4}px)",
    "Resized to {0}×{1} · not saved yet",
    "keep keys and MIDI inputs",
    "＋ Add as page…",
    "Keys and MIDI of “{0}”",
    "from the template",
    "set again: already used by {0}",
    "No input device on {0} in this show: those inputs listen to nothing until a controller is patched there.",
    "Add the page with {0} binding(s)",
    "Add it without keys and MIDI",
]


@pytest.mark.parametrize("lang", LANGS)
def test_new_sentences_are_translated(lang):
    d = json.loads((ROOT / "static" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    for k in KEYS:
        assert d.get(k), (lang, k)
        assert set(re.findall(r"\{\d+\}", d[k])) == set(re.findall(r"\{\d+\}", k)), (lang, k)


def test_every_sentence_the_code_draws_is_a_key():
    """The English text drawn by the new code is the key: check the ones built from pieces."""
    js = (ROOT / "static" / "js" / "vc_editor.js").read_text(encoding="utf-8")
    assert "Resizing — x:${r.x} y:${r.y} w:${r.w} h:${r.h} (grid ${m.grid}px)" in js
    assert "`Resized to ${n.w}×${n.h}`" in js
