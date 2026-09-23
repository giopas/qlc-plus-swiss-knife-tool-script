"""core.qxw_io — the single safe QXW reader/writer (WORKPLAN 0.3)."""
import glob
import os
import re
import xml.etree.ElementTree as ET

import pytest

from core import qxw_io

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SAMPLE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n'
    '<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="VirtualConsole">\n'
    ' <Creator><Name>Q Light Controller Plus</Name><Version>5.0.0</Version></Creator>\n'
    ' <Engine>\n'
    '  <Function ID="401" Type="Scene" Name="⚡ STROBE/RED FLASH ⚡">'
    '<FixtureVal ID="0">0,255,4,220</FixtureVal></Function>\n'
    ' </Engine>\n'
    ' <VirtualConsole><Frame Caption="&lt;Main&gt; &amp; more"/></VirtualConsole>\n'
    '</Workspace>\n'
).encode("utf-8")

CORPUS = sorted(glob.glob(os.path.join(HERE, "corpus", "*.qxw"))
                + glob.glob(os.path.join(HERE, "manual", "*.qxw")))


def _canon(el):
    """Structural fingerprint of a tree (tag, attrs, text, tail, children)."""
    return (el.tag, sorted(el.attrib.items()), (el.text or "").strip(),
            (el.tail or "").strip(), [_canon(c) for c in el])


# ── serialisation ─────────────────────────────────────────────────────────────

def test_header_and_doctype_always_present():
    out = qxw_io.qxw_bytes(qxw_io.loads_qxw(SAMPLE))
    assert out.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n'
                          b'<!DOCTYPE Workspace>\n<Workspace ')


def test_default_namespace_no_prefix():
    out = qxw_io.qxw_bytes(qxw_io.loads_qxw(SAMPLE))
    assert b'xmlns="http://www.qlcplus.org/Workspace"' in out
    assert b"ns0:" not in out


def test_accepts_elementtree():
    root = qxw_io.loads_qxw(SAMPLE)
    assert qxw_io.qxw_bytes(ET.ElementTree(root)) == qxw_io.qxw_bytes(root)


def test_deterministic_and_idempotent():
    once = qxw_io.qxw_bytes(qxw_io.loads_qxw(SAMPLE))
    twice = qxw_io.qxw_bytes(qxw_io.loads_qxw(once))
    assert once == twice == qxw_io.qxw_bytes(qxw_io.loads_qxw(SAMPLE))


@pytest.mark.parametrize("path", CORPUS, ids=os.path.basename)
def test_round_trip_lossless(path, tmp_path):
    """load → write → load keeps every element/attribute/text; bytes stable."""
    tree = qxw_io.load_qxw(path)
    out = tmp_path / "rt.qxw"
    qxw_io.write_qxw(tree.getroot(), str(out))
    again = qxw_io.load_qxw(str(out))
    assert _canon(again.getroot()) == _canon(tree.getroot())
    assert qxw_io.qxw_bytes(again.getroot()) == out.read_bytes()


# ── writing safety ────────────────────────────────────────────────────────────

def test_write_refuses_protected_path(tmp_path):
    src = tmp_path / "Show_v1.qxw"
    src.write_bytes(SAMPLE)
    root = qxw_io.loads_qxw(SAMPLE)
    with pytest.raises(qxw_io.OverwriteError):
        qxw_io.write_qxw(root, str(src), protect=[str(src)])
    # relative / non-normalised spelling of the same file is caught too
    with pytest.raises(qxw_io.OverwriteError):
        qxw_io.write_qxw(root, str(tmp_path / "." / "Show_v1.qxw"),
                         protect=[str(src)])
    assert src.read_bytes() == SAMPLE


def test_write_is_atomic_no_temp_left(tmp_path):
    out = tmp_path / "new.qxw"
    qxw_io.write_qxw(qxw_io.loads_qxw(SAMPLE), str(out), protect=[None, ""])
    assert out.exists()
    assert [p.name for p in tmp_path.iterdir()] == ["new.qxw"]


def test_load_size_cap(tmp_path, monkeypatch):
    p = tmp_path / "big.qxw"
    p.write_bytes(SAMPLE)
    monkeypatch.setattr(qxw_io, "MAX_QXW_BYTES", 10)
    with pytest.raises(ValueError):
        qxw_io.load_qxw(str(p))


# ── versioned names ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("given,expected", [
    ("SangAKlang_v41.qxw", "SangAKlang_v42.qxw"),
    ("LiquidBar_v14.qxw", "LiquidBar_v15.qxw"),
    ("Show_V9.qxw", "Show_v10.qxw"),
    ("Show_v09.qxw", "Show_v10.qxw"),
    ("Show_v099.qxw", "Show_v100.qxw"),
    ("Show.qxw", "Show_v2.qxw"),
    ("Show3.qxw", "Show3_v2.qxw"),
    ("Show", "Show_v2.qxw"),
    ("/a/b/Show_v1.qxw", "/a/b/Show_v2.qxw"),
])
def test_next_version_name(given, expected):
    assert qxw_io.next_version_name(given) == expected


def test_next_version_path_skips_existing(tmp_path):
    (tmp_path / "Show_v42.qxw").write_bytes(b"x")
    (tmp_path / "Show_v43.qxw").write_bytes(b"x")
    got = qxw_io.next_version_path(str(tmp_path / "Show_v41.qxw"))
    assert os.path.basename(got) == "Show_v44.qxw"


def test_suffixed_name():
    assert qxw_io.suffixed_name("x/Show_v41.qxw", "doctor") == "x/Show_v41_doctor.qxw"


# ── single-writer guard ──────────────────────────────────────────────────────

def test_no_other_qxw_output_paths():
    """Only core/qxw_io.py may serialise workspaces (WORKPLAN §2.2)."""
    bad = []
    pat = re.compile(r"ET\.tostring\(|\.write\([^)]*xml_declaration|<!DOCTYPE Workspace>|tree\W*\]?\.write\(")
    for folder in ("core", "routes"):
        for p in glob.glob(os.path.join(REPO, folder, "**", "*.py"), recursive=True):
            if p.endswith(os.path.join("core", "qxw_io.py")):
                continue
            for n, line in enumerate(open(p, encoding="utf-8"), 1):
                if pat.search(line) and "qxw-io: not output" not in line:
                    bad.append(f"{os.path.relpath(p, REPO)}:{n}: {line.strip()}")
    assert not bad, "\n".join(bad)


# ── namespace handling ───────────────────────────────────────────────────────

def test_strip_and_requalify_round_trip():
    root = qxw_io.loads_qxw(SAMPLE)
    ref = qxw_io.qxw_bytes(root)
    qxw_io.strip_ns(root)
    assert root.tag == "Workspace" and root.find("Engine") is not None
    # qxw_bytes restores the namespace without mutating the stripped tree
    assert qxw_io.qxw_bytes(root) == ref
    assert root.tag == "Workspace"


def test_load_strip_namespace(tmp_path):
    p = tmp_path / "s.qxw"
    p.write_bytes(SAMPLE)
    root = qxw_io.load_qxw(str(p), strip_namespace=True).getroot()
    assert root.find("Engine/Function").get("ID") == "401"
