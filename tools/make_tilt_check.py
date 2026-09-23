"""Generate tests/manual/tilt_check.qxw for the QLC+ 5 3D-view check (WORKPLAN 0.2).

Six Generic 7-Ch RGB PARs: truss / mid / floor, each once upstage and once
downstage.  Open in QLC+ 5 → 3D view: every beam should cross toward the
middle of the stage (none straight down/up).

    python3 tools/make_tilt_check.py
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.quick_start.qxw_builder import build_qxw  # noqa: E402

W, D, H = 6000, 4000, 3000
POS = [("Truss-Up", 1000, 500, 2900), ("Truss-Down", 1000, 3500, 2900),
       ("Mid-Up", 3000, 500, 1500), ("Mid-Down", 3000, 3500, 1500),
       ("Floor-Up", 5000, 500, 200), ("Floor-Down", 5000, 3500, 200)]


def main(out="tests/manual/tilt_check.qxw"):
    rig = [dict(manufacturer="Generic", model="7-Ch RGB LED PAR",
                mode="7 Channel", ch_count=7, name=n, universe=0,
                address=i * 7, x_mm=x, z_mm=z, y_mm=y)
           for i, (n, x, z, y) in enumerate(POS)]
    frame = ET.Element("{http://www.qlcplus.org/Workspace}Frame",
                       Caption="")
    data = build_qxw(rig, [], frame, stage_w_mm=W, stage_d_mm=D, stage_h_mm=H)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(data)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:])
