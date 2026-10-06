"""v2.8.6 — a cp1252 console (Windows) or a missing stdout must not stop the app."""
import io
import sys

from core import console


def test_cp1252_stream_prints_the_bolt(monkeypatch):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    console.make_stdio_safe()
    print("\n⚡  QLC+ Swiss Knife  →  http://127.0.0.1:5731  ⚠")
    sys.stdout.flush()
    assert "⚡".encode("utf-8") in raw.getvalue()


def test_missing_stdout_is_replaced(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    console.make_stdio_safe()
    print("⚡")                       # does not raise
    sys.stderr.write("⚠")


def test_app_calls_it_before_anything_else():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
               encoding="utf-8").read()
    assert src.index("make_stdio_safe()") < src.index("import flask as _flask_check")
