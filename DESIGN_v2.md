# QLC+ Swiss Knife: DESIGN v2, a clearer Swiss Knife

Accepted by giopas on 21 October 2026 and written against 3.8.0, which was released on 20 October. `WORKPLAN.md` carries the new order and the 3.9.0, 3.9.5 and 3.9.6 entries. It answers three outside UX reviews (ChatGPT, Copilot, Gemini), checks each against the code, and turns what holds up into a design and a build order. It replaces the open parts of [DESIGN_v1.1.0.md](DESIGN_v1.1.0.md), whose shell, groups, Start screen and tokens are built; section 2 lists what is left of it.

Interactive mockups: [mockups/mockup_D_v2.html](mockups/mockup_D_v2.html) (six frames, dark theme, no scripts beyond the frame switcher). The wireframes below are the same screens in text.

**Contents**

1. In one minute
2. What the three reviews say, and how far to trust them
3. The code today: what is good, what is really wrong
4. Verdict on every recommendation
5. Design direction and tokens
6. The show state, the ribbon and the three verbs
7. Home that follows the state
8. The page kit: one frame for every tool
9. Key screens
10. Tablet on stage (the 3.9.0 pilot)
11. Plain language (the old 3.8.5)
12. Proposed changes to the workplan
13. Risks, rejected ideas, open questions

---

## 1. In one minute

**The three reviews agree on the diagnosis.** Swiss Knife is well organised by job (six groups, guided routes, one show in progress, History, Doctor) but every screen has the same visual weight, writing to disk is explained in too many words and in too many places, the first screen does not react to what you are doing, and the look is "an excellent technical tool" rather than "a professional product".

**They disagree on the cure, and two of them reviewed less than they thought.** Gemini could not open the repository and worked from forum posts. ChatGPT worked from the README and wiki. Only Copilot saw current screenshots. About half of what they ask for is built already (section 4). The reviews are right about the rest.

**Recommendation.**

1. Keep the architecture, the stack (Flask, vanilla JS, no new dependency), the six groups and the teal accent. Do not add violet, amber and cyan accents (Gemini, ChatGPT) and do not force a three-stage pipeline (Gemini).
2. Fix the things that make the app feel unfinished: one primary action per screen, one meaning for each verb that writes, a disabled button that says why, a Doctor pill that counts kinds of problems instead of 856 identical warnings, text smaller than 11 px, 61 emoji used as icons, no visible keyboard focus.
3. Make Start follow the state: no show open, show open and clean, show open and needing attention, route in progress.
4. Build the new **Tablet on stage** screen of 3.9.0 as the pilot of the new page kit. It has to be rebuilt anyway, so the kit gets its first real use at no extra cost, and 3.9.5 then rolls it out to the other screens.
5. Order: 3.9.0 Tablet on stage, 3.9.5 A clearer Swiss Knife (look, structure, in-app words), 3.9.6 Plain-language wiki and README. The wiki and the pictures come last because they describe the screens that 3.9.5 changes.

---

## 2. What the three reviews say, and how far to trust them

| | ChatGPT | Copilot | Gemini |
|---|---|---|---|
| Saw | README, wiki text, repository summary, some screenshots | Current screenshots (Start, Rig Reducer, Doctor, Brightness, Show Paperwork, Trigger Manager, Dictionary, ID Browser, Function Porter, History panel) | Nothing from the repository; it said so and used forum posts |
| Tone | Strategy and process: audit first, prototype Home, then migrate | Concrete: ten numbered recommendations, a score table (overall 7.8/10, visual hierarchy 6.5, modern feel 6) | A prompt for another assistant, with a palette and a "3-stage gig workflow" |
| Best idea | The three states (editing, applying, saving) must look different; do not invent one universal "ready" score | One primary action zone per screen; Function Porter shows three big things at once | Function type badges everywhere; show the match quality of a song |
| Weakest idea | Violet accent and "Good evening" greeting: a rebrand for little gain | "Estimated 5 min" on routes: we only measured one (the Pub test, 12 minutes) | Navigation as Inspect, Adapt, Export: the Doctor gates every export and Create and Run the show do not fit a line |

What all three say in common, in the order they say it most often:

1. Visual hierarchy is flat; many things compete.
2. The difference between changing the show, saving, and exporting is not obvious.
3. Guided routes are the real product and should be more prominent.
4. History and the Doctor are the strongest features and are shown too modestly.
5. Tables look like spreadsheets.
6. Consistent tokens (spacing, type, colour) would make it feel designed.

---

## 3. The code today: what is good, what is really wrong

Measured on 3.8.0 (`templates/index.html` 2981 lines, `static/css/style.css` 4530, `tokens.css` 143).

### Already built, to keep

| Built | Where |
|---|---|
| Six groups in the side menu whose numbers match six job cards on Start | `index.html` sidebar and `start-workflow` |
| Six guided routes with step chips and a start button | `start-routes` |
| One shared ribbon: file, fixtures, functions, widgets, changes, Doctor, Go to… (⌘K), Undo, History, Save as new file, Open, Reload | `metrics-strip` |
| History as a side panel and a compact list in the sidebar | `show-history`, `side-changes` |
| Page header with icon, title, one-line description, help and theme buttons | `.page-h` |
| A "Changes the show in progress" footer with a live summary and Apply, in Rig Reducer, Setlist, Doctor, Stage Monitor, and others | footer of each tool |
| Command palette | `cpOpen()` |
| Tokens: spacing 4/8/16/24/32/48, radii, three themes, semantic colours, row hover and zebra | `tokens.css` |
| Mockup C of 4 October already answered an earlier review (Copilot and Gemini) | `mockups/mockup_C_ui_polish.html` |

So the reviews often ask for what is there. The pictures they judged are partly old: `screenshots/01-start.png` and `10-setlist.png` still show 3.4.0, with the Start screen that listed routes only.

### Really wrong, with evidence

