"""Live QLC+ check — open a workspace in a real QLC+ and press its buttons.

Reading the XML can't tell you how QLC+ actually *behaves*.  This tool
starts QLC+ with its web interface (``-w``), talks to it over the
web-socket API and checks the result on the DMX output:

1. **VC loaded** — every Virtual Console widget in the file is present in
   the running QLC+ (catches widgets silently dropped by the loader).
2. **Buttons light up + PANIC RESET** — for every Toggle button that runs a
   function: press it and check that at least one fixture lights up (not for
   BLACKOUT); press PANIC RESET and check that every fixture channel equals
   the *Reset: neutral state* scene; press PANIC RESET again and check it
   still holds (catches the "every second press does nothing" bug).

Fixture definitions: QLC+ must know every fixture (installed, or a
``<Manufacturer>-<Model>.qxf`` next to the workspace — Quick Start writes
them there).  Unknown fixtures load as generic dimmers and colour/matrix
buttons stay dark, which check 2 reports.

It found four real bugs on 23 Sep 2026 (script never ending in QLC+ 5,
QLC+ 5.2.2 dropping script commands, a Level slider holding dimmers at
full, a Submaster slider dropping the VC).

Usage::

    # macOS, QLC+ installed in /Applications (quit QLC+ first)
    python3 tools/qlc_check.py tests/corpus/QuickStart_club.qxw

    # any QLC+ binary (Linux build, QLC+ 4, ...)
    python3 tools/qlc_check.py show.qxw --qlc /path/to/qlcplus

    # QLC+ already running with web access (started with -w)
    python3 tools/qlc_check.py show.qxw --no-launch

Needs ``pip install websocket-client``.  Exit code 0 = all checks passed.
Works with QLC+ 4.12+ and 5.x (web API ``QLC+API|getChannelsValues``).
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

NS = "{http://www.qlcplus.org/Workspace}"
WIDGET_TAGS = {"Button", "Slider", "Frame", "SoloFrame", "Label", "XYPad",
               "CueList", "Knob", "SpeedDial", "AudioTriggers", "Clock",
               "Matrix", "Animation"}
MAC_BINARIES = ("/Applications/QLC+.app/Contents/MacOS/qlcplus-qml",
                "/Applications/QLC+.app/Contents/MacOS/qlcplus")


# ── workspace model ──────────────────────────────────────────────────────────

class Workspace:
    def __init__(self, path: str):
        root = ET.parse(path).getroot()
        eng = root.find(f"{NS}Engine")
        self.fixtures = {}                      # id -> (universe, address)
        self.owner = {}                         # (universe, abs address) -> fixture id
        for fx in eng.findall(f"{NS}Fixture"):
            self.fixtures[fx.findtext(f"{NS}ID")] = (
                int(fx.findtext(f"{NS}Universe") or 0),
                int(fx.findtext(f"{NS}Address") or 0))
            u, ad = self.fixtures[fx.findtext(f"{NS}ID")]
            for c in range(int(fx.findtext(f"{NS}Channels") or 0)):
                self.owner[(u, ad + c)] = fx.findtext(f"{NS}ID")
        self.functions = {f.get("ID"): f for f in eng.findall(f"{NS}Function")}
        vc = root.find(f"{NS}VirtualConsole")
        self.widgets = {}                       # id -> (tag, caption), pages excluded
        pages = {el.get("ID") for el in (vc if vc is not None else [])}
        self.buttons = []                       # (id, caption, function id, action)
        for el in vc.iter() if vc is not None else ():
            tag = el.tag.replace(NS, "")
            if tag in WIDGET_TAGS and el.get("ID") is not None and el.get("ID") not in pages:
                self.widgets[el.get("ID")] = (tag, el.get("Caption", ""))
            if tag == "Button":
                fn = el.find(f"{NS}Function")
                self.buttons.append((el.get("ID"), (el.get("Caption") or "").replace("\n", " "),
                                     fn.get("ID") if fn is not None else None,
                                     el.findtext(f"{NS}Action") or "Toggle"))

    def scene_output(self, fid: str) -> dict:
        """{(universe, absolute address): value} a scene writes."""
        out = {}
        for fv in self.functions[fid].findall(f"{NS}FixtureVal"):
            uni, addr = self.fixtures[fv.get("ID")]
            nums = [int(x) for x in (fv.text or "").split(",") if x.strip()]
            for ch, val in zip(nums[0::2], nums[1::2]):
                out[(uni, addr + ch)] = val
        return out

    def fade_out_ms(self, fid: str, _seen=None) -> int:
        """Longest fade-out in a function and everything it runs (chaser
        steps, collection members): how long QLC+ may still be fading after
        the function is stopped."""
        _seen = _seen if _seen is not None else set()
        f = self.functions.get(fid)
        if f is None or fid in _seen:
            return 0
        _seen.add(fid)
        best = 0
        sp = f.find(f"{NS}Speed")
        if sp is not None and (sp.get("FadeOut") or "").isdigit():
            best = int(sp.get("FadeOut"))
        for st in f.findall(f"{NS}Step"):
            if (st.get("FadeOut") or "").isdigit():
                best = max(best, int(st.get("FadeOut")))
            best = max(best, self.fade_out_ms((st.text or "").strip(), _seen))
        return best

    def find_function(self, name_part: str):
        for fid, f in self.functions.items():
            if name_part.lower() in (f.get("Name") or "").lower():
                return fid
        return None


# ── QLC+ connection ──────────────────────────────────────────────────────────

class QLC:
    def __init__(self, port: int):
        import websocket  # pip install websocket-client
        deadline = time.time() + 40
        while True:
            try:
                self.ws = websocket.create_connection(f"ws://127.0.0.1:{port}/qlcplusWS", timeout=5)
                break
            except OSError:
                if time.time() > deadline:
                    raise SystemExit(f"QLC+ web access not reachable on port {port}")
                time.sleep(1)

    def api(self, *args) -> list:
        self.ws.send("QLC+API|" + "|".join(str(a) for a in args))
        while True:
            msg = self.ws.recv()
            if msg.startswith(f"QLC+API|{args[0]}|"):
                return msg.split("|")[2:]

    def widget_ids(self) -> set:
        parts = self.api("getWidgetsList")
        return {parts[i] for i in range(0, len(parts) - 1, 2) if parts[i].isdigit()}

    def press(self, wid: str, settle: float) -> None:
        self.ws.send(f"{wid}|255")
        time.sleep(settle)

    def universe(self, uni: int, count: int = 512) -> dict:
        """{absolute address (0-based): value}.  Handles the 3-field (QLC+ 4.12)
        and 4-field (4.14 / 5.x) record formats."""
        t = self.api("getChannelsValues", uni + 1, 1, count)
        out, i, addr = {}, 0, 1
        while i + 1 < len(t) and addr <= count:
            if t[i] != str(addr):
                break
            out[addr - 1] = int(t[i + 1])
            step = 4 if i + 4 < len(t) and t[i + 4] == str(addr + 1) else 3
            i += step
            addr += 1
        return out


# ── checks ───────────────────────────────────────────────────────────────────

def check_vc_loaded(ws: Workspace, qlc: QLC) -> list:
    loaded = qlc.widget_ids()
    missing = sorted((w for w in ws.widgets if w not in loaded), key=int)
    return [f"VC widget {w} '{ws.widgets[w][1]}' ({ws.widgets[w][0]}) not loaded by QLC+"
            for w in missing]


def check_panic_reset(ws: Workspace, qlc: QLC, settle: float) -> list:
    reset_btn = next((b for b in ws.buttons if "panic" in b[1].lower() and "reset" in b[1].lower()), None)
    neutral_fid = ws.find_function("Reset: neutral state")
    if reset_btn is None or neutral_fid is None:
        return ["no PANIC RESET button / 'Reset: neutral state' scene — skipped"]
    expected = ws.scene_output(neutral_fid)
    universes = sorted({u for u, _ in expected})
    targets = [b for b in ws.buttons
               if b[3] == "Toggle" and b[2] and b[0] != reset_btn[0]
               and ws.functions.get(b[2]) is not None]
    errors = []

    def compare(label, deadline=0.0):
        """Compare with the neutral state; retry until *deadline* (time.time())
        so looks with a fade-out can finish fading first."""
        while True:
            got = {}
            for u in universes:
                for a, v in qlc.universe(u).items():
                    got[(u, a)] = v
            bad = [(k, v, got.get(k)) for k, v in sorted(expected.items()) if got.get(k) != v]
            if not bad or time.time() >= deadline:
                break
            time.sleep(0.3)
        if bad:
            sample = ", ".join(f"U{u + 1}.{a + 1}={g} (want {w})" for (u, a), w, g in bad[:6])
            errors.append(f"{label}: {len(bad)} channel(s) differ — {sample}")
            return False
        return True

    # "Light" channels per fixture: what ALL ON drives above the neutral state
    all_on = ws.find_function("ALL ON")
    light = {}
    if all_on:
        for key, v in ws.scene_output(all_on).items():
            if v > 0 and expected.get(key, 0) == 0:
                light.setdefault(ws.owner.get(key), []).append(key)

    def lit() -> bool:
        got = {}
        for u in universes:
            for a, v in qlc.universe(u).items():
                got[(u, a)] = v
        for chans in light.values():
            on = sum(1 for k in chans if got.get(k, 0) > 0)
            if on >= min(2, len(chans)):
                return True
        return False

    for wid, caption, fid, _ in targets:
        qlc.press(wid, settle)
        dark_ok = any(w in caption.lower() for w in ("blackout", "off"))
        if light and not dark_ok:
            seen = lit()
            for _ in range(4):
                if seen:
                    break
                time.sleep(0.3)
                seen = lit()
            if not seen:
                errors.append(f"'{caption}': no fixture lights up (all DMX intensity/colour at 0)")
                print(f"  DARK {caption}")
        qlc.press(reset_btn[0], settle)
        fade = ws.fade_out_ms(fid) / 1000.0     # stopped looks fade out first
        ok = compare(f"'{caption}' → PANIC RESET", time.time() + fade + 0.5)
        qlc.press(reset_btn[0], settle)
        ok = compare(f"'{caption}' → PANIC RESET ×2") and ok
        print(f"  {'ok  ' if ok else 'FAIL'} {caption}")
    return errors


# ── main ─────────────────────────────────────────────────────────────────────

def find_binary(given: str | None) -> str:
    if given:
        return given
    env = os.environ.get("QLCPLUS_BIN")
    if env:
        return env
    if platform.system() == "Darwin":
        for b in MAC_BINARIES:
            if os.path.exists(b):
                return b
    for name in ("qlcplus-qml", "qlcplus5", "qlcplus"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("QLC+ not found — pass --qlc /path/to/qlcplus or set QLCPLUS_BIN")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("qxw")
    ap.add_argument("--qlc", help="QLC+ binary (default: QLCPLUS_BIN, /Applications/QLC+.app, PATH)")
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--no-launch", action="store_true", help="use a QLC+ already running with -w")
    ap.add_argument("--settle", type=float, default=0.8, help="seconds to wait after each press")
    ap.add_argument("--offscreen", action="store_true",
                    help="no window (Linux / CI: QT_QPA_PLATFORM=offscreen)")
    a = ap.parse_args(argv)

    ws = Workspace(a.qxw)
    proc = None
    if not a.no_launch:
        binary = find_binary(a.qlc)
        env = dict(os.environ)
        if a.offscreen:
            env["QT_QPA_PLATFORM"] = "offscreen"
        log = tempfile.NamedTemporaryFile("w", suffix="-qlcplus.log", delete=False)
        print(f"Starting {binary}  (log: {log.name})")
        cmd = [binary, "-o", os.path.abspath(a.qxw), "-w", "-d"]
        if a.port != 9999:
            cmd += ["-wp", str(a.port)]
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        time.sleep(3)
    try:
        qlc = QLC(a.port)
        time.sleep(2)                           # let the workspace finish loading
        print(f"Workspace: {os.path.basename(a.qxw)} — {len(ws.fixtures)} fixtures, "
              f"{len(ws.functions)} functions, {len(ws.widgets)} VC widgets")
        errors = []
        print("[1] Virtual Console loaded")
        e = check_vc_loaded(ws, qlc)
        errors += e
        print("  ok" if not e else "\n".join("  FAIL " + x for x in e))
        print("[2] every button lights up; PANIC RESET after every button")
        errors += check_panic_reset(ws, qlc, a.settle)
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
    real = [e for e in errors if not e.endswith("skipped")]
    print("\nRESULT:", "PASS" if not real else f"FAIL ({len(real)})")
    for e in errors:
        print("  -", e)
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
