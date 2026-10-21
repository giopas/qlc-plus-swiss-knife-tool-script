"""The ribbon names kinds of problem (3.9.5, stage B): /api/show/status carries the
Doctor's counts and, new, the rules behind them: code, severity, title and how
many places each hit.  The old counts are unchanged."""
import os
import shutil

import pytest

import app

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def client(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / "Fest.qxw"
    shutil.copy(os.path.join(CORPUS, "Festival_14fix.qxw"), p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c


def test_status_has_the_rules_behind_the_counts(client):
    d = client.get("/api/show/status").get_json()["doctor"]
    assert {"error", "warning", "info", "rules"} <= set(d)
    rules = d["rules"]
    assert rules, "the festival show has findings"
    assert sum(r["n"] for r in rules.values() if r["severity"] == "error") == d["error"]
    assert sum(r["n"] for r in rules.values() if r["severity"] == "warning") == d["warning"]
    assert all(set(r) == {"n", "severity", "title"} for r in rules.values())
    assert all(r["severity"] in ("error", "warning") for r in rules.values())   # info stays a count


def test_many_places_are_few_kinds(client):
    d = client.get("/api/show/status").get_json()["doctor"]
    kinds = [c for c, r in d["rules"].items() if r["severity"] == "warning"]
    assert d["warning"] > 3 * len(kinds)       # the point of counting kinds: hundreds of places, a handful of rules
    assert d["rules"]["D005"]["title"].startswith("Scene does not declare")
