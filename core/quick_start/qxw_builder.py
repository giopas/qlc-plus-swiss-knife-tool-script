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


def _compute_orientation(y_mm: int, stage_h_mm: int,
                         custom_x_rot=None, custom_y_rot=None,
                         custom_z_rot=None):
    """Return (XRot, YRot, ZRot) for a fixture based on height or overrides."""
    if custom_x_rot is not None:
        x_rot = int(custom_x_rot)
    else:
        ratio = y_mm / max(stage_h_mm, 1)
        if ratio < 0.15:
            x_rot = 180   # point straight up (floor fixture)
        elif ratio > 0.65:
            x_rot = 0     # point straight down (top fixture)
        else:
            x_rot = 90    # horizontal beam (mid-height)
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
