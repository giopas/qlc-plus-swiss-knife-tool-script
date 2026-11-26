"""3.22.0 — the pictures never show the login name (tools/shots.py sets SK_NO_USER_NAME)."""
import os

import app


def test_settings_give_no_name_for_the_pictures(monkeypatch):
    monkeypatch.setenv("LOGNAME", "someone")
    monkeypatch.delenv("SK_NO_USER_NAME", raising=False)
    c = app.create_app().test_client()
    assert c.get("/api/settings").get_json()["user_name"] == "someone"
    monkeypatch.setenv("SK_NO_USER_NAME", "1")
    assert c.get("/api/settings").get_json()["user_name"] is None


def test_shots_starts_the_app_without_a_name():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "tools", "shots.py"), encoding="utf-8") as fh:
        assert 'SK_NO_USER_NAME="1"' in fh.read()
