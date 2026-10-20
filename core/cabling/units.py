"""
core/cabling/units.py — metres or feet
======================================

Lengths are kept in metres everywhere (the kit, the plan, the routes).  What
the user reads is in their unit, a setting of their kit (``units``: ``m`` or
``ft``).  The caller sets it for the work in hand with :func:`use`; every text
the planner writes formats a length with :func:`fmt`.
"""

from __future__ import annotations

import contextlib
import contextvars

FT = 0.3048
UNITS = ("m", "ft")
# lengths cables are sold in, for the shopping list
BUY_M = (1.5, 3, 5, 10, 15, 20, 25, 30, 50)
BUY_FT = (3, 5, 10, 15, 25, 35, 50, 75, 100, 150)

_cur: contextvars.ContextVar = contextvars.ContextVar("cabling_units", default="m")


def current() -> str:
    return _cur.get()


@contextlib.contextmanager
def use(units: str):
    token = _cur.set(units if units in UNITS else "m")
    try:
        yield
    finally:
        _cur.reset(token)


def fmt(m: float, units: str = "") -> str:
    """``"10 m"`` or ``"33 ft"``."""
    u = units or _cur.get()
    if u == "ft":
        ft = m / FT
        v = round(ft) if ft >= 10 or abs(ft - round(ft)) < 0.05 else round(ft, 1)
        return f"{v:g} ft"
    return f"{round(m, 2):g} m"


def buy_lengths_m(units: str = "") -> tuple:
    u = units or _cur.get()
    return tuple(round(f * FT, 2) for f in BUY_FT) if u == "ft" else BUY_M
