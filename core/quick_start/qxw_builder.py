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


def build_qxw(rig: list,
              functions: List[ET.Element],
              vc_frame: ET.Element,
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
        <Function> XML elements (scenes, chasers, etc.)
    vc_frame : ET.Element
        Root <Frame> for the Virtual Console.
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

    # Fixture group (flat grid)
    fg = _sub(engine, "FixtureGroup", ID="0")
    _sub(fg, "Name", "All Fixtures")
    size_el = _sub(fg, "Size", X=str(len(rig)), Y="1")
    for i in range(len(rig)):
        head = _sub(fg, "Head", X=str(i), Y="0", Fixture=str(i))
        head.text = "0"

    # Functions
    for func_el in functions:
        engine.append(func_el)

    # ── Virtual Console ───────────────────────────────────────────────────
    vc = _sub(root, "VirtualConsole")
    _sub(vc, "Properties")
    vc.append(vc_frame)

    # ── Monitor ───────────────────────────────────────────────────────────
    monitor = _sub(root, "Monitor")
    monitor.set("DisplayMode", "1")  # 3D
    monitor.set("ShowLabels", "1")

    grid_el = _sub(monitor, "Grid")
    grid_el.set("Width",  str(int(stage_w_mm / 1000)))
    grid_el.set("Height", str(int(stage_h_mm / 1000)))
    grid_el.set("Depth",  str(int(stage_d_mm / 1000)))
    grid_el.set("Units",  "0")  # metres

    # Default height: if fixture has no explicit height (y_mm == 0),
    # place it at ~90% of stage height (simulates truss/ceiling mount).
    default_y = int(stage_h_mm * 0.9)

    for i, e in enumerate(rig):
        y = int(e.get("y_mm", 0))
        if y == 0:
            y = default_y
        fxi = _sub(monitor, "FxItem",
                   ID=str(i),
                   XPos=str(int(e.get("x_mm", 0))),
                   YPos=str(y),
                   ZPos=str(int(e.get("z_mm", 0))),
                   XRot="65", YRot="0", ZRot="0")

    # ── Serialise ─────────────────────────────────────────────────────────
    xml_str = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE Workspace>\n' + xml_str).encode("utf-8")
