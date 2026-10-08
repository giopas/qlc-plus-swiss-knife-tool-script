#!/usr/bin/env python3
"""Write the Claude Desktop connection file:  python tools/make_mcpb.py [folder]
→ <folder>/QLC-Swiss-Knife-<version>-claude.mcpb  (default: release/)"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import mcpb  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "release")
os.makedirs(out, exist_ok=True)
path = os.path.join(out, mcpb.file_name())
with open(path, "wb") as fh:
    fh.write(mcpb.build())
print(path)
