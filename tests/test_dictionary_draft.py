"""Dictionary: Draft descriptions and Save as new file (v3.0.1)."""
import os
import shutil

import pytest

import app

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    client.tmp = tmp_path
    yield client
    from core import workspace
    workspace._state['shared_descriptions'].clear()      # descriptions outlive a show on purpose


def test_draft_fills_only_the_empty_ones_and_saves_a_new_file(c):
    assert c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}).status_code == 200
    rows = c.get("/api/dictionary/").get_json()
    mine = rows[0]["id"]
    c.patch(f"/api/dictionary/{mine}", json={"desc": "My own words"})
    d = c.post("/api/dictionary/draft", json={}).get_json()
    assert d["drafted"] > 0 and d["described"] <= d["total"]
    after = {r["id"]: r.get("desc", "") for r in c.get("/api/dictionary/").get_json()}
    assert after[mine] == "My own words"                         # kept
    assert c.post("/api/dictionary/draft", json={}).get_json()["drafted"] == 0   # deterministic, nothing twice
    s1 = c.post("/api/dictionary/save-new", json={}).get_json()
    s2 = c.post("/api/dictionary/save-new", json={}).get_json()
    assert s1["path"].endswith("Festival_14fix_dictionary.txt")
    assert s2["path"].endswith("Festival_14fix_dictionary_v2.txt")   # never overwrites
    text = open(s1["path"], encoding="utf-8").read()
    assert text.startswith("ID|Name|Description") and "My own words" in text
