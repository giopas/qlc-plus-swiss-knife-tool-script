"""
core.doctor — Workspace Doctor (read-only checks, WORKPLAN Phase 1.0).

    from core.doctor import check_file, load_qxf_defs
    report = check_file("Show_v41.qxw", load_qxf_defs(["fixtures/"]))
    report.ok, report.counts(), report.format_text()

Command line:  python -m core.doctor Show_v41.qxw --qxf fixtures/
"""

from core.doctor.checks import check, check_file, load_qxf_defs  # noqa: F401
from core.doctor.report import (  # noqa: F401
    ERROR, INFO, SEVERITIES, TITLES, WARNING, Finding, Report,
)
