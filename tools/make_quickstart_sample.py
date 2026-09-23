"""Generate tests/corpus/QuickStart_6fix.qxw — a Quick Start output for the corpus.

Rig: 2 × Eurolite LED 4C-12 (truss) + 4 × Generic 7-Ch RGB PAR (floor), using
the corpus QXFs, driven through the real Flask routes.  Deterministic.

    python3 tools/make_quickstart_sample.py
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
CORPUS = os.path.join(REPO, "tests", "corpus")


def build() -> bytes:
    import app
    c = app.create_app().test_client()
    c.post("/api/quickstart/clear")
    keys = []
    for q in ("Eurolite-LED-4C-12-Silent-Slim-Spot.qxf", "Generic-7Ch-RGB-PAR.qxf"):
        r = c.post("/api/quickstart/load-qxf", json={"path": os.path.join(CORPUS, q)})
        d = r.get_json()["definition"]
        keys.append(d.get("key") or f"{d['manufacturer']}::{d['model']}")
    c.post("/api/quickstart/add-fixture", json={"key": keys[0], "quantity": 2, "name": "Ceiling"})
    c.post("/api/quickstart/add-fixture", json={"key": keys[1], "quantity": 4, "name": "Floor"})
    c.post("/api/quickstart/auto-dmx")
    pos = [(1500, 500, 2900), (4500, 500, 2900),
           (750, 3500, 200), (2250, 3500, 200), (3750, 3500, 200), (5250, 3500, 200)]
    for i, (x, z, y) in enumerate(pos):
        c.post("/api/quickstart/update-placement", json={"idx": i, "x": x, "z": z, "y": y})
    r = c.post("/api/quickstart/generate", json={
        "project_name": "QuickStart 6fix",
        "stage": {"w_mm": 6000, "d_mm": 4000, "h_mm": 3000}})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.data


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CORPUS, "QuickStart_6fix.qxw")
    data = build()
    with open(out, "wb") as fh:
        fh.write(data)
    print(out)
