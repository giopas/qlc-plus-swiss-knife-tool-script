# Test corpus

Real QLC+ 5 show files used as the **oracle** for Doctor, Porter, Rig Reducer, Show Book and the Liquid Bar benchmark (see `WORKPLAN.md` §1).

**Do not edit these files.** If a newer show version replaces one, add it as a new file and update `expected_baseline.json`.

## Files

| File | What it is | Role in tests |
|---|---|---|
| `SangAKlang_v41.qxw` | 14-fixture festival show:<br>• 6 × Eurolite LED 4C-12 (9 ch) on the ceiling<br>• 8 × Generic 7-Ch RGB PAR on the floor<br>• 286 functions<br>• 4 VC pages (Master + 3 bands) | Source for Rig Reducer and Porter; a "dirty" reference for Doctor. |
| `LiquidBar_v14.qxw` | 6-fixture pub show derived from v41:<br>• 207 functions<br>• 2 VC pages (setlist first)<br>• CueList wired to the setlist chaser | Target of the Liquid Bar benchmark; a "clean" reference for Doctor. |
| `Generic-7Ch-RGB-PAR.qxf` | Floor PAR definition (7 ch: dimmer, R, G, B, strobe, mode, mode speed) | Channel decoding, D005/D006. |
| `Eurolite-LED-4C-12-Silent-Slim-Spot.qxf` | Ceiling spot definition (9 ch, includes Internal Programs) | Channel decoding, D006. |

**Sanitisation:** only `<Author>` was changed (to `Swiss Knife test corpus`). No file paths, e-mail addresses or device IDs were present. Everything else is byte-identical to the originals.

**Still wanted:** `20Minutes_FLOOR` (8-fixture floor-only show) as a third, mid-size case.

## Baseline findings (23 Sep 2026)

Produced by `tools/doctor_prototype.py`, a throw-away prototype of the Phase 1.0 read-only checks. Counts are in `expected_baseline.json`. The real `core/doctor` must reproduce the **true** findings below, and must **not** reproduce the false positives.

### SangAKlang_v41

- **D005, 801 incomplete channel declarations.** Most of these are the Generic PAR's channel 7 (Mode Speed), which is missing from 645 scene entries. This is a genuine LTP-bleed risk in v41.
- **D004, 4 degenerate chasers**: the three `Setlist: <band>` chasers and `Light Down the Hall`.
- **D002, duplicate VC widget ID `0`** (×2).
- **48 unreferenced functions**, mostly `[NNN] … - Unassigned`. These are candidates for clean-up.
- **D006, 27 strobe hits.** At least scene 401 is used by the `⚡ STROBE/RED FLASH ⚡` collection, so it is intentional (see the lesson on false positives below).

### LiquidBar_v14

- Zero structural errors: no duplicate IDs, no dangling references, no unreferenced functions, and every scene declares all 7 channels. This is the reference for "clean".
- **D006, 4 hits, all false positives.** Scene 401 (`[401] Scene - Unassigned`, Strobe = 220) belongs to `⚡ STROBE/RED FLASH ⚡`.
- **41 buttons with no function.** 39 are *Toggle* buttons used as labels (the nomenclature panel); 2 are *StopAll*.

### Both files

- MIDI input is saved as `None`. In v41, 22 VC widgets have input bindings that are therefore dead (D012).

## Lessons for the Doctor design

1. **D006 must understand intent.** A scene counts as intentional FX if its own name *or the name of any function that contains it* marks it as FX (strobe, flash, `*`, punk), or if the user has allow-listed it. Checking only the scene's own name gives false positives.
2. **New check D015, unnamed functions.** Names like `[NNN] Scene - Unassigned` hide a function's purpose; rename them or remove them.
3. **Caption-only buttons are a real pattern.** They are used as a label or legend panel. Doctor reports them as *info*, not errors. VC Builder should offer proper Label widgets and a "legend panel" generator.
4. **D012 should cross-check** that input bindings exist while no input device is patched.
