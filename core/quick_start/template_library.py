"""
core/quick_start/template_library.py
=====================================
Pre-built skeleton templates for Quick Start QXW generation.

v0.8.0 ships with a minimal set — future versions will add curated
templates (e.g. "Concert", "DJ Set", "Theatre").
"""

from __future__ import annotations

from typing import Dict, List


# ═════════════════════════════════════════════════════════════════════════════
# Template definitions
# ═════════════════════════════════════════════════════════════════════════════

TEMPLATES: Dict[str, dict] = {
    "default": {
        "name":        "Default",
        "description": "Standard layout with macros, groups, scenes and effects.",
        "version":     "0.8.0",
    },
}


def list_templates() -> List[dict]:
    """Return available templates as a list of {id, name, description}."""
    return [
        {"id": tid, "name": t["name"], "description": t["description"]}
        for tid, t in TEMPLATES.items()
    ]


def get_template(template_id: str) -> dict:
    """Return a template definition by ID, or the default."""
    return TEMPLATES.get(template_id, TEMPLATES["default"])
