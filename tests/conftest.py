import pytest


@pytest.fixture(autouse=True)
def _own_palettes_file(tmp_path, monkeypatch):
    """Never read or write the real ~/.qlc_swiss_knife palettes in a test."""
    monkeypatch.setenv("QSK_LOOK_PALETTES", str(tmp_path / "palettes_own.json"))
