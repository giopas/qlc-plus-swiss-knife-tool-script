"""Tilt defaults for Quick Start 3D placement (WORKPLAN §3, 2026-09-23)."""
import xml.etree.ElementTree as ET

import pytest

from core.quick_start.qxw_builder import (
    _compute_orientation, build_qxw, default_x_rot, height_zone,
)

H, D = 4000, 6000          # stage height / depth (mm)
UP, DOWN = 1000, 5000      # upstage / downstage depth positions


@pytest.mark.parametrize("y,zone", [
    (0, "floor"), (599, "floor"), (600, "mid"), (2000, "mid"),
    (2600, "mid"), (2601, "truss"), (3600, "truss"),
])
def test_height_zone(y, zone):
    assert height_zone(y, H) == zone


@pytest.mark.parametrize("y,z,expected", [
    (3600, UP, 45),     # truss, upstage   -> down, tilted downstage
    (3600, DOWN, 315),  # truss, downstage -> down, tilted upstage
    (2000, UP, 90),     # mid, upstage     -> horizontal toward downstage
    (2000, DOWN, 270),  # mid, downstage   -> horizontal toward upstage
    (0, UP, 135),       # floor, upstage   -> uplight toward downstage
    (0, DOWN, 225),     # floor, downstage -> uplight toward upstage
])
def test_default_x_rot_per_zone(y, z, expected):
    assert default_x_rot(y, H, z, D) == expected


def test_centre_line_counts_as_downstage():
    assert default_x_rot(3600, H, D / 2, D) == 315


def test_unknown_depth_tilts_downstage():
    assert default_x_rot(3600, H) == 45
    assert default_x_rot(0, H) == 135


def test_no_default_points_straight_up_or_down():
    for y in (0, 2000, 3600):
        for z in (0, UP, DOWN, D):
            assert default_x_rot(y, H, z, D) not in (0, 180)


def test_overrides_win():
    assert _compute_orientation(3600, H, custom_x_rot=12, custom_y_rot=5,
                                custom_z_rot=-3, z_mm=UP, stage_d_mm=D) == (12, 5, -3)
    assert _compute_orientation(3600, H, z_mm=DOWN, stage_d_mm=D) == (315, 0, 0)


def test_build_qxw_writes_depth_aware_xrot():
    rig = [
        dict(name="T-up", x_mm=1000, z_mm=UP, y_mm=3600),
        dict(name="T-dn", x_mm=2000, z_mm=DOWN, y_mm=3600),
        dict(name="F-up", x_mm=3000, z_mm=UP, y_mm=0),
        dict(name="F-dn", x_mm=4000, z_mm=DOWN, y_mm=0),
        dict(name="Default", x_mm=5000, z_mm=DOWN),  # no height -> 90% truss
    ]
    data = build_qxw(rig, [], ET.Element("Frame"),
                     stage_w_mm=8000, stage_d_mm=D, stage_h_mm=H)
    root = ET.fromstring(data)
    ns = "{http://www.qlcplus.org/Workspace}"
    xr = [int(fx.get("XRot")) for fx in root.iter(f"{ns}FxItem")]
    assert xr == [45, 315, 135, 225, 315]


def test_fixtures_tool_keeps_the_tilt_instead_of_65(tmp_path):
    """Fixtures (core/fixture.py) wrote XRot=65 for every fixture; now the
    show's own tilt is kept and a new or default one follows the height."""
    import re
    from core import fixture, qxw_io
    root = qxw_io.load_qxw("tests/corpus/QuickStart_6fix.qxw")
    fixture.clear_rig()
    fixture.import_from_qxw(root)
    rig = fixture.get_rig()
    assert all("x_rot" not in e for e in rig)          # all defaults: automatic
    fixture.update_fixture(0, {"x_rot": 10})
    fixture.update_fixture(2, {"y_mm": 2900})           # floor → truss (stage 6 × 4 × 3 m)
    out = fixture.build_qxw(root).decode()
    rots = {m[0]: int(m[1]) for m in re.findall(r'<FxItem ID="(\d+)"[^>]*XRot="(\d+)"', out)}
    assert rots["0"] == 10
    assert rots["2"] == default_x_rot(2900, 3000, 3500, 4000) == 315   # follows the move
    assert 65 not in rots.values()
    again = qxw_io.loads_qxw(out.encode())
    fixture.clear_rig()
    fixture.import_from_qxw(again)
    assert fixture.get_rig()[0].get("x_rot") == 10