| # | Problem | Evidence | Why it matters |
|---|---|---|---|
| P1 | The Doctor pill shouts. | The test show shows `1 · 856` in red. In the Doctor screen of the same show, 851 of the 855 warnings are one rule (D005); the screen groups them correctly, the pill counts instances. (Read from Copilot's screenshot: the ribbon says 856 and the list 855, a small mismatch to check in stage B.) | Every show looks broken, so the pill stops being read. |
| P2 | Several things write, with several names. | Ribbon: *Save as new file…*. Footers: *Export a copy…*, *Apply to the show*, *Save Songs* (a second filled button beside Apply on the Setlist), *Save setlist…*, *Save dictionary*, *Export the page*. | ChatGPT and Gemini both flagged it. A user cannot predict what a button does to disk. |
| P3 | Two filled buttons compete on one screen. | Setlist footer: *Save Songs* (green) and *Apply to the show* (teal). | The eye has no first choice. |
| P4 | Text is too small for a dim room. | Token use in `style.css`: `--fs-small` (11 px) 110 times, `--fs-micro` (10 px) 66 times, `--fs-body` (13 px) 68 times, plus literals of 8, 8.5, 9 and 9.5 px. | 176 places at 11 px or less. Copilot's "visual hierarchy 6.5" is mostly this. |
| P5 | Seven type steps, three wanted. | `--fs-title, section, lead, body, ui, small, micro` all in use. Page titles are a literal 16 px, not a token. | Hierarchy is blurred. |
| P6 | Spacing is half on the scale. | Padding values of 6, 10, 5 and 3 px: 97 uses against 8 and 4 px: 73. | Looks slightly uneven everywhere. |
| P7 | Emoji as icons. | 61 buttons start with an emoji (📂 💾 🕘 📱 ▶ …). The icon sprite exists (`static/icons.svg`) and the sidebar uses it. | Different weight and colour on each system. DESIGN v1.1.0 asked to remove them. |
| P8 | No visible keyboard focus, no motion preference. | `:focus-visible` appears 0 times, `prefers-reduced-motion` 0 times, `role=` twice, `aria-*` 36 times in the template. | A keyboard user cannot tell where they are. |
| P9 | Style leaks into markup. | 172 inline `style="…"` in `index.html`; 86 hex colours in `style.css` outside the tokens. | The kit cannot be changed in one place. |
| P10 | Start does not react. | The same Start page with or without a show. Recent shows are a plain list. The ribbon shows the Doctor but Start does not say "1 error, look at it". | ChatGPT's best point: Start should say what to do now. |
| P11 | Function Porter step 3 shows three large things together. | Source stage, target stage and the mapping table on one screen (Copilot's screenshot). | The only screen that really overwhelms. The other tools are dense but each has one job. |
| P12 | Tablet is two doors. | Setlist *Tablet page…* and the Stage Monitor do one job. Already decided for 3.9.0. | |
| P13 | Narrow footer wraps badly. | 3.4.0 Setlist screenshot: "Changes the / show in / progress" in three lines. To check on 3.8.0. | Small, but it is the sentence that explains safety. |
| P14 | The file name is cut. | Ribbon shows `Festival_14fi…` at 1440 px wide. | The most important label is the one that is shortened. |

Not a problem, in spite of the reviews: History ("killer feature", yes, and it exists), the command palette (exists), the idea of routes (exists), the grey theme (cheap to keep).

---

## 4. Verdict on every recommendation

Status: **Built** (nothing to do), **Adopt**, **Adapt** (the idea, our way), **Defer**, **Reject**.

| # | Recommendation | From | Status | Note |
|---|---|---|---|---|
| 1 | Task-oriented Home with large job cards | ChatGPT A, Copilot 4 | **Built**, adapt | Six cards exist and match the groups. What is missing is state (section 7). |
| 2 | Home shows project, health, next step | ChatGPT 3 | **Adopt** | Section 7. Rule based, no score. |
| 3 | Persistent workspace header with save state, Doctor, undo | ChatGPT 6, Copilot 2, Gemini 2 | **Built**, adapt | Ribbon exists. Fix P1, P14, show the three states (section 6). |
| 4 | History always visible | Copilot 3 | **Built** | Sidebar list and panel. Polish only. |
| 5 | Editing, applying, saving as three visible states | ChatGPT 6 | **Adopt** | Section 6. |
| 6 | Preview before Apply, "what will happen" | ChatGPT 5C, Copilot 1, 7 | **Adopt** | Reducer, Setlist, Doctor have it. Make it one contract (section 8). |
| 7 | Disabled controls explain themselves | ChatGPT 5D | **Adopt** | `data-why` plus a test (section 8). |
| 8 | One primary action per screen | Copilot 1 | **Adopt** | Fixes P3. |
| 9 | Consistent page header | ChatGPT 5A | **Built**, adapt | `.page-h` exists; unify the 16 px title and the description wording. |
| 10 | Command palette | Copilot 10 | **Built** | Already ⌘K. Add recent tools to it. |
| 11 | Three type levels, 8 px grid | Copilot 9 | **Adapt** | Five levels, floor 11 px (section 5). Three is too few for tables and labels. |
| 12 | Subtle panels, soft borders, 8 px radius | Copilot 9 | **Adopt** | Radius is 10 and 6 now; keep 8 for cards, 6 for controls. |
| 13 | One semantic palette | Copilot 9, Gemini 3 | **Adapt** | Four semantics on a teal accent. No violet, magenta or cyan UI accents. |
| 14 | New primary accent (violet or blue) | ChatGPT 1 | **Reject** | The logo and every picture are teal. A rebrand changes nothing for the user. |
| 15 | Amber, cyan, emerald, coral as four UI accents | Gemini 3 | **Adapt** | Warning, success and error already exist. Function type colours stay in the badges only. |
| 16 | Function type badges, never plain text | Gemini 3 | **Adopt** | `.badge-Chaser` and its siblings exist; use them in Setlist, Porter and Doctor lists. |
| 17 | Modern font (Inter) | Gemini 3 | **Defer** | Swiss Knife works offline. A bundled variable font is about 300 KB and gives the same look on three systems. Decide at stage A. |
| 18 | Tailwind or a new frontend stack | Gemini 4 | **Reject** | ChatGPT says the same: no new framework. |
| 19 | Navigation as Inspect and Clean, Adapt and Build, Export and Stage | Gemini 1 | **Reject** | The Doctor gates every export and runs anywhere. Create and Run the show do not form a line. The routes already give an order when one is wanted. |
| 20 | Source file, arrow, working copy in the header | Gemini 2 | **Adapt** | Ribbon states in section 6. |
| 21 | "Commit step" with a micro-animation | Gemini 5 | **Adapt** | The verb stays *Apply to the show*. Feedback is a toast and the new History row lighting up, 150 ms. |
| 22 | Setlist as cards with match quality, drag handles, running time | Gemini 4 | **Adapt** | Rows exist with a dot. The matcher has four stages (exact, substring, token, fuzzy), so a pill "exact", "partial", "guess" is honest and cheap if the route returns the stage. Drag to reorder already exists in some form: check. Running time: later. |
| 23 | Function Porter in four steps with one subject each | Copilot 5 | **Adopt** | Section 9. The steps exist; the screen shows too much at once. |
| 24 | Modernise tables: hover, separators, zebra, narrower ID, stronger name | Copilot 6 | **Adapt** | `--zebra` and `--row-hover` exist. Apply to ID Browser, Dictionary, Trigger Manager and give ID columns a fixed narrow width. |
| 25 | Success previews (Rig Reducer, Brightness, Paperwork are the best) | Copilot 7 | **Adopt** | Before and after on Porter, Setlist and Look Builder. |
| 26 | Sidebar section labels with more contrast | Copilot 8 | **Adopt** | Small. |
| 27 | Estimated minutes on routes | Copilot 4 | **Reject** | Not measured. Show the number of steps; keep the Pub test figure where it was measured. |
| 28 | "Good evening. Let's get your show ready." | ChatGPT 3 | **Defer** | Charming, needs seven translations of time-of-day greetings. Not now. |
| 29 | Action-first onboarding ("Let's open your first show") | ChatGPT 9 | **Adopt** | State A of Home. |
| 30 | A universal "ready" status | ChatGPT 7 | **Reject** | ChatGPT itself warns against it. Home lists rule by rule. |
| 31 | Right-hand contextual panel on Home | ChatGPT 3 | **Reject** | History already has a panel. Another column costs width on a 1440 px laptop. |
| 32 | Remove tools to reduce complexity | none | Not proposed | All three reviews say keep them. |
| 33 | Accessibility audit | ChatGPT 10 | **Adopt** | P8. Stage pages get stricter rules (section 10). |
| 34 | Interactive prototype before touching code | ChatGPT 13 | **Done** | `mockup_D_v2.html`. |
| 35 | Do not change write behaviour in a visual redesign | ChatGPT 12 | **Adopt** | A standing rule for 3.9.5: no change to `core/`, to routes, or to what any button writes. Wording and structure only. |

---

## 5. Design direction and tokens

**Feel.** A lighting desk in a dim room. Calm dark surfaces, one teal accent for "this is what you do next", colour used for meaning, and light spent on content (fixtures, looks, stage), not on chrome.

**What changes in `tokens.css`**

| Token group | Today | Proposed |
|---|---|---|
| Type | `--fs-title 20, section 15, lead 14, body 13, ui 12, small 11, micro 10` | Five steps: **title 20, section 15, body 13, ui 12, small 11**. `lead` maps to body, `micro` to small. Nothing below 11 px except the 1 px ID gutter in the 3D views, which is drawn, not text. Page titles use `--fs-title` (today a literal 16). |
| Weight | mixed | 400 text, 600 labels and headings, 700 only for the page title |
| Spacing | 4/8/16/24/32/48 in tokens, 6/10/5/3 in use | Only the tokens in shared components. Tools keep their local spacing until they are migrated. |
| Radius | 10 and 6 | 8 (cards, panels), 6 (controls), 999 (pills only) |
| Surfaces | `--bg`, `--surface-0..2` | Same. Panels differ by surface step, borders become `--border` (soft); `--border-strong` only on focus and active |
| Accent | teal `#2dd4bf` | Same. Plus `--accent-ring` for focus: 2 px outline, 2 px offset |
| Semantic | success, warning, error (+soft) and orange for "replaces a file" | Same four, each with a **soft** background and a **text** colour that passes 4.5:1 on it, in all three themes. Test below |
| Function types | one colour per badge class on `--surface-1` | Same, used in lists (section 9) |
| Motion | none defined | `--t-fast 120ms`, `--t-med 200ms`; all wrapped in `@media (prefers-reduced-motion: no-preference)` |
| Stage pages | own CSS | Own tokens (section 10): higher contrast, larger type, 56 px targets |

**Buttons: four kinds, as in DESIGN v1.1.0, now enforced.** Primary (filled teal, one per screen), Secondary (outline), Ghost (toolbar), Danger (outline red, filled only in a confirm). The seven classes in use today (`btn-accent`, `-green`, `-red`, `-surface`, `-secondary`, `-overwrite`, `-danger`) fold into these four. *Replace* (orange) stays only for the Stage Monitor exception.

**Icons.** The sprite (`static/icons.svg`) for every button. Emoji go. Text stays, so a button is "icon + word". See the i18n note in section 13: the emoji are part of today's translation keys.

**Keyboard and screen readers.** `:focus-visible` ring everywhere; groups in the sidebar as `<nav>` with `aria-current` on the active tool; `aria-live="polite"` on the status line and on the Apply toast; the dot colours of the Doctor never carry meaning alone.

**Automatic checks (new, small).**

- `tests/test_tokens_contrast.py`: computes the WCAG ratio of every text and background pair declared in `tokens.css` for the three themes. Fails below 4.5 (7 for the stage tokens).
- `tests/test_ui_lint.py`: no `<button disabled>` that is an Apply without `data-why`; no inline `style` in the shell and in the page kit; no literal `font-size` below 11 px.

---

## 6. The show state, the ribbon and the three verbs

### Three states, shown the same everywhere

| State | Meaning | Where it shows | Word |
|---|---|---|---|
| **Draft** | You are choosing in a tool. Nothing has changed. | The tool's own footer: *Nothing applied yet* | (no verb) |
| **Applied** | The show in progress changed. Nothing is on disk. | Ribbon: *3 changes not saved*; History row; toast after Apply | **Apply to the show** |
| **Saved** | A new file was written. | Ribbon: *Saved as Festival_14fix_v2.qxw*; the original named as *never touched* | **Save as new file…** |

### The verbs that write

Today there are seven names for things that write. Four meanings are enough.

| Verb | Writes | Chip on the footer | Allowed in |
|---|---|---|---|
| **Apply to the show** | Nothing on disk. Changes the show in progress. | `Changes the show in progress` (teal) | tools that edit the show |
| **Save as new file…** | A new `_vN.qxw` with report and recipe. | `Writes a new file` (green) | ribbon only; tools may link to it |
| **Export…** | A file that is not a show: PDF, CSV, page, zip, `.txt`. The show is not touched. | `Does not change the show` (neutral) | any tool |
| **Save to settings** | Swiss Knife's own settings or a side file next to the show (dictionary, kit, layout, profile, `.stage.json`). | `Saved in your settings` or `Saved next to the show` (neutral) | tools that own such data |

The footer states which one a button is, before it is pressed. *Export a copy…* in Rig Reducer is an Export of the changed show as a `.qxw` that is not the show in progress; it keeps its name but gets the chip `Writes a new file`. *Save Songs* on the Setlist becomes *Save to settings* or *Apply*, depending on what it does: the audit in stage C decides, and the Setlist gets one primary only.

The Stage Monitor exception (it replaces its own earlier page after a yes) keeps its orange chip: `Replaces the earlier page, after asking`.

### The ribbon

Same contents as today, with three changes: more room for the file name, one grouped stats block, a Doctor pill that counts kinds.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ● Festival_14fix.qxw   opened, never touched      14 fixtures · 286 functions · 113 widgets          │
│   ▸ 3 changes, not saved     Doctor: 1 error · 4 kinds of warning        ⌘K   ↶ Undo  History  [ Save as new file… ] │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Part | Today | Proposed |
|---|---|---|
| File | Name cut at 170 px | At least 240 px, middle ellipsis (`Festival…_14fix.qxw`); a second line says `opened, never touched` or `Saved as <name>` |
| Stats | Three cards | One quiet line; below 1360 px they move into the file's tooltip |
| Changes | Card `0 CHANGES` | Text `3 changes, not saved` that opens History; teal dot when there are changes |
| Doctor | `1 · 856 DOCTOR ERR · WARN` | `1 error · 4 kinds of warning`. Hover: `856 warnings: D005 ×851, D004 ×4, D017 ×1`. Red only for errors; warnings amber; clean green with a check |
| Save | Filled teal button always | Filled when there are unsaved changes, outline when there are none |
| Open and Reload | Two buttons | One split button: **Open…** with *Reload from disk* and the recent shows in its menu |

The numbers in the wireframes are illustrative; the real count of kinds comes from the Doctor's rules. The ribbon reads `_show.doctor` (`error`, `warning` totals today); the Doctor screen groups by rule, so the per-rule counts exist in its report. Check in stage B that `/api/show/state` returns them or add the three lines that do.

---

## 7. Home that follows the state

Start keeps its two halves, **jobs** (the six cards) and **routes** (the guided sequences), and gains a top zone that depends on the state. Four states, picked by simple rules, in this order:

| # | Rule | Top zone says |
|---|---|---|
| A | No show open | *Open a show to start.* Drop zone, **Open workspace…**, **Open session…**, the five most recent shows with the date, fixtures and Doctor result (what Swiss Knife remembers). Under it: *No show yet? Quick Start builds one from your fixtures.* |
| B | A route is in progress | *You are on step 4 of 9 in Adapt a show to a new venue: Groups.* **Continue**, and *Leave the route*. |
| C | Show open, Doctor has errors | *Festival_14fix.qxw has 1 error to look at.* **Open the Doctor**. The warnings are named by kind, not counted. |
| D | Show open, changes not saved | *3 changes are not saved.* **Save as new file…**, **History**. |
| E | Show open, clean and saved | *Festival_14fix.qxw is ready. What next?* The six job cards, with the tools used last on top. |

If two rules fit, the first wins and the rest appear as small lines under it (a clean show with unsaved changes shows D, then nothing else). No score, no percentage, no "readiness": each line is one fact and one button.

**State A, no show open** (wireframe)

```
┌──────────────┬──────────────────────────────────────────────────────────────────────────────┐
│ SWISS KNIFE  │ ○ No show open                                       ⌘K          [ Open… ▾ ] │
│ ⌂ Start      ├──────────────────────────────────────────────────────────────────────────────┤
│ 1 New show   │                                                                              │
│   Quick Start│   Open a show to start                                                       │
│   Fixtures   │   Swiss Knife changes a copy. The file you open is never touched.            │
│ 2 Adapt …    │   ┌───────────────────────────────────────────────────────────────────┐      │
│ 3 Create …   │   │  Drop a .qxw here                                                 │      │
│ 4 Run …      │   │  [ Open workspace… ]  [ Open session… ]                           │      │
│ 5 Check …    │   └───────────────────────────────────────────────────────────────────┘      │
│ 6 Document   │   Recent                                                                     │
│              │   Festival_14fix.qxw   14 fixtures · 1 error      yesterday     [ Open ]     │
│ HISTORY      │   Pub_6fix_v3.qxw       6 fixtures · clean         Mon          [ Open ]     │
│  (empty)     │                                                                              │
│              │   No show yet?  Quick Start builds one from your fixtures →                  │
│              │                                                                              │
│              │   What Swiss Knife does                         (the six job cards, calm)    │
└──────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

**State C, show open with an error** (wireframe)

```
│ ● Festival_14fix.qxw  opened, never touched   14 · 286 · 113   Doctor: 1 error · 4 kinds   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│  Festival_14fix.qxw has 1 error to look at.                                                 │
│  D002  Two widgets use the same ID (VC widget 0).        [ Open the Doctor ]                │
│  Also: 4 kinds of warning, none blocks saving.           [ See them ]                       │
│                                                                                             │
│  What do you want to do?                                                                    │
│  ┌ 1 New show ───────┐ ┌ 2 Adapt a show ────┐ ┌ 3 Create ─────────┐                         │
│  │ …description…     │ │ …                  │ │ …                 │   (six cards, as today) │
│  │ Quick Start  …    │ │ Rig Reducer  …     │ │ Look Builder …    │                         │
│  └───────────────────┘ └────────────────────┘ └───────────────────┘                         │
│  Guided routes (Start a new show · Adapt to a new venue · Get ready for the gig · …)        │
```

Changes to the cards themselves: each shows its tools as chips (as now), and the **last-used** tool of the card is marked. The routes move below the cards, since the cards are the answer to "what do I want to do" and the routes the answer to "show me the order". Today the routes come first; with the state zone on top, the order becomes: state, jobs, routes, sessions.

Files: `templates/index.html` (Start section), `static/js/app.js` (`renderStart()` picks the state), `static/js/route.js` (`routeState()` already tracks the step), `static/js/session.js` (recents; add the Doctor result and the fixture count to the recent entry, `localStorage` `sk-recents`).

---

## 8. The page kit: one frame for every tool

Seven pieces. Each is a class set in a new `static/css/kit.css` (loaded after `tokens.css`) and a few lines of JS. Existing tools adopt them one at a time.

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ [icon] Rig Reducer                                                         [?]  [ ☾ ]     │  1  header
│        Adapt your show to a smaller rig.                                                  │     (title, one outcome sentence)
├───────────────────────────────────────────────────────────────────────────────────────────┤
│ toolbar: filters, mode, tool-specific controls                                            │  2  toolbar
├───────────────────────────────────────────────────────────────────────────────────────────┤
│                                                           ┌ What will change ────────────┐│
│   main work area                                          │ 6 fixtures removed           ││  3  work area
│   (table, canvas, editor: keeps its own layout)           │ 11 functions removed         ││  4  change panel
│                                                           │ Doctor: nothing new          ││
│                                                           └──────────────────────────────┘│
├───────────────────────────────────────────────────────────────────────────────────────────┤
│ [Changes the show in progress]  6 fixtures, 11 functions go.        [Export…]  [ Apply ]  │  5  action bar (sticky)
│ ⓘ Pick at least one fixture to remove.                                                    │  6  disabled reason
└───────────────────────────────────────────────────────────────────────────────────────────┘
   7  states: empty (no show), loading, done (toast: "Applied. 6 fixtures removed.  Undo · History")
```

| # | Piece | Rule |
|---|---|---|
| 1 | Header | Icon, title (`--fs-title`), one sentence that says the outcome ("Adapt your show to a smaller rig"), not the name again. Help (?) opens the wiki page for the tool. |
| 2 | Toolbar | Optional. Filters and view switches only; never an action that writes. |
| 3 | Work area | Free layout. The VC Visual Editor stays a canvas, the Trigger Manager a table, the Stage a 3D view. No big headers or cards inside them. |
| 4 | Change panel | Optional, right side or under the table. A sentence list produced from real data. Required when the tool has a footer Apply. |
| 5 | Action bar | Sticky. Left: the chip that names what the main button does (section 6) and the live summary. Right: at most one Secondary and one Primary. |
| 6 | Disabled reason | Any disabled Primary shows why in plain words next to it, from a `data-why` attribute. The tooltip is a backup. |
| 7 | States | Empty (no show open: *Open a show to use this tool*, with a button), loading, done (toast, History row lights up). |

Implementation notes.

- The footer exists already in six or more tools under the same sentence. Replace the copied markup with one helper, `skActionBar({chip, summary, secondary, primary, why})`, rendered by JS into a placeholder `<div data-actionbar>`. The summary is a function the tool provides, so it always shows real numbers.
- `data-why` is checked by `test_ui_lint.py`; the text goes through `i18n`.
- The footer must not wrap its sentence: the chip is one line, the summary may wrap. (P13.)
- Existing tools keep working while migrated: kit classes are additive, old classes stay until a tool moves.

**Tables** (ID Browser, Dictionary, Trigger Manager, Setlist, Doctor lists): row height 32 px, hover, subtle separators, zebra off by default and on in the dense tables, ID columns 56 px wide and monospace, the name column in `--text` at weight 600, type as a badge, the sticky header. No colour except for badges and states.

---

## 9. Key screens

For each: what is wrong, what changes, what must stay. Order by value.

### 9.1 Start

See section 7.

### 9.2 Workspace Doctor

- **Problem.** The Doctor is the strongest screen, but the first thing you see is a wall of rules, and the header pill counts 851 copies of one rule.
- **Change.** A summary row of three blocks: **Errors** (1), **Warnings** (4 kinds), **Info** (n kinds), each filterable. Each rule is one card with the rule's one-line meaning in plain words, the count, a *Show them* link and the fix choice. The footer reads `Fixes the show in progress`, with *Fix 853 selected* as the Primary and *Export a fixed copy…* as the Secondary.
- **Must stay.** Every rule ID, the tick boxes, the per-rule fix choices, the Copy report button.

### 9.3 Rig Reducer

- **Problem.** The "What will change" text is a small dense list on the right of a large table.
- **Change.** The list becomes the change panel of the kit: three counts on top (fixtures, functions, widgets), the Doctor result of the outcome, and a *Details* fold for the long list. Rows being removed fade to 40% and strike through (they do now); add *Keep all / Keep none* as a segmented control.
- **Must stay.** Preview before Apply, `Export a copy…`.

### 9.4 Function Porter

- **Problem (P11).** Step 3 shows two stages and the whole mapping table.
- **Change.** The step stays "3. Map", but opens on the mapping list only, one row per source fixture, with a small stage thumbnail beside the selected row. A *Show both stages* toggle (remembered) opens the two stage views above the list as today. Auto-map and match mode go in the toolbar. The footer's summary says `14 source fixtures: 9 mapped, 3 without exact match, 2 left out`.
- **Must stay.** The five steps and their numbering, *Mirror pan*, *Port this fixture*, the colour pairing between stages and rows.
- **Check later.** If the toggle is left on "both" most of the time, the default flips.

### 9.5 Setlist

- **Problem.** About a dozen buttons in the right rail, two filled buttons in the footer (P3).
- **Change.** The rail keeps its groups but collapses *Setlist TXT* and *Workspace* into folds that are closed by default. A song row shows the function badge, the match as a pill (exact, partial, guess) and, when it exists, the BPM from 3.8.0. The footer: **Apply to the show** is the only filled button; *Save Songs* is re-labelled once the audit says what it writes. *Tablet page…* moves out (section 10).
- **Must stay.** Slots, auto-match, the timing fields, import and paste.

### 9.6 Trigger Manager, ID Browser, Dictionary

Table styling only (section 8). Trigger Manager keeps its conflict highlighting. Dictionary's *Browse TXT* becomes *Load descriptions…*.

### 9.7 Show Paperwork, Brightness, Library, Stage and Meshes, VC Visual Editor, Look Builder

Header, action bar, chips and focus ring only. Canvas tools keep their layout. No change in what they do.

### 9.8 Tool names

Keep the names; add an outcome line in the header and in the Start cards (they have them already). A beginner would guess wrong on four names. Proposal, to be decided by giopas:

| Today | Possible | Note |
|---|---|---|
| Dictionary | Function notes | What it holds: a description per function. The wiki page and the sidebar change; Dictionary stays as a search word. |
| ID Browser | Function and widget list | |
| Wizard Repair | Finish a Show Wizard show | Matches the route name. |
| Library | Shared library | Optional. |

Other names stay: Quick Start, Rig Reducer, Function Porter, Look Builder, VC Visual Editor, Setlist, Trigger Manager, Workspace Doctor, Cabling, Show Paperwork. Each rename costs the sidebar, the page title, the palette, the Claude tool descriptions (no change in tool ids), the wiki and seven languages, so rename only what is confirmed.

---

## 10. Tablet on stage (the 3.9.0 pilot)

3.9.0 puts the Stage Monitor and the Setlist's *Tablet page…* behind one entry and adds song cards and role views. That makes it a new screen, so it is the best place to prove the kit before the other screens move.

### 10.1 What 3.9.0 builds on the new kit

Before the feature work, a small **step 0**: `static/css/kit.css` with the seven pieces of section 8 (header, toolbar, change panel, action bar, `data-why`, empty and done states, segmented control) and `skActionBar()`. It touches no existing screen. The new Tablet screen is its only user. If the pilot shows a flaw in the kit, it is fixed before 3.9.5 rolls it out. The cost is a day of CSS that 3.9.5 would have written anyway.

Not in step 0: tokens. The tablet screen uses the tokens as they are. 3.9.5 changes tokens for everyone at once.

### 10.2 The screen

One sidebar entry, **Tablet on stage** (group 4, Run the show), replacing *Stage Monitor*. Setlist's *Tablet page…* button becomes *Tablet on stage…* and opens it. The old wiki titles stay as redirects.

Two modes in a segmented control at the top:

| Mode | What it is | Needs |
|---|---|---|
| **Live monitor** | The Stage Monitor: follows QLC+ live; optional Control buttons. | QLC+ with web access, the tablet on the same network |
| **Simple page** | One `.html` with every song, ticked off by a tap, opened from AirDrop, mail or a drive. | Nothing; offline |

Settings that were set twice are set once and used by both: title, text size, colours (including the two black ones), the songs shown and their names on the page. Mode-only settings stay with their mode (Control, Safety hold, ports for Live; paper size is not needed).

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ [tablet] Tablet on stage                                                         [?]  [☾] │
│          Put tonight's setlist on a tablet for the band.                                   │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  ( Live monitor )  Simple page          Cue list: [ Set A ▾ ]    3 hidden · 21 shown       │
├──────────────────────────────────────────┬─────────────────────────────────────────────────┤
│ SONGS                                    │  [ Song card ]  Page  Send to the tablet        │
│  ☑ 1  Walk-in            ▸              │ ┌─────────────────────────────────────────────┐ │
│  ☑ 2  Intro               ▸              │ │ Card for  3 · Song 34                       │ │
│ ▌☑ 3  Song 34   ♪128  Drop D   ▾        │ │ Tuning        [ Drop D          ] ▲ differs │ │
│  ☐ 4  Song 30  (hidden)                  │ │ Tempo         128 BPM  from the Setlist     │ │
│  ☑ 6  Song 09   ♪96   E std    ▸        │ │ Starts        [ Drums, 4 bars count-in ]    │ │
│  ☑ 7  Song 08                  ▸        │ │ Per player    + Add: [Pedal / FX]           │ │
│                                          │ │   Guitar      Delay on, boost off           │ │
│  chips: ♪ tempo set · tuning · note      │ │ Note          Capo 2                        │ │
│                                          │ │ Use the Dictionary text  [ Song 34: … ] [+] │ │
│                                          │ └─────────────────────────────────────────────┘ │
├──────────────────────────────────────────┴─────────────────────────────────────────────────┤
│ [Saved next to the show]  Reads the show, writes the page and Gig.stage.json                │
│ ⓘ                                                       [ Preview ]  [ Export the page ]    │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

Right pane has three tabs, in this order, so that the job reads left to right:

1. **Song card.** Follows the song selected on the left. Fields as in the workplan: tuning, tempo (read from the Setlist, shown as a link back, not edited here), who starts and how, per player pedal or FX, a free note, and the Dictionary description offered as a start. A line `▲ differs from the song before` appears when the tuning changes, in the colour the tablet will use.
2. **Page.** Title, text size, colours, *Show the next cue / time / step numbers / step notes*, role views (below), and in Live mode the Control mode, Safety hold and the two ports.
3. **Send to the tablet.** The four numbered steps that are text now, as a checklist with a status each (QLC+ web reachable, page exported, server running), the addresses, a QR code if the encoder fits, *Preview*, *Export*, *Serve*.

Changes from the screen of 3.5.5, to keep the working parts: cue lists as tabs (not stacked cards), the step list with its hide and rename fields, the colour choices, the safety hold, the exception for replacing an earlier export (orange chip and the same confirm). Nothing about what is written changes: the page files and `<show>.stage.json`.

### 10.3 The pages on the tablet

The page is its own small app with its own rules, because it is read at arm's length, in dim light, by a player who is busy.

| Rule | Value |
|---|---|
| Text and background contrast | at least 7:1 for the current song, 4.5:1 for the rest, checked by the test |
| Touch targets | 56 px minimum (the VC Fit check uses 44 px for desktop consoles; the stage is harsher) |
| Type | The current song at least 10% of the screen height in portrait. Card text at least 28 px on a 10-inch tablet at default size |
| Colour never alone | A tuning change shows `▲ TUNING CHANGE` and the new tuning in text, not only in amber |
| Motion | None. The *Next song* banner appears and disappears; no sliding |
| Network loss | Unchanged: the dot, the grey song, the red note, the retry steps (1 s, 2 s, then 5 s) |

**Next song banner** (portrait, 800 × 1280)

```
┌────────────────────────────────────────┐
│ Festival                  ● Connected  │
│ [ Set A ] [ Set B ]            4 / 21  │
├────────────────────────────────────────┤
│  2  Intro                              │
│ ┌────────────────────────────────────┐ │
│ │ 3  Song 34          (playing)      │ │
│ └────────────────────────────────────┘ │
│  6  Song 09                            │
│  …                                     │
├────────────────────────────────────────┤
│ ┌────────────────────────────────────┐ │
│ │ NEXT UP                            │ │  appears when the step changes,
│ │ Song 09                            │ │  stays 6 seconds, or until the
│ │ ▲ TUNING CHANGE   Drop D → E       │ │  next step, whichever is first
│ │ 96 BPM · Drums count in, 4 bars    │ │
│ │ Guitar: delay on, boost off        │ │
│ └────────────────────────────────────┘ │
│ [ ◀ Previous ]  [ ■ Stop ]  [ Next ▶ ] │
└────────────────────────────────────────┘
```

**Commander view** (`?role=commander`, landscape 1280 × 800): cues on the left (current large, next below), the card of the next song on the right, Control buttons along the bottom. **Vocals** (`?role=vocals`): the current and next song names, the tempo and the note; no Control. **Band** (`?role=band`): the card in full, the cue list small.

Which field is shown to which role is a table in the Page tab, three columns of ticks. Default: Tuning, Tempo, Starts to everyone; Pedal or FX to the player named; Note to everyone.

### 10.4 What to decide before building

| Question | Recommendation |
|---|---|
| Do cards also appear in the Simple page? | Yes, as a fold under each song. The data is the same. **Decided yes, 21 October (giopas), built in 3.9.0**, together with views by role of your own (layout, fields, one player). |
| One renderer for both pages? | Only if cheap. Unify the entry and the settings in 3.9.0; leave renderers apart if merging needs a rewrite. |
| Role views: one page or separate files? | One page, the role in the address, as in the workplan. |
| QR code | Only with a small pure-Python encoder. Otherwise show the address in large type. |

---

## 11. Plain language (the old 3.8.5)

The aim from the workplan stays: a reader of 10 or 15 can follow each feature. This section adds how, now that the screens change first.

**Order inside the work.** In-app words are written with the screens in 3.9.5, because both change the same files and the seven language files change once. The wiki and README follow in 3.9.6 and use the new pictures.

### 11.1 In-app words (3.9.5, stage E)

| Where | Rule |
|---|---|
| Header sentence | One sentence, about the result: "Adapt your show to a smaller rig." The current long wording ("Keep some fixtures and remove the others, with their values, groups…") is cut to the outcome. |
| Tooltips (`data-tooltip`) | One sentence, up to 20 words. What happens, not how it is built. |
| Buttons | A verb and a thing: *Apply to the show*, *Save as new file…*, *Export the page*. No file extensions unless the person needs them. |
| Empty and disabled states | What to do next, as a sentence: *Open a show to use this tool.* |
| Terms | First use on a screen gets a short explanation in the tooltip or in a *What is this?* fold: chaser, step, fade, hold, BPM, beat, mesh, DMX universe, cue list. Same wording as the *Words used here* page. |
| No dashes as connectors, no marketing tone | As in the workplan. |

### 11.2 Wiki pages (3.9.6)

Every feature page has the same shape, so a reader learns it once.

1. **In one minute** box: what it is for, in everyday words, with a real gig as the example (a pub, a band of five, a pedal).
2. **Before you start**: what you need open and what it will not touch.
3. **Steps**: numbered, one action each, each with what you should see.
4. **A worked example** with the Festival and Pub shows.
5. **If it does not work**: the three usual causes.
6. **Words used here**: only the new terms, linked to the shared page.
7. Pictures from `tools/shots.py`, retaken after 3.9.5.

New shared page **Words used here**: about 40 terms in one sentence each, with a picture where a layout is clearer than words (the 3.8.0 Setlist section on tempo and Beats is the model).

README: three sentences on what Swiss Knife is; who it is for; the first ten minutes (install, open a show, Quick Start); then the tools in six groups, one line each; then links. History stays in the CHANGELOG.

### 11.3 Tests for the words

- **The Pub test for the docs**: someone who has never used the tool follows *Quick Start* and *Rig Reducer* pages and gets the result. Two people, one of them not a lighting person. Noted in the workplan as check D1.
- `tools/plain_check.py` (advisory, small): per page, the average sentence length (aim under 18 words), the longest sentence, a list of terms used before they are explained, any dash used as a connector, any page missing the *In one minute* box. It does not rewrite; it lists.
- Translations: the English texts are fixed first. Then `python tools/i18n_extract.py --missing <code>` for each of the seven languages, translated in one batch, Italian read by giopas.

---

## 12. Proposed changes to the workplan

### 12.1 Order

Today:

> 3.8.0 stage layouts and per-song tempo, 3.8.5 plain-language wiki and README, 3.9.0 Stage Monitor song cards and one Tablet entry, 3.10.0 teleprompter, 3.11.0 colour themes and porting by eye.

Agreed on 21 October (giopas asked for the swap; the plan keeps it, with a split):

| Release | Name | What | Why here |
|---|---|---|---|
| 3.8.0 | Stage layouts and per-song tempo | Released 20 October (tag `v3.8.0`). Nothing left to do. | The workplan now says so. |
| **3.9.0** | **Tablet on stage** | Song cards, *Next song* banner, role views, one entry. Step 0: `kit.css` and `skActionBar()`. | The screen changes first, as asked, and pilots the kit. |
| **3.9.5** | **A clearer Swiss Knife** | Stages A to E below: tokens, shell and Start, the kit on every tool, key screens, in-app words. No change to what anything writes. | After 3.9.0 so that the Tablet screen is designed once. |
| **3.9.6** | **Plain-language wiki and README** | The old 3.8.5, docs only, with new pictures. | The wiki shows the screens 3.9.5 changes; pictures and wording come after. |
| 3.10.0 | Teleprompter | Unchanged. Uses the kit. | |
| 3.11.0 | Colour themes and porting by eye | Unchanged. Porting by eye is also a good place to use the "what will change" panel. | |

Splitting 3.9.5 from 3.9.6 costs nothing: the wiki is a separate repository, and a docs-only release needs no installer test. It also lets the UI ship to users before the long writing work is done.

If giopas prefers one number for both, call it 3.9.5 and keep stage F (the wiki) last in the same branch; the cost is a longer branch and one release pipeline run for several weeks of writing.

### 12.2 3.9.5 in stages

Each stage ends green (tests, i18n, shots) and can be committed on its own. Nothing merges to `main` until all of A to E are done, as the workplan requires one branch per release.

| Stage | Scope | Files | Done when |
|---|---|---|---|
| **A. Foundation** | Type scale to five steps and floor 11 px; shared spacing; radii; semantic colours with soft and text pairs; `:focus-visible`; reduced motion; emoji to sprite icons; inline styles in the shell to classes; button classes folded into four; decide the font | `tokens.css`, `style.css`, `icons.svg`, `index.html` shell, `static/i18n/*` (key migration, section 13) | `test_tokens_contrast.py` and `test_ui_lint.py` green; the contact sheet from `tools/shots.py` before and after looks the same except for the type and the icons |
| **B. Shell and Start** | Ribbon (file room, Doctor by kind, save states, split Open); sidebar (recent tools, active bar, labels contrast, collapsible groups); Start state zone A to E; recents with date and Doctor result | `index.html`, `show.js`, `app.js`, `session.js`, `route.js`, the show state route | The five-second test: someone finds where to start in five seconds in each state. A to E each have a test of `renderStart()` for the rule order |
| **C. The kit on every tool** | `skActionBar` in every tool with a footer; chips and verbs (section 6); `data-why`; change panel where Apply exists; toast and History highlight; audit of every write button | each tool's template block and JS | `test_ui_lint.py`: every Apply has summary and `data-why`; the audit table of writing buttons is in the CHANGELOG; no change in `core/` or routes |
| **D. Key screens** | Doctor summary; Porter step 3; Setlist rail and badges; tables | `doctor.js`, `porter.js`, `setlist.js`, the table CSS | Pub test again from a clean profile in 12 minutes or less, same file as before byte for byte |
| **E. In-app words** | Header sentences, tooltips, empty states, tool names that are confirmed; seven languages | templates, `static/i18n/*` | `--missing` empty for all seven; the strings follow section 11.1 |

Regression rule for all stages (from ChatGPT, and the workplan's principles 1 to 4): no change to `core/`, to API routes or to what a button writes; recorded sessions replay to the same file; the full test suite stays green. Visual change comes with a before and after contact sheet from `tools/shots.py` in the release notes.

### 12.3 3.9.6 in steps

1. *Words used here* page.
2. README (three sentences, ten minutes, six groups).
3. The wiki pages in this order, by use: Quick-Start, Show-in-Progress, Rig-Reducer, Function-Porter, Setlist-Manager, Workspace-Doctor, Tablet-on-stage (new, replaces Stage-Monitor), Look-Builder, VC-Visual-Editor, Cabling, Show-Paperwork, then the rest. Each page to the template of 11.2.
4. Pictures with `tools/shots.py all`.
5. Docs Pub test (D1) with two readers.
6. `tools/plain_check.py` run; the list is cleared or accepted.

### 12.4 What changed in WORKPLAN.md (done on 21 October)

- Section 1: version 3.8.0; the new order agreed on 21 October.
- Section 2: 3.8.0 marked released; *3.9.0 Tablet on stage* with step 0 (the kit) first; new *3.9.5 A clearer Swiss Knife* and *3.9.6 Plain-language wiki and README* (the old 3.8.5, moved after the UI); the checks D1 to D3 sit in those entries.
- Section 4: a row for 3.8.0.
- Section 6: principle 9, a visual change does not change what a button writes.
- Section 7: two rows, *Verbs that write* and *Design*.

---

## 13. Risks, rejected ideas, open questions

### Risks

| Risk | Handling |
|---|---|
| **Emoji are in the translation keys.** The strings in `static/i18n/*` include the emoji ("📱 Tablet page…"). Removing the emoji from the template changes the key and loses seven translations. | Stage A starts with a script that strips the leading emoji from every key in the seven files and from the template in one commit, then a test that no key starts with an emoji. Check on a branch first. |
| A larger type floor (11 px) makes some dense screens overflow at 1100 px. | Check each tool at 1100, 1280, 1440 with the contact sheet. The tables scroll; the rails collapse (the existing media queries). |
| The kit gets the wrong shape in the pilot. | That is the point of 3.9.0 step 0. A change to the kit after 3.9.0 costs one screen. |
| Start's state rules hide the routes users like. | Routes stay on Start in every state, one scroll down. A user setting *Show routes first* is possible later; not now. |
| Doctor by kind hides how many places a rule hit. | The hover and the Doctor screen keep the numbers. |
| The restyle changes screenshots and so all docs. | The reason the wiki comes after, in 3.9.6. |
| Scope creep: "while we are here". | Rule 35: no behaviour change in 3.9.5. Ideas go to the wishlist. |

### Rejected, on purpose

A violet or blue accent; amber, cyan and magenta as UI colours; Tailwind or any framework; Gemini's three-stage navigation; "estimated minutes" on routes; a right-hand panel on Start; a readiness score; removing or hiding any tool.

### Open questions for giopas

1. One number (3.9.5) or two (3.9.5 and 3.9.6)? Recommendation: two.
2. Which tool renames of 9.8, if any? Recommendation: Dictionary and Wizard Repair only if you are comfortable with the wiki redirects.
3. Bundle a font (Inter variable, about 300 KB) or keep the system font? Recommendation: bundle, if the licence file goes in the package; otherwise keep the system font.
4. *Save Songs* on the Setlist: what exactly does it write, and is it still needed beside *Save setlist…*? The audit in stage C needs your answer.
5. Cards in the Simple page: yes or no (10.4)?
6. Is the grey theme used? If not, dropping it halves the colour checking.
