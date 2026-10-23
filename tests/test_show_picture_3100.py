"""3.10.0: the read-only picture of a Show."""
import os
import shutil
import xml.etree.ElementTree as ET

import app as app_mod
from core import show_picture, workspace

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
NS = "{http://www.qlcplus.org/Workspace}"


def client_with(tmp_path, name="SongBuilder_demo.qxw"):
    for f in os.listdir(CORPUS):
        if f.startswith("SongBuilder_demo"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    c = app_mod.create_app().test_client()
    assert c.post("/api/load", json={"path": str(tmp_path / name)}).status_code == 200
    return c


def test_the_picture_of_a_song_builder_show(tmp_path):
    c = client_with(tmp_path)
    shows = c.get("/api/showpic/list").get_json()
    demo = next(s for s in shows if s["name"] == "Demo Song")
    pic = c.get("/api/showpic/" + demo["id"]).get_json()
    assert pic["song"] is True and pic["length_ms"] > 0
    names = [t["name"] for t in pic["tracks"]]
    assert "Music" in names
    music = next(t for t in pic["tracks"] if t["name"] == "Music")["items"][0]
    assert music["type"] == "Audio" and music["file"] == "SongBuilder_demo.wav" and music["status"] == "ok"
    for tr in pic["tracks"]:
        for it in tr["items"]:
            assert it["start"] >= 0 and it["duration"] >= 0 and it["color"].startswith("#") and len(it["color"]) == 7


def test_a_missing_sound_file_is_marked(tmp_path):
    c = client_with(tmp_path)
    os.remove(tmp_path / "SongBuilder_demo.wav")
    c.post("/api/load", json={"path": str(tmp_path / "SongBuilder_demo.qxw")})
    demo = next(s for s in c.get("/api/showpic/list").get_json() if s["name"] == "Demo Song")
    pic = c.get("/api/showpic/" + demo["id"]).get_json()
    music = next(t for t in pic["tracks"] if t["name"] == "Music")["items"][0]
    assert music["status"] == "missing"


def test_only_a_show_has_a_picture(tmp_path):
    c = client_with(tmp_path)
    scene = next(f["id"] for f in c.get("/api/functions").get_json() if f["type"] == "Scene")
    assert c.get("/api/showpic/" + scene).status_code == 400
    assert c.get("/api/showpic/99999").status_code == 400


def test_the_picture_changes_nothing(tmp_path):
    c = client_with(tmp_path)
    before = ET.tostring(workspace._state["qxw_root"])
    for s in c.get("/api/showpic/list").get_json():
        c.get("/api/showpic/" + s["id"])
    assert ET.tostring(workspace._state["qxw_root"]) == before
    assert c.get("/api/show/history").get_json()["steps"] == []


def test_a_hostile_colour_and_name_are_not_passed_as_markup(tmp_path):
    root = ET.fromstring(f'''<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>
      <Function ID="1" Type="Scene" Name="&lt;img src=x onerror=alert(1)&gt;"/>
      <Function ID="2" Type="Show" Name="S"><TimeDivision Type="Time" BPM="120"/>
        <Track ID="0" Name="T" SceneID="4294967295" isMute="0">
          <ShowFunction ID="1" StartTime="0" Duration="1000" Color="red;background:url(x)"/>
          <ShowFunction ID="1" StartTime="-5" Duration="1000" Color="#123456"/>
          <ShowFunction ID="77" StartTime="1000" Duration="500" Color="#123456"/>
        </Track></Function></Engine></Workspace>''')
    pic = show_picture.picture(root.find(NS + "Engine"), "2")
    items = pic["tracks"][0]["items"]
    assert len(items) == 2                                    # the negative start is dropped
    assert items[0]["color"] == show_picture.TYPE_COLORS["Scene"]     # not the hostile text
    assert items[1]["status"] == "missing" and items[1]["name"] == ""
    # the script escapes names (see showpic.js); here the data is plain text, never markup
    assert "<img" in items[0]["name"]


def test_the_doctor_links_a_show_finding_to_its_picture(tmp_path):
    c = client_with(tmp_path)
    d = c.get("/api/doctor/check").get_json()
    show_ids = {s["id"] for s in c.get("/api/showpic/list").get_json()}
    for f in d["findings"]:
        if "show_id" in f:
            assert f["show_id"] in show_ids
    # an empty Show gets one
    eng = workspace._state["qxw_root"].find("q:Engine", workspace.NS)
    ET.SubElement(eng, NS + "Function", {"ID": "900", "Type": "Show", "Name": "Empty"})
    d = c.get("/api/doctor/check").get_json()
    empty = [f for f in d["findings"] if f["code"] == "D004" and "empty show" in f["message"]]
    assert empty and empty[0]["show_id"] == "900"
    assert c.get("/api/showpic/900").get_json()["tracks"] == []


def test_the_page_has_the_pieces():
    html = open(os.path.join(HERE, "..", "templates", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(HERE, "..", "static", "js", "showpic.js"), encoding="utf-8").read()
    assert 'id="showpic-modal"' in html and "showpic.js" in html
    for name in ("setlist.js", "doctor.js"):
        text = open(os.path.join(HERE, "..", "static", "js", name), encoding="utf-8").read()
        assert "showPicOpen('" not in text, name                                    # the id is data, not code in a handler
        assert "data-showpic=" in text, name
    assert "onclick=" not in js
