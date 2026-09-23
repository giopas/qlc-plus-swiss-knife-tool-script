"""Merger and Porter must read real QLC+ files, which declare xmlns.

Regression: both modules looked up plain tag names ("Engine") on namespaced
trees and silently found 0 fixtures / 0 functions in every real workspace.
"""
import os

import pytest

from core import merger, porter, qxw_io

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")

NS_QXW = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n'
    '<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="VC">\n'
    ' <Creator><Name>Q Light Controller Plus</Name><Version>5.2.2</Version></Creator>\n'
    ' <Engine>\n'
    '  <Fixture><Manufacturer>Generic</Manufacturer><Model>7-Ch RGB LED PAR</Model>'
    '<Mode>7 Channel</Mode><ID>0</ID><Name>PAR 1</Name><Universe>0</Universe>'
    '<Address>0</Address><Channels>7</Channels></Fixture>\n'
    '  <Function ID="1" Type="Scene" Name="Red"><Speed FadeIn="0" FadeOut="0" Duration="0"/>'
    '<FixtureVal ID="0">0,255,1,255,2,0,3,0,4,0,5,0,6,0</FixtureVal></Function>\n'
    ' </Engine>\n'
    '</Workspace>\n'
)


@pytest.fixture
def ns_file(tmp_path):
    p = tmp_path / "Show_v1.qxw"
    p.write_text(NS_QXW, encoding="utf-8")
    return str(p)


def test_merger_reads_namespaced_file(ns_file):
    merger.clear_src(); merger.clear_dst()
    assert merger.load_src(ns_file) == {"fixtures": 1, "groups": 0, "functions": 1}
    merger.load_dst(ns_file)
    name, data = merger.export_dst()
    assert name == "Show_v2.qxw"
    assert b'<Workspace xmlns="http://www.qlcplus.org/Workspace"' in data


def test_porter_reads_namespaced_file(ns_file):
    porter.clear()
    src = porter.load_source(ns_file)
    assert src["fixtures"] == 1 and src["functions"] == 1
    assert src["creator_version"] == "5.2.2"


@pytest.mark.skipif(not os.path.isdir(CORPUS), reason="corpus not present")
@pytest.mark.parametrize("name,fixtures,functions", [
    ("SangAKlang_v41.qxw", 14, 286), ("LiquidBar_v14.qxw", 6, 207)])
def test_corpus_counts(name, fixtures, functions):
    path = os.path.join(CORPUS, name)
    porter.clear()
    src = porter.load_source(path)
    assert (src["fixtures"], src["functions"]) == (fixtures, functions)
    merger.clear_src()
    assert merger.load_src(path)["functions"] == functions
    # a merger pass-through export is byte-identical to a direct qxw_io write
    merger.clear_dst()
    merger.load_dst(path)
    _, data = merger.export_dst()
    assert data == qxw_io.qxw_bytes(qxw_io.load_qxw(path).getroot())


def test_upload_keeps_real_file_name(ns_file):
    """Browse/upload in Merger and Porter must not show 'tmpxw7vxz61'."""
    import io
    import app
    c = app.create_app().test_client()
    data = open(ns_file, "rb").read()
    for url in ("/api/porter/source/load", "/api/merger/src/load"):
        r = c.post(url, data={"file": (io.BytesIO(data), "SangAKlang_v41.qxw")},
                   content_type="multipart/form-data")
        assert r.get_json()["name"] == "SangAKlang_v41", url
