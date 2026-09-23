"""Quick Start is deterministic: regenerating each reference rig is
byte-identical to its golden file, and every golden file passes Doctor
with zero errors and zero warnings (WORKPLAN Phase 1.1)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import make_quickstart_sample  # noqa: E402
from core.doctor import check_file, load_qxf_defs  # noqa: E402

RIGS = sorted(make_quickstart_sample.RIGS)


@pytest.mark.parametrize("rig", RIGS)
def test_quickstart_golden(rig):
    with open(make_quickstart_sample.golden_path(rig), "rb") as fh:
        expected = fh.read()
    assert make_quickstart_sample.build(rig) == expected, (
        f"Quick Start output for '{rig}' changed. If intended, run "
        "`python tools/make_quickstart_sample.py` and update expected_baseline.json.")


@pytest.mark.parametrize("rig", RIGS)
def test_quickstart_golden_is_doctor_clean(rig):
    defs = load_qxf_defs([os.path.join(HERE, "corpus"), os.path.join(HERE, "fixtures")])
    rep = check_file(make_quickstart_sample.golden_path(rig), defs)
    bad = [f"{f.code} {f.location}: {f.message}" for f in rep.errors + rep.warnings]
    assert not bad, bad
    assert not rep.by_code("I003"), "all fixture definitions must be known"
