"""Trigger Manager never overwrites the loaded workspace (WORKPLAN 0.4)."""
import os
import shutil

import pytest

from core import workspace as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "manual", "tilt_check.qxw")


@pytest.fixture
def loaded(tmp_path):
    src = tmp_path / "Show_v41.qxw"
    shutil.copy(SAMPLE, src)
    res = ws.load_qxw(str(src))
    assert not res.get("error")
    yield src
    ws._reset()


def test_save_writes_next_version_and_keeps_original(loaded):
    before = loaded.read_bytes()
    out = ws.save_triggers()
    assert os.path.basename(out) == "Show_v42.qxw"
    assert loaded.read_bytes() == before
    data = open(out, "rb").read()
    assert data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n')
    # second save does not clobber the first
    assert os.path.basename(ws.save_triggers()) == "Show_v43.qxw"


def test_save_refused_in_upload_mode(loaded):
    ws.set_original_name("Show_v41.qxw")
    with pytest.raises(RuntimeError):
        ws.save_triggers()


def test_save_as_new_route_keeps_doctype(loaded):
    import app
    client = app.create_app().test_client()
    r = client.post("/api/triggers/save-as-new")
    assert r.status_code == 200
    assert r.headers["X-Suggested-Filename"] == "Show_v42.qxw"
    assert b"<!DOCTYPE Workspace>" in r.data[:80]
