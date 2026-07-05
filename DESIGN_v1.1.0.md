# QLC+ Swiss Knife — v1.1.0 GUI Redesign

Goal: turn "nine tools in a tab bar" into one coherent, guided app. Big visual jump, same Flask + vanilla JS stack (no framework — lightness preserved).

---

## 1. What's wrong today (honest audit)

**No entry experience.** First launch shows an empty dark screen, a path input, and 9 tabs. Nothing explains what the tool does, what to load, or where to start. The header path-paste input is developer UX, not user UX.

**File loading is scattered across 7 places.** Workspace in the header; session hidden in a modal; dictionary `.txt` in the Dictionary toolbar; slot `.txt` files inside Setlist actions; QXF paths in both Fixtures and Brightness toolbars; source/destination QXW inside Merger. There is no single answer to "what is loaded right now?"

**Flat navigation with historical order.** The 9 tabs are ordered by when they were written, not by what users do. Setlist (show prep) sits next to Merger (file surgery). α/β superscripts are the only hint of maturity. No grouping, no hierarchy.

**Inconsistent visual language.** Emoji as icons (different weight/color per platform), 4+ button styles used interchangeably, inline styles everywhere, VC Editor ships its own scoped stylesheet with different paddings and font sizes. Toolbars vary: 1 row (Checklist), 2 rows (Fixtures), toolbar + help banner (Brightness), load bar + toolbar (Merger).

**Tooltips carry the whole UX.** Critical distinctions live only in `data-tooltip`: e.g. Triggers "Save to QXW" *overwrites* the loaded file while every other Save writes a new file — visually identical buttons.

**No guidance on prerequisites.** Buttons are just `disabled` with no explanation of *why* or what to load to enable them.

---

## 2. New information architecture

Tools regrouped by **user intent**, not build history:

| Group | Tools | Question it answers |
|---|---|---|
| **Start** | Home (new) | "What do I want to do?" |
| **Run the show** | Setlist · Triggers · Dictionary | "I have a gig" |
| **Build the rig** | Fixtures · Checklist · Brightness | "I'm setting up hardware" |
| **Workspace tools** | ID Browser · VC Visual Editor · Merger | "I need to inspect/transform the file" |

### The Home screen (the core of 1.1.0)

One page, three zones:

1. **Open** — a large drop zone + three explicit entry points: *Open Session (.qsk)* (primary, restores everything), *Open Workspace (.qxw)*, *Recent sessions* list. Path-paste stays but demoted to a small "advanced" row.
2. **Loaded files panel** — always shows workspace / dictionary / session / QXF overrides as chips with name, dirty dot, and a *Change* action. This replaces the session modal + header clutter and becomes the single source of truth.
3. **Guided task cards** — plain-language verbs, grouped as above: "Build a setlist for a gig", "Map keys & MIDI", "Print a patch checklist", "Fix an overpowered fixture", "Tidy the Virtual Console", "Copy functions between shows"… Each card states its file requirement; if missing, the card isn't dead — it says *"Needs a workspace → Open one"*.

### Tool pages — one uniform template

Every tool gets the same skeleton:

- **Page header**: icon + name + one-line "what this does" + maturity badge (α/β as a real pill, not superscript) + the page's *primary action* right-aligned.
- **Body**: the tool's existing layout (they're mostly fine functionally).
- **Output footer** (only where files are produced): explicit, color-coded semantics — 🟢 *"Writes a NEW file"* vs 🟠 *"Overwrites the loaded file"* (Triggers). Never again hidden in a tooltip.
- **Empty state**: every tool shows the same styled placeholder with a direct CTA ("Open a workspace to start → ") instead of grey text.

---

## 3. Design system (one file: `tokens.css`)

- **Spacing**: 4/8/12/16/24 scale only. **Radius**: 6px controls, 10px cards.
- **One accent** (electric blue/violet), semantic colors: green = safe/new-file, orange = overwrite, red = destructive. Everything else neutral surfaces (3 elevations).
- **Icons**: single inline-SVG set (Lucide-style, stroke 1.75) replacing all emoji. Consistent 16px in buttons, 20px in nav, 28px on cards.
- **Buttons**: exactly 4 kinds — Primary (filled accent), Secondary (outlined), Ghost (toolbar), Destructive. Disabled buttons get a `title`-less inline hint when hovered: "Load a workspace first".
- **Typography**: UI sans for chrome, mono only for data (IDs, paths, tables).
- **Theme**: keep Dark default + Light; drop the third "Grey" (cheaper to maintain, coherent).

## 4. Lightness

No framework. The redesign is: one Home screen (new HTML/JS module ~300 lines), one shared shell (sidebar/nav + files bar), one `tokens.css` replacing scattered inline styles, and per-tab markup mostly untouched. Grid.js stays. Net page weight goes *down* (emoji tooltips CSS + 3rd theme removed).

## 5. Suggested build order

1. `tokens.css` + SVG icon sprite + button/badge/empty-state classes.
2. Shell: sidebar (or grouped nav) + Files bar (absorbs header + session modal).
3. Home screen with Open zone, recents, task cards.
4. Migrate tabs one by one to the page-header/footer template (Checklist first — smallest; Setlist last — biggest).
5. Output-footer semantics on Triggers/Setlist/Brightness/Merger/VC Editor.

---

*Two clickable mockups accompany this doc: `mockups/mockup_A_hub.html` (hub-and-spoke, top nav) and `mockups/mockup_B_sidebar.html` (persistent sidebar shell).*
