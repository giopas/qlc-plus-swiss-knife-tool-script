"""Quick Start is deterministic: regenerating the corpus sample is byte-identical
(WORKPLAN Phase 1.1 golden files — first reference rig)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import make_quickstart_sample  # noqa: E402


def test_quickstart_golden_6fix():
    golden = os.path.join(HERE, "corpus", "QuickStart_6fix.qxw")
    with open(golden, "rb") as fh:
        expected = fh.read()
    assert make_quickstart_sample.build() == expected, (
        "Quick Start output changed. If intended, run "
        "`python tools/make_quickstart_sample.py` and update expected_baseline.json.")
