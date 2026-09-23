# Workspace Doctor

Read-only health checks for QLC+ 5 workspaces. It is the test oracle for every Swiss Knife builder and, from v1.4, gates every export (errors block, warnings are shown). Auto-fixes arrive in v1.5 and will always write a new file (`<name>_doctor.qxw`).

## Usage

```bash
python -m core.doctor Show_v41.qxw                 # text report, exit 1 if errors
python -m core.doctor Show_v41.qxw --qxf ~/fixtures --all
python -m core.doctor Show_v41.qxw --json          # machine-readable
python -m core.doctor Show_v41.qxw --allow-fx 401,602 --min-severity warning
```

`.qxf` files in the workspace's folder are always loaded; add more with `--qxf` (file or folder, repeatable). Without a definition a fixture still gets D005, but not D006 (reported as I003).

```python
from core.doctor import check_file, load_qxf_defs
rep = check_file("Show_v41.qxw", load_qxf_defs(["fixtures/"]))
rep.ok, rep.counts(), rep.errors, rep.to_json()
```

## Checks

| ID | Severity | Check |
|---|---|---|
| D001 | error | File is not a valid QLC+ workspace: no XML declaration, no `<!DOCTYPE Workspace>`, not well-formed, wrong root |
| D002 | error | Duplicate fixture / fixture-group / function / VC-widget ID (widgets across all pages) |
| D003 | error | Dangling reference: step/bound scene/show/script → missing function; scene → missing fixture; RGB Matrix → missing group; button/slider → missing function; CueList with no chaser or a non-chaser |
| D004 | warning | Empty scene, degenerate chaser (0–1 steps), empty collection |
| D005 | warning | Scene sets some but not all channels of a fixture (LTP bleed) |
| D006 | warning | Strobe (Shutter) or internal-program (Effect) channel at a non-neutral value in a scene that is not intentional FX |
| D007 | warning | Same scene on a VC button and in a chaser step (latch conflict) |
| D008 | warning | No PANIC RESET function, or it is not on a VC button |
| D009 | warning | DMX address overlap |
| D012 | warning | VC input bindings on a universe whose input device is not patched (saved as None) |
| D015 | info | Unnamed function (`[NNN] Scene - Unassigned`) |
| D016 | warning | Function not used by any function or VC widget |
| I001 | info | Button with no function (label use) — StopAll/Blackout buttons excluded |
| I002 | info | VC pages in order |
| I003 | info | No fixture definition loaded — channel checks skipped |

**Intentional FX (D006).** A scene is FX when its own name or the name of any function that contains it (transitively) matches *strob, flash, `*`, punk, macro, program, audio, fx*, or when its ID (or a container's) is allow-listed. A value is neutral when it falls in a capability labelled *No function / No flash / Open / Off / DMX mode* or with preset `ShutterOpen`; without capabilities only 0 is neutral.

Findings are deterministic: checks run in ID order, items in document order.
