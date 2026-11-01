"""3.10.0: the "No workspace open" banner follows the state after a page reload."""
from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_the_late_page_load_handler_keeps_the_known_state():
    # DOMContentLoaded can come after the status answer: it must not put the banner back
    assert "_updateNeedWsBanners(false));" not in APP
    assert "_updateNeedWsBanners(_wsLoadedKnown)" in APP
    assert "_wsLoadedKnown = !!loaded;" in APP
