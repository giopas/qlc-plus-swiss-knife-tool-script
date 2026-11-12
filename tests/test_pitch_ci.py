"""The pitch video and deck are made and attached by GitHub Actions, never by hand.

pitch.yml makes them with tools/make_pitch_video.py and attaches them to the
release; release.yml calls it after publishing.  The README links to the files
of the latest release, and the updater must never pick them up.
"""
import importlib.util
import os
import re
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WF = ROOT / ".github" / "workflows"


def _tool():
    spec = importlib.util.spec_from_file_location("pitch", ROOT / "tools" / "make_pitch_video.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_release_calls_pitch_after_publishing():
    rel = (WF / "release.yml").read_text(encoding="utf-8")
    m = re.search(r"\n  pitch:\n((?:    .*\n|\s*\n)+)", rel + "\n")
    assert m, "release.yml has no pitch job"
    job = m.group(1)
    assert "needs: publish" in job
    assert "uses: ./.github/workflows/pitch.yml" in job
    assert "tag: ${{ github.ref_name }}" in job


def test_pitch_workflow_uses_the_strict_voice_and_attaches_both_files():
    text = (WF / "pitch.yml").read_text(encoding="utf-8")
    assert "--stills --tts edge --strict-voice" in text
    assert "gh release upload" in text and "QLC_Swiss_Knife_Pitch.mp4 QLC_Swiss_Knife_Pitch.pdf" in text
    for trigger in ("  workflow_call:", "  workflow_dispatch:", "  push:", '      - "tools/make_pitch_video.py"'):
        assert trigger in text, trigger


def test_updater_ignores_the_pitch_files():
    from core import update
    for name in ("QLC_Swiss_Knife_Pitch.mp4", "QLC_Swiss_Knife_Pitch.pdf"):
        assert not update._ASSET_RE.match(name)


def test_readme_links_the_latest_release_files_and_the_poster_exists():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "releases/latest/download/QLC_Swiss_Knife_Pitch.mp4" in readme
    assert "releases/latest/download/QLC_Swiss_Knife_Pitch.pdf" in readme
    assert (ROOT / "screenshots" / "pitch-poster.png").is_file()
    m = _tool()
    assert m.FILE_STEM == "QLC_Swiss_Knife_Pitch"


def test_claude_slide_says_it_can_start_a_show():
    m = _tool()
    slide = next(s for s in m.SLIDES if s["title"] == "Undo It, or Ask Claude")
    assert "Claude can even start a new show from scratch" in slide["bullets"]
    assert "from scratch" in slide["vo"]


def test_the_readme_poster_opens_the_page_that_plays_the_video():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "](https://giopas.github.io/qlc-plus-swiss-knife-tool-script/)" in readme
    page = (WF / "pitch-page.yml").read_text(encoding="utf-8")
    for needed in ("pages: write", "id-token: write", "name: github-pages", "actions/deploy-pages@",
                   "gh release download", "tools/pitch_page/index.html"):
        assert needed in page, needed
    # started on main by pitch.yml (a deploy from a tag is refused by the environment)
    pitch = (WF / "pitch.yml").read_text(encoding="utf-8")
    assert "gh workflow run pitch-page.yml" in pitch and "--ref main" in pitch
    assert "actions: write" in pitch
    html = (ROOT / "tools" / "pitch_page" / "index.html").read_text(encoding="utf-8")
    assert 'src="QLC_Swiss_Knife_Pitch.mp4"' in html and "<video controls playsinline" in html
    assert "__VERSION__" in html
