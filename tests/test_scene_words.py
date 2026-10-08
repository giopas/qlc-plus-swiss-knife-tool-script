"""Plain colour words for the Dictionary (core/scene_words.py, v3.0.1)."""
import os
import xml.etree.ElementTree as ET

from core import scene_words as sw
from core.doctor import load_qxf_defs

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def test_colour_words():
    assert sw.colour_word((1, 0, 0)) == "red"
    assert sw.colour_word((0, 1, 0.78)) == "teal"
    assert sw.colour_word((1, 0, 0.7)) == "magenta"
    assert sw.colour_word((1, 0.7, 0.43)) == "warm white"
    assert sw.colour_word((1, 1, 1)) == "white"
    assert sw.colour_word((1, 0, 0), 0.3) == "dim red"
    assert sw.colour_word((1, 1, 1), 0.0) == "off"


def _info():
    defs = load_qxf_defs([CORPUS])
    d = defs[("generic", "7-ch rgb led par")]
    names = {"1": "DR: Drums", "2": "FL: Front Left", "3": "FR: Front Right", "4": "LG: Logo"}
    return {k: {"name": v, "mode": "7 Channel", "def": d} for k, v in names.items()}


def _scene(vals):
    s = ET.Element("Function", Type="Scene")
    for fid, txt in vals.items():
        ET.SubElement(s, "FixtureVal", ID=fid).text = txt
    return s


def test_scene_is_described_by_colour_with_the_rest_last():
    red, blue = "0,255,1,255,2,0,3,0", "0,255,1,0,2,0,3,255"
    sc = _scene({"1": red, "2": blue, "3": blue, "4": blue})
    assert sw.describe(sc, _info()) == "red on Drums, blue on the rest"
    assert sw.dominant(sc, _info()) == "blue"
    strobe = _scene({"1": red + ",4,200", "2": red + ",4,200"})
    assert sw.describe(strobe, _info()) == "all 2 fixtures red strobe"
    assert sw.describe(_scene({"1": "0,0", "2": "0,0"}), _info()) == "blackout (all off)"
    assert sw.describe(sc, {}) == ""                    # no definitions: nothing guessed


def test_chase_words_say_how_a_chase_changes():
    red, dim, blue = "0,255,1,255,2,0,3,0", "0,80,1,255,2,0,3,0", "0,255,1,0,2,0,3,255"
    i = _info()
    swap = [_scene({"1": red, "2": blue}), _scene({"1": blue, "2": red})]
    assert sw.chase_words(swap, i) == (["red", "blue"], "moves")
    pulse = [_scene({"1": red, "2": red}), _scene({"1": dim, "2": dim})]
    assert sw.chase_words(pulse, i)[1] == "level"
    change = [_scene({"1": red, "2": red}), _scene({"1": blue, "2": blue})]
    assert sw.chase_words(change, i) == (["red", "blue"], "colours")
