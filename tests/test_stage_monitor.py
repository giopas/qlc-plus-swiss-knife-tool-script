"""Stage Monitor (3.5.0): cue lists read from the show, the settings file,
the exported page and the little server for the tablet."""
import json
import os
import py_compile
import re
import shutil
import socket
import urllib.request
import xml.etree.ElementTree as ET

import pytest

from core import stage_monitor as sm

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
ROOT = os.path.dirname(HERE)

# Two cue lists on two pages of a multipage frame, steps out of order, a note,
# a cue list with no chaser, the QLC+ namespace.
SMALL = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Workspace>
<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="VC">
 <Engine>
  <Function ID="1" Type="Scene" Name="Intro"/>
  <Function ID="2" Type="Scene" Name="Song A"/>
  <Function ID="3" Type="Scene" Name="Song B"/>
  <Function ID="10" Type="Chaser" Name="Set 1">
   <Step Number="1" FadeIn="0" Hold="0" FadeOut="0" Note="capo 2">2</Step>
   <Step Number="0" FadeIn="0" Hold="0" FadeOut="0">1</Step>
   <Step Number="2" FadeIn="0" Hold="0" FadeOut="0">3</Step>
  </Function>
  <Function ID="11" Type="Chaser" Name="Set 2">
   <Step Number="0" FadeIn="0" Hold="0" FadeOut="0">3</Step>
  </Function>
 </Engine>
 <VirtualConsole>
  <Frame Caption="Main" ID="0">
   <Frame Caption="Setlists" ID="20">
    <Multipage PagesNum="2" CurrentPage="0"/>
    <Shortcut Page="0" Name="First set"/>
    <Shortcut Page="1" Name="Second set"/>
    <CueList Caption="Set one" ID="21" Page="0">
     <Chaser>10</Chaser>
     <Next><Input Universe="0" Channel="64"/><Key>Space</Key></Next>
    </CueList>
    <CueList Caption="Set two" ID="22" Page="1"><Chaser>11</Chaser></CueList>
   </Frame>
   <CueList Caption="Empty" ID="23"/>
  </Frame>
  <Frame Caption="Second page" ID="30">
   <CueList Caption="Encore" ID="31"><Chaser>11</Chaser></CueList>
  </Frame>
 </VirtualConsole>
