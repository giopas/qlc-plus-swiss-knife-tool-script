#!/usr/bin/env python3
"""Make tests/corpus/SongBuilder_demo.qxw and SongBuilder_demo.wav (3.9.8).

A show to try the Song Builder on: the Pub show, taken to QLC+ 5.3 with the
Upgrade tool, with two songs built by the Song Builder itself:

* *Demo Song*          120 BPM, 16 bars with a short music file (the .wav next to the show)
* *Demo Instrumental*  100 BPM, 8 bars, no music

    python3 tools/make_songbuilder_sample.py            # write both files into tests/corpus
    python3 tools/make_songbuilder_sample.py OUT_DIR    # somewhere else

The music is a quiet 220 Hz tone, 32 s, 2 kHz 8-bit mono (64 KB): enough to see the
bars, not worth listening to.  It is referenced by its file name, so the pair can be
copied to any folder.
"""
import math
import os
import sys
import wave
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
CORPUS = os.path.join(REPO, "tests", "corpus")
SOURCE = os.path.join(CORPUS, "Pub_6fix.qxw")
WAV = "SongBuilder_demo.wav"


def make_wav(path, seconds=32, rate=2000):
    frames = bytes(int(128 + 20 * math.sin(2 * math.pi * 220 * i / rate)) for i in range(seconds * rate))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(frames)


def pick(funcs, kind, n):
    """The first *n* functions of a type, by name, so the demo does not depend on ids."""
    return sorted((f for f in funcs if f["type"] == kind), key=lambda f: f["name"])[:n]


def main(out_dir=CORPUS):
    import app
    from core import qxw_io, upgrade53, workspace
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, WAV)
    make_wav(wav)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": SOURCE}).status_code == 200
    r = c.post("/api/upgrade/apply", json={"steps": list(upgrade53.DEFAULT_STEPS), "target": "5.3"})
    if r.status_code != 200:
        raise SystemExit(r.get_data(as_text=True))
    funcs = c.get("/api/functions").get_json()
    scenes = [f for f in funcs if f["type"] == "Scene" and f["name"] and not f["name"].startswith("[")]
    a, b, d = scenes[0]["id"], scenes[1]["id"], scenes[2]["id"]
    song = {"name": "Demo Song", "bpm": 120, "beats_per_bar": 4, "unit": "bars", "music": {"path": wav},
            "parts": [{"name": "Intro", "function_id": a, "length": "2", "fade_in": "1"},
                      {"name": "Verse", "function_id": b, "length": "4"},
                      {"name": "Chorus", "function_id": d, "length": "4", "fade_out": "0.5"},
                      {"name": "Verse", "function_id": b, "length": "4"},
                      {"name": "Outro", "function_id": a, "length": "to the end", "fade_out": "2"}]}
    inst = {"name": "Demo Instrumental", "bpm": 100, "beats_per_bar": 4, "unit": "bars", "music": {},
            "parts": [{"name": "A", "function_id": b, "length": "4"}, {"name": "B", "function_id": d, "length": "4"}]}
    for spec in (song, inst):
        r = c.post("/api/songbuilder/build", json=spec)
        if r.status_code != 200:
            raise SystemExit(r.get_data(as_text=True))
    data = qxw_io.qxw_bytes(workspace._state["qxw_root"]).decode("utf-8")
    data = data.replace(wav, WAV).replace(wav.replace("&", "&amp;"), WAV)          # the file is next to the show
    data = data.replace("<Version>5.2.2</Version>", "<Version>5.3.0</Version>", 1)      # what QLC+ 5.3 writes after the upgrade
    with open(os.path.join(out_dir, "SongBuilder_demo.qxw"), "w", encoding="utf-8") as fh:
        fh.write(data)
    print("written:", os.path.join(out_dir, "SongBuilder_demo.qxw"), "and", wav)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CORPUS)
