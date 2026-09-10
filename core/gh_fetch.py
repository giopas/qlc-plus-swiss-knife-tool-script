"""
core/gh_fetch.py — Shared GitHub QXF repository helpers
========================================================
Centralises the HTTP helpers, base URLs, and name normalisation used
by both the Brightness tool and the Quick Start wizard when fetching
fixture definitions from the official QLC+ GitHub repository.

⚠  Every function that makes an outbound request is clearly marked.
   Always disclose network access to the user before calling.
"""

import json
import re
import urllib.request

# ── GitHub base URLs ──────────────────────────────────────────────────────────

GH_API_BASE = (
    "https://api.github.com/repos/mcallegari/qlcplus/contents/"
    "resources/fixtures"
)
GH_RAW_BASE = (
    "https://raw.githubusercontent.com/mcallegari/qlcplus/master/"
    "resources/fixtures"
)

_HTTP_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "qlc-swiss-knife/1.0",
}


# ── Name normalisation ────────────────────────────────────────────────────────

def norm_name(s: str) -> str:
    """Normalise a name for fuzzy filename matching.

    Lowercases, then collapses any run of non-alphanumeric characters into a
    single hyphen.  This makes 'LED 4C-12 Silent Slim Spot' and
    'LED-4C-12-Silent-Slim-Spot' identical after normalisation.
    """
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ── HTTP helpers (⚠ outbound network!) ────────────────────────────────────────

def gh_get(url: str) -> list | dict:
    """GET from the GitHub API, return parsed JSON.  Raises on HTTP error."""
    req = urllib.request.Request(url, headers=_HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def gh_get_raw(url: str) -> bytes:
    """GET raw file content from GitHub.  Raises on HTTP error."""
    headers = {k: v for k, v in _HTTP_HEADERS.items() if k != "Accept"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()
