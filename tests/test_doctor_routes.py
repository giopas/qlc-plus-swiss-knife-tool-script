"""Workspace Doctor tab API (WORKPLAN Phase 2.1) — through the Flask routes."""
import os
import shutil

import app
from core import qxw_io
from core.doctor import check, load_qxf_defs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _client(tmp_path, name="Festival_14fix.qxw"):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / name
    shutil.copy(os.path.join(CORPUS, name), p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c, p


def test_check_lists_findings_with_fix_info(tmp_path):
    c, _ = _client(tmp_path)
    d = c.get("/api/doctor/check").get_json()
    assert d["summary"]["error"] == 1
    d002 = [f for f in d["findings"] if f["code"] == "D002"][0]
    assert d002["fixable"] and d002["default"] and d002["hint"] == "renumber the later copies"
    d016 = [f for f in d["findings"] if f["code"] == "D016"][0]
    assert d016["fixable"] and d016["removing"] and not d016["default"]
    assert "D017" in d["titles"]


def test_fix_returns_new_file_and_report(tmp_path):
    c, p = _client(tmp_path)
    before = p.read_bytes()
    d = c.get("/api/doctor/check").get_json()
    keys = [f["key"] for f in d["findings"] if f["default"]]
    r = c.post("/api/doctor/fix", json={"keys": keys})
    assert r.status_code == 200
    assert r.headers["X-Suggested-Filename"] == "Festival_14fix_v2.qxw"
    root = qxw_io.loads_qxw(r.data)
    rep = check(root, load_qxf_defs([CORPUS]))
    assert not rep.errors and not rep.by_code("D005") and not rep.by_code("D017")
    assert p.read_bytes() == before                    # original untouched
    res = c.get("/api/doctor/last-result").get_json()
    assert res["before"]["error"] == 1 and res["after"]["error"] == 0
    out = tmp_path / "Festival_14fix_v2.qxw"
    out.write_bytes(r.data)
    sr = c.post("/api/doctor/save-report", json={"qxw_path": str(out)}).get_json()
    assert sr["name"] == "Festival_14fix_v2_fix_report.txt"
    assert "── FIXES" in (tmp_path / sr["name"]).read_text(encoding="utf-8")


def test_fix_needs_a_selection(tmp_path):
    c, _ = _client(tmp_path, "Pub_6fix.qxw")
    assert c.post("/api/doctor/fix", json={"keys": []}).status_code == 400


def test_fix_options_are_cleaned():
    from core.doctor import fixes
    assert fixes.clean_options({"d004": "x", "d003": "rewire", "d013": {"bpm": "120"}}) == \
        {"d003": "rewire", "d013": {"bpm": 120.0}}
    assert fixes.clean_options({"d013": {"ms": 0}}) == {}
    assert fixes.clean_options("nope") == {}
