"""Cabling 3.16.0: your decisions kept.  Fixtures sent by radio stay by radio
when the planner proposes again, and a plan can be approved, compared with and
gone back to."""

import copy

from core.cabling import auto, plan

from tests.test_cabling_3150 import festival, radio_plan  # noqa: F401  (the fixture and the plan)


def _radio_ids(ev):
    return {f["id"] for f in ev["fixtures"] if f.get("radio")}


def test_propose_keeps_the_fixtures_sent_by_radio(festival):  # noqa: F811
    p, tx, rx = radio_plan()
    assert [g["devices"][1] for g in plan.radio_groups(p)] == [{"fixture": "0"}, {"fixture": "5"}]
    alts = auto.alternatives(p, festival)
    assert alts
    for a in alts:
        ev = a["evaluation"]
        assert _radio_ids(ev) == {"0", "5"}, a["name"]
        assert a["radio_kept"] == 2 and "2 by radio, as you chose" in a["note"]
        allis = ev["issues"] + [i for w in ev["chains"] for i in w["issues"]]
        assert not any(i["code"] == "C006" and "Not on any chain" in i["text"] for i in allis), a["name"]
        radio = [c for c in a["plan"]["chains"] if c["source"]["item"] == tx]
        assert [c["devices"][0]["item"] for c in radio] == [rx, rx]
        assert sum(1 for c in a["plan"]["chains"] for d in c["devices"] if d.get("item") == tx) == 1
    assert [a["key"] for a in alts] == list("ABCDEF"[:len(alts)])


def test_propose_without_radio_is_as_before(festival):  # noqa: F811
    p, tx, rx = radio_plan()
    p["chains"] = p["chains"][:3]
    for a in auto.alternatives(p, festival):
        assert "radio_kept" not in a and not _radio_ids(a["evaluation"])


def test_approve_compare_and_go_back(festival):  # noqa: F811
    p, tx, rx = radio_plan()
    ok = plan.approve(p, "2026-11-07T18:02")
    assert plan.evaluate(ok, festival)["approved"] == {"at": "2026-11-07T18:02", "same": True, "chains": 6}
    moved = copy.deepcopy(ok)
    moved["chains"][1]["devices"].reverse()
    st = plan.evaluate(moved, festival)["approved"]
    assert st["same"] is False
    back = plan.back_to_approved(moved)
    assert back["chains"] == ok["chains"] and plan.evaluate(back, festival)["approved"]["same"]
    alts = auto.alternatives(moved, festival)
    assert all(set(a["vs_approved"]) == {"cable_m", "error", "warning"} for a in alts)
    assert all(a["plan"]["approved"]["at"] == "2026-11-07T18:02" for a in alts)


def test_the_approval_is_kept_in_the_file_and_checked(tmp_path, festival):  # noqa: F811
    p, tx, rx = radio_plan()
    f = str(tmp_path / "x.cabling.json")
    plan.save_plan(plan.approve(p, "2026-11-07T18:02"), f)
    assert plan.load_plan(f)["approved"]["chains"] == plan.clean_plan(p)["chains"]
    assert "approved" not in plan.clean_plan({"approved": {"at": "yesterday", "chains": []}})
    assert "approved" not in plan.clean_plan({"approved": {"at": "2026-11-07", "chains": "x"}})
    assert plan.evaluate(plan.clean_plan(p), festival)["approved"] is None
