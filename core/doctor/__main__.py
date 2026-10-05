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


def _options(args) -> dict:
    raw = {"d003": args.d003, "d004": args.d004, "d015": args.d015}
    t = (args.timing or "").strip().lower()
    if t.endswith("bpm") and t[:-3].replace(".", "", 1).isdigit():
        raw["d013"] = {"bpm": float(t[:-3])}
    elif t.rstrip("ms").isdigit():
        raw["d013"] = {"ms": int(t.rstrip("ms"))}
    from core.doctor import fixes
    return fixes.clean_options(raw)


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
    ap.add_argument("--fix", action="store_true",
                    help="write a fixed copy <name>_v<N+1>.qxw (+ _fix_report.txt); "
                         "the original is never changed")
    ap.add_argument("--codes", default="", metavar="CODES",
                    help="with --fix: comma-separated codes to fix (default: "
                         "D002,D003,D005,D006,D007,D008,D017 — no removals)")
    ap.add_argument("--remove", action="store_true",
                    help="with --fix: also remove empty (D004), unnamed unused (D015) "
                         "and unused (D016) functions")
    ap.add_argument("--timing", metavar="500ms|120bpm",
                    help="with --fix D013: the duration given to 0 ms chaser steps (default 500ms)")
    ap.add_argument("--d004", choices=("merge", "remove"),
                    help="with --fix D004: degenerate chasers merged into their scene (default) or removed")
    ap.add_argument("--d015", choices=("remove", "rename"),
                    help="with --fix D015: unnamed functions removed (if unused) or renamed from context")
    ap.add_argument("--d003", choices=("unlink", "rewire"),
                    help="with --fix D003: broken buttons / CueLists unlinked (default) or rewired by name")
    ap.add_argument("--out", metavar="PATH", help="with --fix: output file (one input only)")
    args = ap.parse_args(argv)

    allow = [x.strip() for x in args.allow_fx.split(",") if x.strip()]
    worst = 0
    out_json = []
    for path in args.files:
        if not os.path.isfile(path):
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        defs = load_qxf_defs([os.path.dirname(os.path.abspath(path))] + args.qxf)
        if args.fix:
            from core.doctor import fixes
            codes = ({c.strip().upper() for c in args.codes.split(",") if c.strip()}
                     or set(fixes.DEFAULT_CODES) | (fixes.REMOVING if args.remove else set()))
            out = fixes.fix_file(path, defs, out_path=args.out if len(args.files) == 1 else None,
                                 codes=codes, allow_fx=allow, options=_options(args))
            res = out["result"]
            print(f"{len(res.actions)} fix(es) → {out['output']}  (report: {out['report_path']})")
            path = out["output"]
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
