"""
core/quick_start/qxw_builder.py
================================
Build a complete, standalone QXW workspace from a rig definition +
generated VC layout.  Does NOT require a pre-existing template —
creates the full XML skeleton from scratch.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

QLC_NS_URI = "http://www.qlcplus.org/Workspace"
ET.register_namespace("", QLC_NS_URI)


def _ns(tag: str) -> str:
    return f"{{{QLC_NS_URI}}}{tag}"


def _sub(parent: ET.Element, tag: str, text: str = None, **attribs) -> ET.Element:
    el = ET.SubElement(parent, _ns(tag))
    if text is not None:
        el.text = str(text)
    for k, v in attribs.items():
        el.set(k, str(v))
    return el


# ── Show-lighting tilt defaults (WORKPLAN §3, decision 2026-09-23) ──────
# QLC+ 3D convention: XRot 0 = beam straight down, 90 = horizontal,
# 180 = straight up.  A positive XRot swings a hanging fixture's beam
# toward +Z (downstage / "Front"; Z = 0 is the back of the stage).
#
#   zone      upstage half (z < d/2)   downstage half (z >= d/2)
#   truss     45   (down, toward +Z)   315 (down, toward -Z)
#   mid       90   (horizontal, +Z)    270 (horizontal, -Z)
#   floor     135  (up, toward +Z)     225 (up, toward -Z)
#
# i.e. downstage fixtures tilt upstage and upstage fixtures tilt
# downstage, so beams cross the performance area instead of lighting
# only the floor or the ceiling.
FLOOR_RATIO = 0.15   # y / stage height below this  -> floor fixture
TRUSS_RATIO = 0.65   # y / stage height above this  -> truss/ceiling fixture
TILT_DEG = 45

_ZONE_XROT = {
    # zone: (upstage half, downstage half)
    "truss": (TILT_DEG, 360 - TILT_DEG),
    "mid":   (90, 270),
    "floor": (180 - TILT_DEG, 180 + TILT_DEG),
}


def height_zone(y_mm: float, stage_h_mm: float) -> str:
    """Classify a mounting height as ``'floor'``, ``'mid'`` or ``'truss'``."""
    ratio = y_mm / max(stage_h_mm, 1)
    if ratio < FLOOR_RATIO:
        return "floor"
    if ratio > TRUSS_RATIO:
        return "truss"
    return "mid"


def default_x_rot(y_mm: float, stage_h_mm: float,
                  z_mm: float = None, stage_d_mm: float = None) -> int:
    """Default XRot for a fixture from its height zone and depth position.

    Fixtures in the upstage half (``z < d/2``) tilt downstage (+Z); fixtures
    at or beyond the centre line tilt upstage (-Z).  When depth is unknown
    the fixture is treated as upstage (tilting toward the audience side).
    """
    upstage = (z_mm is None or stage_d_mm is None
               or z_mm < stage_d_mm / 2)
    up_val, down_val = _ZONE_XROT[height_zone(y_mm, stage_h_mm)]
    return up_val if upstage else down_val


def _compute_orientation(y_mm: int, stage_h_mm: int,
                         custom_x_rot=None, custom_y_rot=None,
                         custom_z_rot=None,
                         z_mm: int = None, stage_d_mm: int = None):
    """Return (XRot, YRot, ZRot) for a fixture.

    Per-axis overrides win; otherwise XRot comes from :func:`default_x_rot`
    (height zone + depth) and YRot/ZRot default to 0.
    """
    if custom_x_rot is not None:
        x_rot = int(custom_x_rot)
    else:
        x_rot = default_x_rot(y_mm, stage_h_mm, z_mm, stage_d_mm)
    y_rot = int(custom_y_rot) if custom_y_rot is not None else 0
    z_rot = int(custom_z_rot) if custom_z_rot is not None else 0
    return x_rot, y_rot, z_rot


def build_qxw(rig: list,
              functions: List[ET.Element],
              vc_frame: ET.Element,
              fixture_groups: List[ET.Element] = None,
              stage_w_mm: int = 8000,
              stage_d_mm: int = 6000,
              stage_h_mm: int = 4000) -> bytes:
    """
    Build a complete .qxw XML file.

    Parameters
    ----------
    rig : list[dict]
        Fixture entries with: manufacturer, model, mode, ch_count, name,
        universe (0-indexed), address (0-indexed), x_mm, z_mm, y_mm
    functions : list[ET.Element]
        <Function> XML elements (scenes, chasers, RGBMatrix, etc.)
    vc_frame : ET.Element
        Root <Frame> for the Virtual Console.
    fixture_groups : list[ET.Element] | None
        Additional <FixtureGroup> elements (for RGBMatrix, etc.).
        Group ID=0 ("All Fixtures") is always created automatically.
    stage_w_mm, stage_d_mm, stage_h_mm : int
        Stage dimensions in millimetres.

    Returns
    -------
    bytes   UTF-8 encoded QXW XML content.
    """
    root = ET.Element(_ns("Workspace"))

    _sub(root, "Creator")
    creator = root.find(_ns("Creator"))
    _sub(creator, "Name", "QLC+ Swiss Knife — Quick Start")
    _sub(creator, "Version", "4.13.1")
    _sub(creator, "Author", "Swiss Knife Quick Start Generator")

    # ── Engine ────────────────────────────────────────────────────────────
    engine = _sub(root, "Engine")

    # InputOutputMap (minimal — user configures in QLC+)
    iom = _sub(engine, "InputOutputMap")
    # Create universes referenced by the rig
    universes_used = set()
    for e in rig:
        universes_used.add(e.get("universe", 0))
    for uni in sorted(universes_used):
        u = _sub(iom, "Universe", Name=f"Universe {uni + 1}", ID=str(uni))
        _sub(u, "Output", Plugin="None")

    # Fixtures
    for i, e in enumerate(rig):
        fx = ET.SubElement(engine, _ns("Fixture"))
        _sub(fx, "Manufacturer", e.get("manufacturer", "Unknown"))
        _sub(fx, "Model",        e.get("model", "Unknown"))
        _sub(fx, "Mode",         e.get("mode", "Default"))
        _sub(fx, "ID",           str(i))
        _sub(fx, "Name",         e.get("name", f"Fixture {i}"))
        _sub(fx, "Universe",     str(e.get("universe", 0)))
        _sub(fx, "Address",      str(e.get("address", 0)))
        _sub(fx, "Channels",     str(e.get("ch_count", 1)))

    # Fixture group — "All Fixtures" (flat grid, ID=0)
    fg = _sub(engine, "FixtureGroup", ID="0")
    _sub(fg, "Name", "All Fixtures")
    _sub(fg, "Size", X=str(len(rig)), Y="1")
    for i in range(len(rig)):
        head = _sub(fg, "Head", X=str(i), Y="0", Fixture=str(i))
        head.text = "0"

    # Additional fixture groups (for RGBMatrix, etc.)
    if fixture_groups:
        for fg_el in fixture_groups:
            engine.append(fg_el)

    # Functions
    for func_el in functions:
        engine.append(func_el)

    # ── Monitor (MUST be inside Engine — QLC+ parses it here) ─────────────
    monitor = _sub(engine, "Monitor")
    monitor.set("DisplayMode", "1")  # 3D
    monitor.set("ShowLabels", "1")

    grid_el = _sub(monitor, "Grid")
    grid_el.set("Width",  str(int(stage_w_mm / 1000)))
    grid_el.set("Height", str(int(stage_h_mm / 1000)))
    grid_el.set("Depth",  str(int(stage_d_mm / 1000)))
    grid_el.set("Units",  "0")  # metres
    grid_el.set("POV",    "1")  # perspective view — needed for QLC+ to use dims

    # StageItem — tells QLC+ to render the stage floor
    _sub(monitor, "StageItem", "1")

    # Default height: if fixture has no explicit height (y_mm is None),
    # place it at ~90% of stage height (simulates truss/ceiling mount).
    default_y = int(stage_h_mm * 0.9)

    for i, e in enumerate(rig):
        raw_y = e.get("y_mm")
        if raw_y is None:
            y = default_y
        else:
            y = int(raw_y)

        # Corner-origin coordinates (QLC+ uses all-positive values)
        raw_x = int(e.get("x_mm", 0))
        raw_z = int(e.get("z_mm", 0))

        # Orientation: custom overrides or height-based auto
        x_rot, y_rot, z_rot = _compute_orientation(
            y, stage_h_mm,
            custom_x_rot=e.get("x_rot"),
            custom_y_rot=e.get("y_rot"),
            custom_z_rot=e.get("z_rot"),
            z_mm=raw_z, stage_d_mm=stage_d_mm,
        )

        fxi = _sub(monitor, "FxItem",
                   ID=str(i),
                   XPos=str(raw_x),
                   YPos=str(y),
                   ZPos=str(raw_z),
                   XRot=str(x_rot),
                   YRot=str(y_rot),
                   ZRot=str(z_rot))

    # ── Virtual Console ───────────────────────────────────────────────────
    vc = _sub(root, "VirtualConsole")
    vc.append(vc_frame)
    props = _sub(vc, "Properties")
    _sub(props, "Size", Width="1920", Height="1080")
    _sub(props, "GrandMaster", ChannelMode="Intensity",
         ValueMode="Reduce", SliderMode="Normal")

    # ── Simple Desk (empty — user populates in QLC+) ─────────────────────
    sd = _sub(root, "SimpleDesk")
    _sub(sd, "Engine")

    # ── Serialise ─────────────────────────────────────────────────────────
    xml_str = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE Workspace>\n' + xml_str).encode("utf-8")
