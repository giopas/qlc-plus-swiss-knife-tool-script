"""Opt-in: run the Quick Start golden files in a real QLC+ (tools/qlc_check.py).

Skipped unless QLCPLUS_BIN points at a QLC+ binary and websocket-client is
installed, so CI stays fast and self-contained.  Locally on macOS::

    QLCPLUS_BIN=/Applications/QLC+.app/Contents/MacOS/qlcplus-qml pytest tests/test_qlc_live.py -v
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

pytest.importorskip("websocket")
QLC = os.environ.get("QLCPLUS_BIN")
pytestmark = pytest.mark.skipif(not QLC, reason="set QLCPLUS_BIN to run live QLC+ checks")


@pytest.mark.parametrize("rig", ["club", "multiuni"])
def test_quickstart_in_real_qlcplus(rig):
    import qlc_check
    path = os.path.join(HERE, "corpus", f"QuickStart_{rig}.qxw")
    args = [path, "--qlc", QLC]
    if sys.platform.startswith("linux"):
        args.append("--offscreen")
    assert qlc_check.main(args) == 0
