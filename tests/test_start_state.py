"""The Start screen follows the state (3.9.5, DESIGN_v2.md section 7).

``skStartState`` in static/js/start_state.js is a pure function; these tests run
it with node and check the rule order: A no show, B a route in progress, C the
Doctor has errors, D changes not saved, E clean and saved.  The first rule that
fits wins and the others become small lines under it.
"""
import json
import os
import shutil
import subprocess
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")

ROUTE = {"title": "Adapt a show to a new venue", "step": 4, "total": 9, "label": "Groups"}


def state(**ctx):
    code = textwrap.dedent("""
        const {skStartState} = require(%r);
        process.stdout.write(JSON.stringify(skStartState(%s)));
    """) % (os.path.join(ROOT, "static", "js", "start_state.js"), json.dumps(ctx))
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def doc(e=0, w=0, kinds=0):
    return {"error": e, "warning": w,
            "rules": {"D%03d" % (i + 4): {"n": 1, "severity": "warning"} for i in range(kinds)}}


def test_a_no_show_open():
    s = state(loaded=False)
    assert s["state"] == "A"
    assert s["headline"] == ["Open a show to start"]
    assert s["notes"][0]["action"]["run"] == "go:quickstart"


def test_a_wins_over_everything_when_no_show_is_open():
    assert state(loaded=False, route=ROUTE, unsaved=3, doctor=doc(2))["state"] == "A"


def test_b_a_route_in_progress():
    s = state(loaded=True, name="Festival_14fix.qxw", route=ROUTE, unsaved=0, doctor=doc())
    assert s["state"] == "B"
    assert s["headline"] == ["You are on step {0} of {1} in {2}: {3}.", 4, 9, "Adapt a show to a new venue", "Groups"]
    assert [a["run"] for a in s["actions"]] == ["fn:routeContinue", "fn:routeClose"]
    assert s["actions"][0]["primary"] is True


def test_b_wins_over_errors_which_become_a_line():
    s = state(loaded=True, name="F.qxw", route=ROUTE, doctor=doc(1, 4, 2), unsaved=2)
    assert s["state"] == "B"
    texts = [n["text"][0] for n in s["notes"]]
    assert "{0} error to look at." in texts and "{0} changes are not saved." in texts


def test_c_errors_name_the_show_and_open_the_doctor():
    s = state(loaded=True, name="Festival_14fix.qxw", doctor=doc(1, 856, 4), unsaved=0)
    assert s["state"] == "C"
    assert s["headline"] == ["{0} has {1} error to look at.", "Festival_14fix.qxw", 1]
    assert s["actions"][0]["run"] == "go:doctor"
    # warnings are named by kind, not counted by place
    assert s["notes"][0]["text"] == ["Also: {0} kinds of warning, none blocks saving.", 4]


def test_c_plural_and_unsaved_line():
    s = state(loaded=True, name="F.qxw", doctor=doc(3), unsaved=1)
    assert s["headline"][0] == "{0} has {1} errors to look at."
    assert s["notes"][-1]["text"] == ["{0} change is not saved.", 1]


def test_d_unsaved_changes():
    s = state(loaded=True, name="F.qxw", doctor=doc(0, 5, 1), unsaved=3)
    assert s["state"] == "D"
    assert s["headline"] == ["{0} changes are not saved.", 3]
    assert [a["run"] for a in s["actions"]] == ["fn:showSave", "fn:showHistoryToggle"]
    assert s["notes"][0]["text"][0] == "Also: {0} kind of warning, it does not block saving."


def test_d_clean_show_with_unsaved_changes_shows_nothing_else():
    s = state(loaded=True, name="F.qxw", doctor=doc(), unsaved=1)
    assert s["state"] == "D" and s["notes"] == []


def test_e_clean_and_saved():
    s = state(loaded=True, name="Pub_6fix_v3.qxw", doctor=doc(), unsaved=0)
    assert s["state"] == "E"
    assert s["headline"] == ["{0} is ready. What next?", "Pub_6fix_v3.qxw"]
    assert s["actions"] == [] and s["notes"] == []


def test_e_without_a_doctor_result_is_still_ready():
    assert state(loaded=True, name="x.qxw", doctor=None, unsaved=0)["state"] == "E"


def test_every_text_is_a_pattern_for_the_languages():
    """No state builds a sentence by joining strings: parts are {0}, {1}, … in a pattern."""
    for ctx in ({"loaded": False}, {"loaded": True, "name": "a", "route": ROUTE, "doctor": doc(2, 1, 1), "unsaved": 2},
                {"loaded": True, "name": "a", "doctor": doc(1, 2, 2), "unsaved": 1}, {"loaded": True, "name": "a", "unsaved": 4}):
        s = state(**ctx)
        arrays = [s["headline"], s["sub"]] + [n["text"] for n in s["notes"]] + [a["label"] for a in s["actions"]]
        for arr in arrays:
            if arr:
                assert isinstance(arr[0], str) and arr[0].count("{") == len(arr) - 1, arr
