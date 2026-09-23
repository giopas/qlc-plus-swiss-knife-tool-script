"""Command line:  python -m core.doctor FILE.qxw [FILE ...] [options]

Exit status: 0 = no errors, 1 = at least one error, 2 = usage problem.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from core.doctor.checks import check_file, load_qxf_defs
from core.doctor.report import SEVERITIES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m core.doctor",
        description="Workspace Doctor — read-only checks for QLC+ .qxw files.")
    ap.add_argument("files", nargs="+", help=".qxw workspace(s) to check")
    ap.add_argument("--qxf", action="append", default=[], metavar="PATH",
                    help="fixture definition file or folder (repeatable). "
                         "The workspace's own folder is always searched.")
    ap.add_argument("--allow-fx", default="", metavar="IDS",
                    help="comma-separated function IDs that are intentional FX")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--all", action="store_true",
                    help="list every finding (text mode shows 10 per check)")
    ap.add_argument("--min-severity", choices=SEVERITIES, default="info",
                    help="hide less severe findings in text mode")
    args = ap.parse_args(argv)

    allow = [x.strip() for x in args.allow_fx.split(",") if x.strip()]
    worst = 0
    out_json = []
    for path in args.files:
        if not os.path.isfile(path):
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        defs = load_qxf_defs([os.path.dirname(os.path.abspath(path))] + args.qxf)
        rep = check_file(path, defs, allow_fx=allow)
        if args.json:
            out_json.append(rep.to_dict())
        else:
            print(rep.format_text(None if args.all else 10, args.min_severity))
            print()
        if not rep.ok:
            worst = 1
    if args.json:
        print(json.dumps(out_json[0] if len(out_json) == 1 else out_json,
                         ensure_ascii=False, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
