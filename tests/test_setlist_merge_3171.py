"""3.17.1 Setlist Manager: loading a setlist file keeps the looks the slot
already has; the file brings the order and the BPMs.  Re-Match gives a song
the look its copy was made from, not the copy."""
import os
import shutil

import pytest

import app
from core import workspace as ws

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")) and " 2." not in f:
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    client.tmp = tmp_path
    r = client.post("/api/load", json={"path": str(tmp_path / "Festival_14fix.qxw")})
    assert r.status_code < 300, r.get_data(as_text=True)[:300]
    return client


def _txt(c, lines, name="setlist.txt"):
    p = c.tmp / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def test_merge_keeps_looks_and_takes_bpm():
    cur = [
        {"txt_name": "Intro", "qxw_id": "1", "qxw_name": "A", "in": "0", "hold": "4294967294", "out": "500"},
        {"txt_name": "- Stage Patter", "qxw_id": "2", "qxw_name": "B", "in": "0", "hold": "4294967294", "out": "0"},
        {"txt_name": "Song One", "qxw_id": "3", "qxw_name": "C", "in": "0", "hold": "4294967294", "out": "0", "bpm": "100"},
        {"txt_name": "- Stage Patter", "qxw_id": "4", "qxw_name": "D", "in": "0", "hold": "4294967294", "out": "0"},
    ]
    dflt = {"qxw_id": "", "qxw_name": "", "in": "0", "hold": "4294967294", "out": "0"}
    loaded = [
        dict(dflt, txt_name="intro"),                      # case ignored
        dict(dflt, txt_name="New Song", bpm="132"),
        dict(dflt, txt_name="- Stage Patter"),
        dict(dflt, txt_name="Song One (Setlist)"),         # copy suffix ignored, keeps BPM 100
        dict(dflt, txt_name="- Stage Patter", hold="8000", bpm="90"),
    ]
    rows, kept = ws.merge_loaded_rows(cur, loaded)
    assert kept == 4
    assert [r["qxw_id"] for r in rows] == ["1", "", "2", "3", "4"]
    assert rows[0]["out"] == "500"                         # timing kept
    assert rows[1]["bpm"] == "132" and not rows[1]["qxw_id"]
    assert rows[3]["bpm"] == "100"                         # file had none
    assert rows[4]["hold"] == "8000" and rows[4]["bpm"] == "90"   # the file's time and tempo win


def test_load_file_merges_into_the_show_setlist(c):
    shown = c.get("/api/setlist/4001/details").get_json()
    assert shown and all(r["qxw_id"] for r in shown)
    names = [r["txt_name"] for r in shown]
    lines = [f"{n} | {120 + i} BPM" for i, n in enumerate(names)]
    lines.insert(1, "Brand New Song | 132")
    d = c.post("/api/setlist/4001/load-file", json={"path": _txt(c, lines)}).get_json()
    assert d["ok"] and d["count"] == len(names) + 1
    assert d["kept"] == len(names)
    assert d["with_bpm"] == len(names) + 1
    rows = d["rows"]
    assert rows[1]["txt_name"] == "Brand New Song" and not rows[1]["qxw_id"]
    others = rows[:1] + rows[2:]
    assert [r["qxw_id"] for r in others] == [r["qxw_id"] for r in shown]
    assert all(r.get("bpm") for r in rows)
    # stored for the slot, so Apply and the PDF see it
    assert c.get("/api/setlist/4001/details").get_json() == rows


def test_load_file_without_merge_replaces(c):
    names = [r["txt_name"] for r in c.get("/api/setlist/4001/details").get_json()]
    d = c.post("/api/setlist/4001/load-file",
               json={"path": _txt(c, names), "merge": False}).get_json()
    assert d["kept"] == 0 and not any(r["qxw_id"] for r in d["rows"])


def test_merge_endpoint_uses_the_page_rows(c):
    cur = [{"txt_name": "X", "qxw_id": "7", "qxw_name": "Seven", "in": "0", "hold": "4294967294", "out": "0"}]
    new = [{"txt_name": "X", "qxw_id": "", "qxw_name": "", "in": "0", "hold": "4294967294", "out": "0", "bpm": "128"}]
    d = c.post("/api/setlist/4001/merge", json={"rows": new, "current": cur}).get_json()
    assert d["kept"] == 1 and d["rows"][0]["qxw_id"] == "7" and d["rows"][0]["bpm"] == "128"


def test_rematch_gives_the_original_not_the_copy(c):
    # a show applied before: its chaser plays copies named like the songs
    c.post("/api/setlist/4001/details", json={"rows": [
        {"txt_name": "Zebra Crossing Song", "qxw_id": "1421" if "1421" in ws._state["func_by_id"]
         else next(iter(ws._state["func_by_id"])), "qxw_name": "", "in": "0", "hold": "4294967294", "out": "0"}]})
    assert c.post("/api/setlist/4001/apply", json={}).get_json().get("ok")
    copies = {cid: base for cid, base in ws._state["clone_base_map"].items()
              if base in ws._state["func_by_id"]
              and ws._state["func_by_id"][cid].startswith("Zebra Crossing Song")}
    assert copies
    cid, base = next(iter(copies.items()))
    m = c.post("/api/setlist/auto-match", json={"songs": ["Zebra Crossing Song"]}).get_json()[0]
    assert m["matched_id"] == base
    assert m["matched_name"] == ws._state["func_by_id"][base]