</Workspace>
"""


def _small():
    return ET.fromstring(SMALL.split("\n", 2)[2])


def _corpus(name):
    return ET.parse(os.path.join(CORPUS, name)).getroot()


# ── reading the show ─────────────────────────────────────────────────────────

def test_every_cuelist_with_its_place_chaser_and_steps():
    cls = sm.cuelists(_small())
    assert [c["id"] for c in cls] == ["21", "22", "23", "31"]
    one = cls[0]
    assert one["caption"] == "Set one"
    assert one["path"] == ["Main", "Setlists"]
    assert one["page"] == 0
    assert one["frame_page"] == {"page": 0, "name": "First set"}
    assert one["chaser"] == {"id": "10", "name": "Set 1"}
    assert [(s["index"], s["name"], s["note"]) for s in one["steps"]] == [
        (0, "Intro", ""), (1, "Song A", "capo 2"), (2, "Song B", "")]
    assert one["inputs"] == {"next": ["MIDI U1 ch 64", "key Space"]}
    assert cls[1]["frame_page"] == {"page": 1, "name": "Second set"}
    assert cls[2]["chaser"] is None and cls[2]["steps"] == []
    assert cls[3]["page"] == 1 and cls[3]["path"] == ["Second page"] and cls[3]["frame_page"] is None


def test_the_corpus_setlists():
    cls = sm.cuelists(_corpus("Festival_14fix.qxw"))
    assert [c["caption"] for c in cls] == ["Setlist: Band A", "Setlist: Band B", "Setlist: Band C"]
    assert [len(c["steps"]) for c in cls] == [24, 20, 22]
    assert cls[0]["steps"][1]["name"] == "- Intro (Silhouette)"
    assert set(cls[0]["inputs"]) == {"next", "previous", "stop"}
    pub = sm.cuelists(_corpus("Pub_6fix.qxw"))
    assert len(pub) == 1 and pub[0]["chaser"]["name"] == "Setlist: Pub"


def test_a_show_without_virtual_console():
    assert sm.cuelists(ET.fromstring("<Workspace><Engine/></Workspace>")) == []


def test_reading_does_not_change_the_show():
    root = _corpus("Festival_14fix.qxw")
    before = ET.tostring(root)
    sm.cuelists(root)
    assert ET.tostring(root) == before


# ── the settings file ────────────────────────────────────────────────────────

def test_sidecar_is_shared_by_every_version_of_the_show(tmp_path):
    assert sm.sidecar_path(str(tmp_path / "Gig_v7.qxw")) == str(tmp_path / "Gig.stage.json")
    assert sm.sidecar_path(str(tmp_path / "Gig.qxw")) == str(tmp_path / "Gig.stage.json")
    assert sm.sidecar_path(str(tmp_path / "Gig_vintage.qxw")) == str(tmp_path / "Gig_vintage.stage.json")


def test_clean_config_checks_every_value():
    c = sm.clean_config({
        "title": "x" * 500, "font": "XXL", "theme": "pink", "show_next": 0, "ws_port": "70000",
        "http_port": "8090", "junk": 1,
        "lists": [{"id": "21", "mode": "god", "label": " A ", "steps": {"1": {"hide": 1, "label": " "}, "x": {}, "2": {}}},
                  {"id": "21"}, {"id": "abc"}, "nonsense"],
    })
    assert len(c["title"]) == 120 and c["font"] == "M" and c["theme"] == "dark"
    assert c["show_next"] is False and c["ws_port"] == 9999 and c["http_port"] == 8090
    assert "junk" not in c
    assert c["lists"] == [{"id": "21", "label": "A", "mode": "read", "steps": {"1": {"hide": True}}}]


def test_save_and_load_round_trip(tmp_path):
    p = str(tmp_path / "Gig.stage.json")
    cfg = sm.clean_config({"title": "Gig", "lists": [{"id": "21", "steps": {"0": {"label": "Walk-in"}}}]})
    sm.save_config(cfg, p)
    assert sm.load_config(p) == cfg
    assert open(p, encoding="utf-8").read() == json.dumps(cfg, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert sm.load_config(str(tmp_path / "none.json")) is None
    (tmp_path / "bad.json").write_text("{nope")
    assert sm.load_config(str(tmp_path / "bad.json")) is None


def test_reconcile_by_widget_id():
    cls = sm.cuelists(_small())
    cfg = {"lists": [{"id": "99", "label": "Gone"}, {"id": "22", "steps": {"0": {"hide": True}, "5": {"hide": True}}}]}
    r = sm.reconcile(cfg, cls)
    assert r["missing"] == [{"id": "99", "label": "Gone"}]
    assert [i["id"] for i in r["config"]["lists"]] == ["22"]
    assert r["config"]["lists"][0]["steps"] == {"0": {"hide": True}}     # step 5 does not exist
    assert r["new"] == ["21", "23", "31"]


def test_default_config_takes_the_first_list():
    cls = sm.cuelists(_small())
    assert [i["id"] for i in sm.default_config(cls, "Gig")["lists"]] == ["21"]
    assert sm.default_config([], "Gig")["lists"] == []


# ── the page ─────────────────────────────────────────────────────────────────

def _cfg(**kw):
    base = {"title": "Gig", "lists": [{"id": "21", "label": "", "mode": "read",
                                      "steps": {"0": {"label": "Walk-in"}, "2": {"hide": True}}},
                                     {"id": "31", "label": "Encore!", "mode": "control"}]}
    base.update(kw)
    return base


def _inlined(html):
    m = re.search(r"const CFG = (\{.*?\}) \|\|", html, re.S)
    assert m, "configuration not inlined"
    return json.loads(m.group(1))


def test_page_data_has_labels_hidden_steps_and_order():
    d = _inlined(sm.build_page(_cfg(), sm.cuelists(_small())))
    assert [l["id"] for l in d["lists"]] == [21, 31]
    one = d["lists"][0]
    assert one["label"] == "Set one" and one["mode"] == "read"
    assert [(s["i"], s["name"], s["hide"]) for s in one["steps"]] == [
        (0, "Walk-in", False), (1, "Song A", False), (2, "Song B", True)]
    assert one["steps"][1]["note"] == "capo 2"
    assert d["lists"][1]["label"] == "Encore!" and d["lists"][1]["mode"] == "control"
    assert d["wsPort"] == 9999 and d["title"] == "Gig" and d["t"] == {}


def test_page_is_self_contained_and_deterministic():
    cls = sm.cuelists(_small())
    a, b = sm.build_page(_cfg(), cls), sm.build_page(_cfg(), cls)
    assert a == b
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", a), "no outside resources"
    assert "@import" not in a and "fonts.googleapis" not in a
    assert "<title>Gig</title>" in a


def test_names_cannot_break_out_of_the_page():
    root = _small()
    for f in root.iter("{http://www.qlcplus.org/Workspace}Function"):
        if f.get("ID") == "1":
            f.set("Name", "</script><script>alert(1)</script>")
    html = sm.build_page(_cfg(title='<b>"x"</b>'), sm.cuelists(root))
    assert "</script><script>alert(1)" not in html
    assert html.count("</script>") == 1
    assert "<title>&lt;b&gt;&quot;x&quot;&lt;/b&gt;</title>" in html
    assert _inlined(html)["lists"][0]["steps"][0]["name"] == "Walk-in"
    html = sm.build_page(_cfg(lists=[{"id": "21"}]), sm.cuelists(root))
    assert _inlined(html)["lists"][0]["steps"][0]["name"] == "</script><script>alert(1)</script>"


def test_the_protocol_lives_in_one_place():
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    js = html[html.index("<script>"):]
    block = js[js.index("const PROTOCOL"):js.index("const POLL_MS")]
    for s in ("/qlcplusWS", "/vc.json", "getWidgetStatus", "|NEXT", "|PREV", '"CUE"', '"CUE_STATE"'):
        assert s in block, s
    rest = js.replace(block, "")
    assert "QLC+API" not in rest and "qlcplusWS" not in rest


@pytest.mark.parametrize("lang", ["it", "fr", "de", "es", "pt", "ja", "zh"])
def test_every_word_on_the_page_is_translated(lang):
    t = sm.page_strings(lang)
    assert set(t) == set(sm.PAGE_STRINGS), set(sm.PAGE_STRINGS) - set(t)
    d = _inlined(sm.build_page(_cfg(title=""), sm.cuelists(_small()), lang))
    assert d["lang"] == lang and d["t"]["NEXT"] == t["NEXT"]


def test_every_word_of_the_page_is_in_the_page():
    """PAGE_STRINGS is the list of what the page passes to T()."""
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    used = set(re.findall(r'\bT\("([^"]+)"\)', html))
    assert used == set(sm.PAGE_STRINGS), (used ^ set(sm.PAGE_STRINGS))


def test_an_unknown_language_is_english():
    assert sm.page_strings("xx") == {} and sm.page_strings("en") == {}


# ── export and serving ───────────────────────────────────────────────────────

def test_export_writes_the_page_and_the_server(tmp_path):
    out = sm.export(str(tmp_path / "stage_monitor"), _cfg(http_port=8090), sm.cuelists(_small()))
    assert os.path.isfile(out["page"]) and os.path.isfile(out["script"])
    script = open(out["script"], encoding="utf-8").read()
    assert "DEFAULT_PORT = 8090" in script
    py_compile.compile(out["script"], doraise=True)
    # again: the same bytes
    first = open(out["page"], "rb").read()
    sm.export(str(tmp_path / "stage_monitor"), _cfg(http_port=8090), sm.cuelists(_small()))
    assert open(out["page"], "rb").read() == first


def test_export_needs_a_cue_list(tmp_path):
    with pytest.raises(ValueError):
        sm.export(str(tmp_path / "x"), {"lists": []}, sm.cuelists(_small()))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_server_serves_only_that_folder(tmp_path):
    out = sm.export(str(tmp_path / "stage_monitor"), _cfg(), sm.cuelists(_small()))
    (tmp_path / "secret.txt").write_text("no")
    srv = sm.StageServer()
    port = _free_port()
    srv.start(out["folder"], port, host="127.0.0.1")
    try:
        assert srv.status()["running"] and srv.status()["port"] == port
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode()
        assert "const CFG" in body
        with pytest.raises(Exception):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/../secret.txt", timeout=5)
    finally:
        srv.stop()
    assert not srv.running
    with pytest.raises(Exception):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)


def test_the_server_needs_an_exported_page(tmp_path):
    with pytest.raises(ValueError):
        sm.StageServer().start(str(tmp_path), _free_port(), host="127.0.0.1")


def test_a_busy_port_is_said_plainly(tmp_path):
    out = sm.export(str(tmp_path / "stage_monitor"), _cfg(), sm.cuelists(_small()))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        srv = sm.StageServer()
        with pytest.raises(ValueError, match="busy"):
            srv.start(out["folder"], port, host="127.0.0.1")
        assert not srv.running


IFCONFIG = """lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	inet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	inet 192.168.1.23 netmask 0xffffff00 broadcast 192.168.1.255
bridge100: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	inet 192.168.2.1 netmask 0xffffff00 broadcast 192.168.2.255
en5: flags=8863<UP> mtu 1500
	inet 169.254.10.2 netmask 0xffff0000
