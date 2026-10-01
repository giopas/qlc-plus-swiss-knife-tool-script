# Workspace Doctor

Health checks for QLC+ 5 workspaces. It is the test oracle for every Swiss Knife builder and gates every export (errors block, warnings are shown). From v1.5 it also **fixes** what you tick — always into a **new file** (`<name>_v<N+1>.qxw`, the same naming rule as every other tool) with a fix report next to it (`<name>_v<N+1>_fix_report.txt`). The original is never changed.

In the app: **Workspace Doctor** tab (side menu, 5 · Check & fix) — 🔍 Check the open workspace, tick findings (recommended fixes are pre-ticked; fixes that delete functions are offered but not ticked), **💾 Fix selected → new file…**.

## Usage

```bash
python -m core.doctor Show_v41.qxw                 # text report, exit 1 if errors
python -m core.doctor Show_v41.qxw --qxf ~/fixtures --all
python -m core.doctor Show_v41.qxw --json          # machine-readable
python -m core.doctor Show_v41.qxw --allow-fx 401,602 --min-severity warning
python -m core.doctor Show_v41.qxw --fix           # recommended fixes → Show_v42.qxw + Show_v42_fix_report.txt
python -m core.doctor Show_v41.qxw --fix --remove  # … plus removals (D004, D015, D016)
python -m core.doctor Show_v41.qxw --fix --codes D003,D017 --out Fixed.qxw
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
| D010 | info | The only page with a CueList (the setlist) is not page 1 — QLC+ opens on page 1 |
| D011 | warning | Widget sticks out of its page or frame by more than 8 px (partly hidden) |
| D012 | warning | VC input bindings on a universe whose input device is not patched (saved as None) |
| D013 | warning | Chaser steps that last 0 ms (Common duration 0 and no fade-in, or per-step hold and fade-in 0) |
| D014 | warning | CueList runs a chaser with no steps |
| D015 | info | Unnamed function (`[NNN] Scene - Unassigned`) |
| D016 | warning | Function not used by any function or VC widget (a script that only *stops* it doesn't count) |
| D017 | warning | PANIC RESET is a plain Scene: a scene at 0 can't darken looks that are still running (dimmer/colour are HTP) |
| D018 | warning | A song in the setlist (a cue of the chaser a CueList runs) lights nothing — an empty scene, or a chaser / collection with no steps or only such steps: the stage goes dark on that cue |
| I001 | info | Button with no function (label use) — StopAll/Blackout buttons excluded |
| I002 | info | VC pages in order |
| I003 | info | No fixture definition loaded — channel checks skipped |

**Intentional FX (D006).** A scene is FX when its own name or the name of any function that contains it (transitively) matches *strob, flash, `*`, punk, macro, program, audio, fx*, or when its ID (or a container's) is allow-listed. A value is neutral when it falls in a capability labelled *No function / No flash / Open / Off / DMX mode* or with preset `ShutterOpen`; without capabilities only 0 is neutral.

Findings are deterministic: checks run in ID order, items in document order.


## Fixes (v1.5)

| ID | Fix | Ticked by default |
|---|---|---|
| D002 | Duplicate function IDs: later copies get `max + 1` (references keep pointing at the first). Duplicate VC widget IDs: renumbered. Duplicate fixture/group IDs: not fixed. | yes |
| D003 | Remove the broken reference: chaser/collection steps, show items, script commands → missing function; scene values, EFX entries, slider channels for missing fixtures; a button → missing function becomes caption-only. Not fixed: CueList without chaser, RGB matrix → missing group, missing bound scene. | yes |
| D004 | Remove empty scenes/collections with every step, script command and button that used them. Degenerate chasers: not fixed. | no (removes) |
| D005 | Add the missing channels at the fixture's neutral value (0 without a definition). | yes |
| D006 | Set the strobe/program channel to its neutral value. | yes |
| D007 | Give the chaser its own copy of the scene (`<name> (chaser)`); the button keeps the original. | yes |
| D008 | No PANIC RESET: create *Reset: neutral state* (every fixture neutral, intensity 0) + a *PANIC RESET* script (stop every function, start the reset scene, stop itself) + a button on page 1. Not on a button: add the button. | yes |
| D010 | Move the setlist page to page 1. | no (info) |
| D011 | Move the widget back inside its page/frame (not when it is larger than it). | yes |
| D015 | Remove the unnamed function if nothing uses it. | no (removes) |
| D016 | Remove the unused function. | no (removes) |
| D017 | Wrap the scene in a *PANIC RESET* script with the scene's name: stop every function, start the scene (renamed `… (state)`), stop itself; the scene's buttons now run the script. | yes |

Fixes run in code order, items in document order; new IDs are `max + 1` — the same input and selection give the same file. The report lists every change, what was selected but could not be fixed, and what is still open after the fix. Removals can make other functions unused: run the Doctor again on the result.
