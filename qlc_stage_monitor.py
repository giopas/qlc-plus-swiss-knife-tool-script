#!/usr/bin/env python3
"""Start QLC+ Stage Monitor from the sources (the packaged app needs nothing):

    python3 qlc_stage_monitor.py [--folder <exported folder>]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_app.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
