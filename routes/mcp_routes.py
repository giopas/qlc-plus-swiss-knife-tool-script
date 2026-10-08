"""routes/mcp_routes.py — Settings › Connect to Claude (v2.9.0).

  GET  /api/mcp/config    → folders shared with Claude, and the snippet to paste into Claude's settings
  POST /api/mcp/folders   → {"folders": [...]}: the new list (only folders that exist are kept)
"""
import json
import os
import shlex
import subprocess
import sys

from flask import Blueprint, current_app, jsonify, request

from core import mcp_config, mcpb

bp = Blueprint("mcp", __name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch() -> dict:
    """The command Claude should start: {command, args}."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        if sys.platform == "win32":                      # the window app has no console: use the sibling
            mcp = os.path.join(os.path.dirname(exe), "QLC Swiss Knife MCP.exe")
            if os.path.isfile(mcp):
                exe = mcp
        return {"command": exe, "args": ["--mcp"]}
    return {"command": sys.executable, "args": [os.path.join(ROOT, "app.py"), "--mcp"]}


def claude_desktop_config() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json")
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming"),
                            "Claude", "claude_desktop_config.json")
    return os.path.join(home, ".config", "Claude", "claude_desktop_config.json")


@bp.route("/api/mcp/config")
def config():
    la = launch()
    mcp_config.write_launch(la)
    snippet = {"mcpServers": {"qlc-swiss-knife": la}}
    q = (lambda s: '"%s"' % s) if sys.platform == "win32" else shlex.quote
    return jsonify({
        "folders": mcp_config.load_folders(),
        "command": la["command"], "args": la["args"],
        "snippet": json.dumps(snippet, indent=2),
        "claude_code": "claude mcp add qlc-swiss-knife -- " + " ".join(q(x) for x in [la["command"]] + la["args"]),
        "claude_desktop_config": claude_desktop_config(),
    })


@bp.route("/api/mcp/folders", methods=["POST"])
def folders():
    body = request.get_json(silent=True) or {}
    lst = body.get("folders")
    if not isinstance(lst, list):
        return jsonify({"error": "folders must be a list."}), 400
    return jsonify({"folders": mcp_config.save_folders(lst)})


@bp.route("/api/mcp/install-bundle", methods=["POST"])
def install_bundle():
    """Write the Claude Desktop connection file (.mcpb) to Downloads and open it:
    Claude Desktop then shows its install dialog and asks which folders to share."""
    mcp_config.write_launch(launch())
    folder = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(folder):
        folder = os.path.expanduser("~")
    path = os.path.join(folder, mcpb.file_name())
    try:
        with open(path, "wb") as fh:
            fh.write(mcpb.build())
    except OSError as e:
        return jsonify({"error": f"Could not write {path}: {e.strerror}"}), 500
    opened = False
    if not current_app.config.get("TESTING"):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)                                    # noqa: S606 — the user's default app
            else:
                subprocess.Popen(["xdg-open", path])
            opened = True
        except Exception:                                             # noqa: BLE001
            opened = False
    return jsonify({"ok": True, "path": path, "opened": opened})
