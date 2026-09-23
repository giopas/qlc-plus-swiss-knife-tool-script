"""Generate the Quick Start golden files in tests/corpus/ (WORKPLAN 1.1).

Three reference rigs, driven through the real Flask routes, deterministic:

* ``QuickStart_6fix``     — 2 × Eurolite LED 4C-12 (truss) + 4 × Generic 7-Ch
                            RGB PAR (floor). Plain names, default style.
* ``QuickStart_club``     — 2 × Chauvet Intimidator Spot 110 (6-channel mode,
                            channel order ≠ definition order) + 4 × SlimPAR 56.
                            20Minutes names, built-in Compact style.
* ``QuickStart_multiuni`` — 8 × Intimidator Spot 375Z (15-ch, shutter closed
                            at 0) + 60 × SlimPAR 56 → spills into universe 2.
                            20Minutes names, style cloned from Pub_6fix.qxw.

    python3 tools/make_quickstart_sample.py            # write all three
    python3 tools/make_quickstart_sample.py club       # one rig, to corpus
    python3 tools/make_quickstart_sample.py club out.qxw
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
CORPUS = os.path.join(REPO, "tests", "corpus")
FIXTURES = os.path.join(REPO, "tests", "fixtures")

STAGE = {"w_mm": 6000, "d_mm": 4000, "h_mm": 3000}

RIGS = {
    "6fix": {
        "title": "QuickStart 6fix",
        "fixtures": [  # (qxf path, mode or None, quantity, name)
            (os.path.join(CORPUS, "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"), None, 2, "Ceiling"),
            (os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf"), None, 4, "Floor"),
        ],
        "positions": [(1500, 500, 2900), (4500, 500, 2900),
                      (750, 3500, 200), (2250, 3500, 200), (3750, 3500, 200), (5250, 3500, 200)],
        "options": {},
    },
    "club": {
        "title": "QuickStart club",
        "fixtures": [
            (os.path.join(FIXTURES, "Chauvet-Intimidator-Spot-110.qxf"), "6 Channel", 2, "Spot"),
            (os.path.join(FIXTURES, "Chauvet-SlimPAR-56.qxf"), "7-Ch", 4, "Par"),
        ],
        "positions": [(2000, 500, 2900), (4000, 500, 2900),
                      (750, 3500, 200), (2250, 3500, 200), (3750, 3500, 200), (5250, 3500, 200)],
        "options": {"nomenclature": "20minutes", "style": "compact"},
    },
    "multiuni": {
        "title": "QuickStart multiuni",
        "fixtures": [
            (os.path.join(FIXTURES, "Chauvet-Intimidator-Spot-375Z-IRC.qxf"), "15 channel", 8, "Spot"),
            (os.path.join(FIXTURES, "Chauvet-SlimPAR-56.qxf"), "7-Ch", 60, "Par"),
        ],
        # spots on the truss, pars in rows on the floor
        "positions": ([(500 + i * 700, 500, 2900) for i in range(8)] +
                      [(300 + (i % 12) * 480, 1500 + (i // 12) * 500, 200) for i in range(60)]),
        "options": {"nomenclature": "20minutes",
                    "style_path": os.path.join(CORPUS, "Pub_6fix.qxw")},
    },
}


def build(rig: str = "6fix") -> bytes:
    import app
    spec = RIGS[rig]
    c = app.create_app().test_client()
    c.post("/api/quickstart/clear")
    for qxf, mode, qty, name in spec["fixtures"]:
        r = c.post("/api/quickstart/load-qxf", json={"path": qxf})
        d = r.get_json()["definition"]
        key = d.get("key") or f"{d['manufacturer']}::{d['model']}"
        body = {"key": key, "quantity": qty, "name": name}
        if mode:
            body["mode"] = mode
        r = c.post("/api/quickstart/add-fixture", json=body)
        assert r.status_code == 200, r.get_data(as_text=True)
    c.post("/api/quickstart/auto-dmx")
    for i, (x, z, y) in enumerate(spec["positions"]):
        c.post("/api/quickstart/update-placement", json={"idx": i, "x": x, "z": z, "y": y})
    if spec["options"]:
        r = c.post("/api/quickstart/options", json=spec["options"])
        assert r.status_code == 200, r.get_data(as_text=True)
    r = c.post("/api/quickstart/generate", json={
        "project_name": spec["title"], "stage": STAGE})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.data


def golden_path(rig: str) -> str:
    return os.path.join(CORPUS, f"QuickStart_{rig}.qxw")


if __name__ == "__main__":
    args = sys.argv[1:]
    rigs = [args[0]] if args and args[0] in RIGS else list(RIGS)
    out = args[-1] if args and args[-1].endswith(".qxw") else None
    for rig in rigs:
        path = out or golden_path(rig)
        with open(path, "wb") as fh:
            fh.write(build(rig))
        print(path)
