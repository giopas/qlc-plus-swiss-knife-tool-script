"""3.21.0 Function Porter: the step-3 mapping saved as a file and loaded
again, with fixtures found by name and ID (the next show may number them
differently)."""
import json
import os

import pytest

import app
from core import porter_map as M

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _fx(i, name, model="PAR", mode="4ch"):
    return {"id": str(i), "name": name, "manufacturer": "X", "model": model, "mode": mode,
            "universe": "0", "address": str(i * 4)}


SRC = [_fx(0, "FLS"), _fx(1, "FRS"), _fx(2, "Spot L", "Spot", "16ch")]
TGT = [_fx(6, "Pub L"), _fx(7, "Pub R")]


def test_round_trip_keeps_the_mapping():
    data = M.export_map({"0": ["6"], "1": ["7"], "2": []}, SRC, TGT,
                        {"fanout": "fan_in", "drop_unmapped": True, "junk": 1}, "Fest", "Pub")
    assert data["format"] == M.FORMAT and "junk" not in data["options"]
    back = M.import_map(json.loads(json.dumps(data)), SRC, TGT)
    assert back["mapping"] == {"0": ["6"], "1": ["7"], "2": []}
    assert back["options"]["fanout"] == "fan_in" and back["not_found"] == []


def test_found_by_name_when_ids_change():
    data = M.export_map({"0": ["6"], "1": ["7"]}, SRC, TGT)
    src2 = [_fx(10, "FRS"), _fx(11, "FLS")]          # renumbered and reordered
    tgt2 = [_fx(20, "Pub R"), _fx(21, "Pub L")]
    back = M.import_map(data, src2, tgt2)
    assert back["mapping"] == {"11": ["21"], "10": ["20"]}


def test_missing_fixtures_are_reported():
    data = M.export_map({"0": ["6", "7"], "2": ["7"]}, SRC, TGT)
    back = M.import_map(data, SRC[:1], [_fx(6, "Pub L")])
    assert back["mapping"] == {"0": ["6"]}
    assert back["not_found"] == ["Spot L"] and back["targets_not_found"] == ["Pub R"]


def test_not_a_mapping_is_refused():
    with pytest.raises(M.MapError):
        M.import_map({"format": "something else"}, SRC, TGT)
    with pytest.raises(M.MapError):
        M.import_map({"format": M.FORMAT, "version": 99}, SRC, TGT)


def test_mirror_and_skip_follow_the_fixtures():
    data = M.export_map({"0": ["6"]}, SRC, TGT, {"mirror": M.idents(["1"], SRC), "skip": M.idents(["2"], SRC)})
    src2 = [_fx(5, "Spot L", "Spot", "16ch"), _fx(4, "FRS"), _fx(3, "FLS")]
    back = M.import_map(data, src2, TGT)
    assert back["options"]["mirror"] == ["4"] and back["options"]["skip"] == ["5"]


def test_routes_on_the_corpus():
    c = app.create_app().test_client()
    assert c.post("/api/porter/source/load", json={"path": os.path.join(CORPUS, "Festival_14fix.qxw")}).status_code < 300
    assert c.post("/api/porter/target/load", json={"path": os.path.join(CORPUS, "Pub_6fix.qxw")}).status_code < 300
    src = c.get("/api/porter/source/fixtures").get_json()
    tgt = c.get("/api/porter/target/fixtures").get_json()
    mapping = {src[0]["id"]: [tgt[0]["id"]], src[1]["id"]: [tgt[1]["id"], tgt[2]["id"]]}
    r = c.post("/api/porter/map/export", json={"mapping": mapping, "mirror": [src[1]["id"]],
                                                "options": {"fanout": "pattern_repeat"}})
    assert r.status_code == 200, r.get_json()
    saved = r.get_json()
    assert saved["rows"][0]["source"]["name"] == src[0]["name"]
    r = c.post("/api/porter/map/import", json=saved)
    assert r.status_code == 200
    d = r.get_json()
    assert d["mapping"] == mapping and d["options"]["mirror"] == [src[1]["id"]]
    assert c.post("/api/porter/map/import", json={"rows": []}).status_code == 400
