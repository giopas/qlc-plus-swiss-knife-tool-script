"""Doctor findings and reports (plain data, deterministic ordering)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Iterable, List, Optional

ERROR = "error"
WARNING = "warning"
INFO = "info"
SEVERITIES = (ERROR, WARNING, INFO)

# Short titles, used in summaries and in the UI later.
TITLES = {
    "D001": "Not a valid QLC+ workspace file",
    "D002": "Duplicate ID",
    "D003": "Dangling reference",
    "D004": "Empty or degenerate function",
    "D005": "Scene does not declare every channel of a fixture (LTP bleed)",
    "D006": "Strobe / internal-program channel active outside an FX function",
    "D007": "Scene shared by a VC button and a chaser step (latch conflict)",
    "D008": "No PANIC RESET on the Virtual Console",
    "D009": "DMX address overlap",
    "D012": "Input bindings but no input device patched",
    "D015": "Unnamed function",
    "D016": "Unreferenced function",
    "I001": "Caption-only button (used as a label)",
    "I002": "Virtual Console pages",
    "I003": "No fixture definition — channel checks skipped",
}


@dataclass(frozen=True)
class Finding:
    """One Doctor finding.

    ``code``      check ID, e.g. ``"D005"``
    ``severity``  ``"error"`` | ``"warning"`` | ``"info"``
    ``location``  human-readable place, e.g. ``"Function 401 '[401] Scene'"``
    ``message``   what is wrong
    ``ref``       machine-readable pointer, e.g. ``{"function": "401"}``
    """
    code: str
    severity: str
    location: str
    message: str
    ref: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    """All findings for one workspace, in deterministic order."""
    source: str = ""
    findings: List[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    # ── queries ──────────────────────────────────────────────────────────
    def by_code(self, code: str) -> List[Finding]:
        return [f for f in self.findings if f.code == code]

    def by_severity(self, severity: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def errors(self) -> List[Finding]:
        return self.by_severity(ERROR)

    @property
    def warnings(self) -> List[Finding]:
        return self.by_severity(WARNING)

    @property
    def ok(self) -> bool:
        """True when there are no errors (warnings and info allowed)."""
        return not self.errors

    def counts(self) -> dict:
        """``{code: n}`` sorted by code."""
        c = Counter(f.code for f in self.findings)
        return {k: c[k] for k in sorted(c)}

    def severity_counts(self) -> dict:
        c = Counter(f.severity for f in self.findings)
        return {s: c.get(s, 0) for s in SEVERITIES}

    # ── output ───────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "ok": self.ok,
            "summary": self.severity_counts(),
            "counts": self.counts(),
            "stats": self.stats,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def format_text(self, max_per_code: Optional[int] = 10,
                    min_severity: str = INFO) -> str:
        """Plain-text report grouped by code (for the CLI)."""
        keep = SEVERITIES[: SEVERITIES.index(min_severity) + 1]
        s = self.severity_counts()
        lines = [
            f"Workspace Doctor — {self.source or '(in memory)'}",
            "  " + ", ".join(f"{k}={v}" for k, v in sorted(self.stats.items())),
            f"  {s[ERROR]} error(s), {s[WARNING]} warning(s), {s[INFO]} info",
            "",
        ]
        for code in self.counts():
            items = [f for f in self.by_code(code) if f.severity in keep]
            if not items:
                continue
            sev = items[0].severity.upper()
            lines.append(f"[{sev}] {code} {TITLES.get(code, '')} — {len(items)}")
            shown = items if max_per_code is None else items[:max_per_code]
            for f in shown:
                lines.append(f"    {f.location}: {f.message}")
            if len(items) > len(shown):
                lines.append(f"    … {len(items) - len(shown)} more")
        if len(lines) == 4:
            lines.append("No findings.")
        return "\n".join(lines)


def make_report(source: str, findings: Iterable[Finding], stats: dict) -> Report:
    return Report(source=source, findings=list(findings), stats=dict(stats))