"""
IPADDR = """1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
    inet 127.0.0.1/8 scope host lo
3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 10.42.0.1/24 brd 10.42.0.255 scope global noprefixroute wlan0
"""
IPCONFIG = """Wireless LAN adapter Local Area Connection* 2:
   IPv4 Address. . . . . . . . . . . : 192.168.137.1
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 10.0.0.5(Preferred)
   Default Gateway . . . . . . . . . : 10.0.0.1
"""


def test_addresses_from_each_system():
    assert sm.parse_addresses(IFCONFIG, "Darwin") == ["192.168.1.23", "192.168.2.1"]
    assert sm.parse_addresses(IPADDR, "Linux") == ["10.42.0.1"]
    assert sm.parse_addresses(IPCONFIG, "Windows") == ["192.168.137.1", "10.0.0.5"]


def test_hotspot_address_comes_first(monkeypatch):
    class R:
        stdout = IFCONFIG
    monkeypatch.setattr(sm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sm.subprocess, "run", lambda *a, **k: R())
    assert sm.local_addresses() == ["192.168.2.1", "192.168.1.23"]


# ── through the Flask routes ─────────────────────────────────────────────────

def _client(tmp_path, name="Festival_14fix.qxw"):
    import app
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / name
    shutil.copy(os.path.join(CORPUS, name), p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c, p


def test_routes_list_save_preview_export(tmp_path):
    c, p = _client(tmp_path, "Festival_14fix.qxw")
    before = p.read_bytes()
    d = c.get("/api/stagemon/lists").get_json()
    assert [x["id"] for x in d["lists"]] == ["4001", "4101", "4201"]
    assert [x["id"] for x in d["config"]["lists"]] == ["4001"] and not d["saved"]
    assert d["folder"] == str(tmp_path / "stage_monitor")
    assert d["sidecar"] == "Festival_14fix.stage.json"

    cfg = d["config"]
    cfg["lists"].append({"id": "4201", "label": "C", "mode": "control", "steps": {"1": {"hide": True}}})
    r = c.post("/api/stagemon/config", json={"config": cfg}).get_json()
    assert r["saved"] and (tmp_path / "Festival_14fix.stage.json").is_file()
    d = c.get("/api/stagemon/lists").get_json()
    assert d["saved"] and [x["id"] for x in d["config"]["lists"]] == ["4001", "4201"]
    assert d["new"] == ["4101"]

    assert c.post("/api/stagemon/preview", json={"config": cfg, "lang": "it"}).status_code == 200
    resp = c.get("/api/stagemon/preview")
    html = resp.get_data(as_text=True)
    assert _inlined(html)["t"]["NEXT"] == "SUCCESSIVA"
    csp = resp.headers["Content-Security-Policy"]           # it may talk to QLC+, nothing else
    assert "ws://localhost:*" in csp and "ws://127.0.0.1:*" in csp and "https:" not in csp

    r = c.post("/api/stagemon/export", json={"config": cfg}).get_json()
    assert os.path.isfile(r["page"]) and os.path.isfile(r["script"]) and r["lists"] == 2
    assert p.read_bytes() == before, "the show is never written"
    assert c.get("/api/show/status").get_json().get("unsaved", 0) == 0


def test_export_without_a_cue_list_is_refused(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/api/stagemon/export", json={"config": {"lists": []}})
    assert r.status_code == 400


def test_routes_without_a_show():
    import app
    from core import workspace
    workspace._reset()
    c = app.create_app().test_client()
    assert c.get("/api/stagemon/lists").status_code == 400
    assert c.get("/api/stagemon/status").status_code == 200


def test_stage_monitor_calls_are_not_in_the_recipe():
    from core import recipe
    assert not recipe.recordable("POST", "/api/stagemon/config")
    assert not recipe.recordable("POST", "/api/stagemon/serve")


def test_the_screen_is_wired():
    html = open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8").read()
    assert 'id="scr-stagemon"' in html and 'id="sn-stagemon"' in html and "stagemon.js" in html
    app_js = open(os.path.join(ROOT, "static", "js", "app.js"), encoding="utf-8").read()
    assert "stagemonInit" in app_js and "'stagemon'" in app_js
    spec = open(os.path.join(ROOT, "packaging", "swissknife.spec"), encoding="utf-8").read()
    assert "stage_page" in spec
