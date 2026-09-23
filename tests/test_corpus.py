"""Corpus sanity tests — real show files used as the oracle for Doctor, Porter,
Rig Reducer and the Liquid Bar benchmark. See tests/corpus/README.md."""
import json, os
import xml.etree.ElementTree as ET
import pytest

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
W = "{http://www.qlcplus.org/Workspace}"
EXPECTED = json.load(open(os.path.join(CORPUS, "expected_baseline.json"), encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_workspace_is_valid_qlc_file(name):
    path = os.path.join(CORPUS, name)
    with open(path, encoding="utf-8") as fh:
        head = fh.read(200)
    assert head.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<!DOCTYPE Workspace>" in head
    root = ET.parse(path).getroot()
    assert root.tag == W + "Workspace"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_workspace_counts(name):
    root = ET.parse(os.path.join(CORPUS, name)).getroot()
    assert len(root.findall(f".//{W}Engine/{W}Fixture")) == EXPECTED[name]["fixtures"]
    assert len(root.findall(f".//{W}Engine/{W}Function")) == EXPECTED[name]["functions"]


@pytest.mark.parametrize("qxf", ["Generic-7Ch-RGB-PAR.qxf", "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"])
def test_fixture_definitions_parse(qxf):
    ET.parse(os.path.join(CORPUS, qxf))
