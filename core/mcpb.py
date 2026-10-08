"""core/mcpb.py — the one-file way to connect Claude Desktop (v2.9.0).

``build()`` returns a ``.mcpb`` ("MCP bundle"): a small zip that Claude Desktop installs
with a double-click, asking which folders to share.  It holds no Swiss Knife code, only
a tiny launcher (``server/index.js``, run by the Node that Claude Desktop itself carries)
that starts the Swiss Knife you installed with ``--mcp`` and one ``--folder`` per folder
chosen at install.  The launcher finds the program from ``~/.qlc_swiss_knife/mcp-launch.json``
(Swiss Knife rewrites it every time it starts, so moving or updating the app needs nothing
in Claude) and, failing that, from the usual install places.
"""

from __future__ import annotations

import io
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/giopas/qlc-plus-swiss-knife-tool-script"

LAUNCHER = r"""#!/usr/bin/env node
'use strict';
// Starts QLC+ Swiss Knife as an MCP server (stdio). Arguments: the folders to share.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

function fromLaunchFile() {
  try {
    const f = path.join(os.homedir(), '.qlc_swiss_knife', 'mcp-launch.json');
    const j = JSON.parse(fs.readFileSync(f, 'utf8'));
    if (j && j.command && fs.existsSync(j.command)) return { command: j.command, args: j.args || ['--mcp'] };
  } catch (e) { /* not written yet */ }
  return null;
}

function fromUsualPlaces() {
  const h = os.homedir();
  const c = [];
  if (process.platform === 'darwin') {
    for (const base of ['/Applications', path.join(h, 'Applications')])
      c.push(path.join(base, 'QLC Swiss Knife.app', 'Contents', 'MacOS', 'QLC Swiss Knife'));
  } else if (process.platform === 'win32') {
    const la = process.env.LOCALAPPDATA || path.join(h, 'AppData', 'Local');
    c.push(path.join(la, 'Programs', 'QLC Swiss Knife', 'QLC Swiss Knife MCP.exe'));
    for (const pf of [process.env.ProgramFiles, process.env['ProgramFiles(x86)']])
      if (pf) c.push(path.join(pf, 'QLC Swiss Knife', 'QLC Swiss Knife MCP.exe'));
  } else {
    c.push(path.join(h, 'QLC-Swiss-Knife', 'QLC-Swiss-Knife'), '/opt/QLC-Swiss-Knife/QLC-Swiss-Knife');
  }
  const hit = c.find((p) => fs.existsSync(p));
  return hit ? { command: hit, args: ['--mcp'] } : null;
}

const target = fromLaunchFile() || fromUsualPlaces();
if (!target) {
  process.stderr.write('QLC+ Swiss Knife was not found. Install it, start it once, then restart Claude.\n');
  process.exit(1);
}
const folders = process.argv.slice(2).filter((a) => a && !a.startsWith('${'));
const args = target.args.slice();
for (const f of folders) args.push('--folder', f);

const child = spawn(target.command, args, { stdio: 'inherit' });
child.on('error', (e) => { process.stderr.write('Could not start Swiss Knife: ' + e.message + '\n'); process.exit(1); });
child.on('exit', (code, signal) => process.exit(signal ? 1 : (code === null ? 0 : code)));
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => child.kill(s));
"""


def manifest(version: str) -> dict:
    from core import mcp_server
    tools = [{"name": t["name"], "description": mcp_server.TITLES.get(t["name"], t["name"])}
             for t in mcp_server.TOOLS]
    return {
        "manifest_version": "0.3",
        "name": "qlc-swiss-knife",
        "display_name": "QLC+ Swiss Knife",
        "version": version,
        "description": "Let Claude open, check, fix and build on your QLC+ shows with Swiss Knife.",
        "long_description": (
            "Connects Claude to the QLC+ Swiss Knife you have installed. Claude can open a show, run the "
            "Doctor, shrink a rig, port functions, build looks and chasers, edit the Virtual Console, apply "
            "a setlist, compare shows and draft the Dictionary descriptions. It only sees the folders you "
            "choose here, and always saves a NEW file: your originals are never changed. "
            "Install and start QLC+ Swiss Knife (2.9 or later) once before using it."),
        "author": {"name": "giopas", "url": REPO},
        "repository": {"type": "git", "url": REPO + ".git"},
        "homepage": REPO,
        "documentation": REPO + "/wiki/Connect-Claude-to-Swiss-Knife",
        "support": REPO + "/issues",
        "icon": "icon.png",
        "server": {
            "type": "node",
            "entry_point": "server/index.js",
            "mcp_config": {"command": "node",
                           "args": ["${__dirname}/server/index.js", "${user_config.folders}"]},
        },
        "tools": tools,
        "tools_generated": False,
        "keywords": ["qlc+", "lighting", "dmx", "show files"],
        "license": "MIT",
        "user_config": {
            "folders": {
                "type": "directory", "title": "Folders with your shows", "multiple": True, "required": True,
                "description": "Claude can only open files in these folders (and their subfolders), "
                               "and saves its work there as new files.",
            }
        },
        "compatibility": {"claude_desktop": ">=0.10.0", "platforms": ["darwin", "win32", "linux"],
                          "runtimes": {"node": ">=16.0.0"}},
    }


def build(version: str | None = None) -> bytes:
    if version is None:
        from core.workspace import VERSION as version
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest(version), indent=2, ensure_ascii=False) + "\n")
        z.writestr("server/index.js", LAUNCHER)
        icon = os.path.join(ROOT, "static", "logo", "icon-512.png")
        if os.path.isfile(icon):
            z.write(icon, "icon.png")
    return buf.getvalue()


def file_name(version: str | None = None) -> str:
    if version is None:
        from core.workspace import VERSION as version
    return f"QLC-Swiss-Knife-{version}-claude.mcpb"
