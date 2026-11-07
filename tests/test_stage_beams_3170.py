"""3.17.0: beams point where QLC+ points them, and the cabling plot shows the
stage size.  The rotations are those of a real show: ceiling spots tilted to
the audience, PARs on the PA stacks turned toward the middle, floor PARs aimed
up at a backdrop."""

import pytest

from core.cabling import outputs, plan
from core.stage3d import beam_direction

from tests.test_cabling_3150 import festival, radio_plan  # noqa: F401


@pytest.mark.parametrize("rot, want", [
    ((0, 0, 0), (0, -1, 0)),                       # straight down
    ((45, 0, 0), (0, -0.7071, 0.7071)),            # tilted toward the audience
    ((286, 82, 0), (0.9519, -0.2756, -0.1338)),    # stage-right PA stack (low X): toward the middle
    ((286, -81, 0), (-0.9494, -0.2756, -0.1504)),  # stage-left PA stack (high X): toward the middle
    ((304, 286, 4), (-0.834, -0.5022, -0.2285)),   # a wing PAR on the high X side, down to mid-stage
    ((31, -23, 0), (0.2012, -0.8572, 0.4741)),     # a ceiling spot on the left, down, forward and right
    ((220, -43, -10), (-0.5647, 0.6783, -0.4701)), # a floor PAR up at the backdrop, to the left
])
def test_beam_direction_as_qlc_plus(rot, want):
    got = beam_direction(rot)
    assert got == pytest.approx(want, abs=2e-4)
    assert sum(v * v for v in got) == pytest.approx(1, abs=2e-4)


def test_the_stage_fixture_list_carries_the_direction():
    import os
    from core import qxw_io, stage3d
    root = qxw_io.load_qxw(os.path.join(os.path.dirname(__file__), "corpus", "Festival_14fix.qxw"),
                           strip_namespace=True).getroot()
    fxs = stage3d.fixtures(root)
    assert fxs
    for f in fxs:
        assert f["dir"] == pytest.approx(list(beam_direction(f["rot"])))


def test_the_cabling_plot_shows_the_stage_size(festival):  # noqa: F811
    p, tx, rx = radio_plan()
    r = plan.with_extras(festival, p)
    sh, _ = outputs._drawing(plan.evaluate(p, festival), p, r)
    texts = [s[3] for s in sh if s[0] == "text"]
    assert "6 m wide" in texts and "4 m deep" in texts
    p["stage"] = {"w": 8000, "d": 5000}
    p = plan.clean_plan(p)
    sh, _ = outputs._drawing(plan.evaluate(p, festival), p, plan.with_extras(festival, p))
    texts = [s[3] for s in sh if s[0] == "text"]
    assert "8 m wide (tonight)" in texts and "5 m deep" in texts
