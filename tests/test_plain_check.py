"""tools/plain_check.py reads prose, not code, and finds what it promises (3.9.6)."""
import importlib.util
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("plain_check", os.path.join(HERE, "tools", "plain_check.py"))
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def _page(tmp_path, text):
    p = tmp_path / "Page.md"
    p.write_text(text, encoding="utf-8")
    return pc.check(str(p))


def test_the_box_is_found_near_the_top(tmp_path):
    r = _page(tmp_path, "# Page\n\n> **In one minute.** It does a thing.\n\nText here.\n")
    assert r["box"] is True
    assert _page(tmp_path, "# Page\n\nText here.\n")["box"] is False


def test_code_tables_and_links_are_not_prose(tmp_path):
    text = ("# Page\n\n```\n" + "word " * 80 + "\n```\n\n| a | b |\n|---|---|\n| " + "x " * 60 + "| y |\n\n"
            "Short one. Another short one.\n")
    r = _page(tmp_path, text)
    assert r["over"] == 0 and r["avg"] < 6


def test_long_sentences_and_dashes_are_counted(tmp_path):
    long = " ".join(["word"] * 40) + "."
    r = _page(tmp_path, f"# Page\n\n{long}\n\nA clause — joined by a dash.\n")
    assert r["over"] == 1
    assert len(r["dashes"]) == 1


def test_terms_are_explained_by_the_words_page_or_in_place(tmp_path):
    assert "chaser" in _page(tmp_path, "# Page\n\nPlay the chaser now.\n")["terms"]
    assert _page(tmp_path, "# Page\n\nPlay the chaser now. See [[Words used here]].\n")["terms"] == []
    assert "chaser" not in _page(tmp_path, "# Page\n\nA **chaser** is a list of scenes.\n")["terms"]


def test_stubs_need_no_box(tmp_path, capsys):
    p = tmp_path / "Stub.md"
    p.write_text("# Stub\n\nMoved to [[Other]].\n", encoding="utf-8")
    assert pc.main([str(p), "--strict"]) == 0
