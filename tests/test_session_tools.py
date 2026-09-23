"""Sessions (.qsk) restore every tool's state, not just the workspace."""
import json

import app
from core import session as sess


def test_tools_and_show_info_round_trip(tmp_path):
    c = app.create_app().test_client()
    c.post("/api/session/new")
    qsk = {"version": 1, "workspace": None, "show_name": "My Show", "event_date": "2026-10-03",
           "tools": {"porter": {"source": "/a/S_v41.qxw"}, "paper": {"checklist": "A4 Portrait"},
                     "brightness": {"scales": {"0": 0.6}}}}
    p = tmp_path / "t.qsk"
    p.write_text(json.dumps(qsk))
    r = c.post("/api/session/load-from-path", json={"path": str(p)}).get_json()
    assert r["session"]["tools"]["porter"]["source"] == "/a/S_v41.qxw"
    assert sess.get_show_name() == "My Show"
    exp = c.get("/api/session/export").get_json()
    assert exp["tools"]["brightness"]["scales"] == {"0": 0.6}
    assert exp["event_date"] == "2026-10-03"


def test_old_session_keys_are_migrated():
    c = app.create_app().test_client()
    c.post("/api/session/new")
    r = c.post("/api/session/apply", json={"session": {
        "version": 1, "porter_source": "/x/a.qxw",
        "showbook_qxf_dir": "/q", "showbook_sections": ["summary"]}}).get_json()
    t = r["session"]["tools"]
    assert t["porter"]["source"] == "/x/a.qxw"
    assert t["showbook"] == {"qxf_dir": "/q", "sections": ["summary"]}
