"""
core/mcp_guide.py
=================
The documentation of Claude's Swiss Knife tools, in one place (v3.0.1).

* ``GUIDE``: for every tool, what it is for, its arguments, what it answers,
  and an example.  Claude reads it with the ``guide`` tool or as the MCP
  resources ``swissknife://guide`` and ``swissknife://guide/<tool>``.
* ``PROMPTS``: ready requests Claude Desktop can offer from the connection
  (MCP prompts), the same requests the app copies with *Ask Claude…*.
* :func:`wiki_page` writes ``wiki/Claude-Tools.md`` from the same text, so
  the wiki and what Claude reads never drift apart (a test checks it).
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ── one entry per tool ─────────────────────────────────────────────────────────
# "use": when to call it; "args": [(name, text)]; "returns"; "example"; "notes"

GUIDE: Dict[str, dict] = {
    "guide": {
        "use": "Read this guide: the arguments, answers and an example for any tool, or the list of all of them.",
        "args": [("topic", "A tool name (e.g. `edit_vc`), `edit_vc:<op>` for one Virtual Console operation, "
                           "`workflows` for the usual sequences, or empty for the index.")],
        "returns": "Plain text.",
        "example": '{"topic": "edit_vc:create"}',
    },
    "list_shows": {
        "use": "Find the .qxw shows in the folders the user shared with Claude, newest first.",
        "args": [("query", "Keep only the paths that contain this text (a venue, a folder, a show name)."),
                 ("limit", "How many to return (default 25, at most 200)."),
                 ("offset", "Skip this many; use `next_offset` from the previous answer.")],
        "returns": "`folders`, `total`, `shows` [{path, name, bytes, modified}], `next_offset` when there are more, "
                   "`problems` when a folder could not be read.",
        "example": '{"query": "Liquid", "limit": 10}',
    },
    "open_show": {
        "use": "Open a show to work on. Everything after this works on this show in progress.",
        "args": [("path", "Full path of a .qxw inside a shared folder (from `list_shows`).")],
        "returns": "A summary of the show: fixtures, functions, widgets, Doctor counts, the suggested next file name.",
        "example": '{"path": "/Users/me/Shows/Club/Club_v3.qxw"}',
        "notes": "The file on disk is never changed. The Swiss Knife window does not show this session: "
                 "the user opens the saved file there afterwards.",
    },
    "show_summary": {
        "use": "Say what is open now: name, steps, unsaved changes, Doctor counts, a short overview.",
        "args": [],
        "returns": "`open`, `show` (steps, unsaved, doctor, suggested_name) and `overview`.",
    },
    "doctor_check": {
        "use": "Run the Workspace Doctor on the show in progress.",
        "args": [],
        "returns": "`by_code` counts and up to 30 findings sorted errors first: key, code, severity, location, "
                   "message, fixable, default (ticked by default).",
        "notes": "Pass the `key` of a finding to `doctor_fix`.",
    },
    "doctor_fix": {
        "use": "Fix Doctor findings in the show in progress (one History step).",
        "args": [("keys", "The `key` of each finding to fix. Without keys: every finding the Doctor ticks by default."),
                 ("options", "Choices for the fixes that have one, by code in lower case, e.g. "
                             '`{"d003": "rewire", "d015": "rename"}`. Without options the Doctor\'s default choice is used.')],
        "returns": "What was done, the Doctor counts after, the History step.",
        "example": '{"keys": ["D016|Function 30 \'Spare\'|Scene not used by any function or VC widget"]}',
        "notes": "A fix that would leave new errors is refused.",
    },
    "rig_fixtures": {
        "use": "List the fixtures of the show in progress (id, name, universe, address). Use it before `reduce_rig`.",
        "args": [],
        "returns": "A list of fixtures.",
    },
    "reduce_rig": {
        "use": "Shrink the rig to the fixtures you keep; what only the dropped fixtures used goes too.",
        "args": [("keep", "Fixture ids to keep."),
                 ("repatch", 'Optional new name, universe or address per kept fixture: `{"6": {"name": "DR: Drums", "address": 1}}`.'),
                 ("preview", "true: say what would be removed and change nothing.")],
        "returns": "The preview, or what was removed and the Doctor counts after.",
        "example": '{"keep": ["6", "7", "8"], "preview": true}',
    },
    "source_functions": {
        "use": "Open another show as the source for porting and list its functions.",
        "args": [("source_path", "The other .qxw, in a shared folder."),
                 ("query", "Keep the functions whose name contains this."),
                 ("type", "Keep one type: Scene, Chaser, Collection, EFX, RGBMatrix, Script, Sequence.")],
        "returns": "id, name, type and folder path of each function.",
    },
    "port_functions": {
        "use": "Bring functions, with everything they need, from another show into the show in progress.",
        "args": [("source_path", "The other .qxw."),
                 ("function_ids", "Ids from `source_functions`."),
                 ("strategy", "How source fixtures map onto yours: `fan_in` (default, many to fewer), `same_id` or `all`."),
                 ("options", "Extra Porter plan fields: `name_prefix`, `vc` (bring the buttons), `drop_unmapped`, …"),
                 ("preview", "true: validate only.")],
        "returns": "What was ported and the Doctor counts after.",
        "example": '{"source_path": "/Users/me/Shows/Festival.qxw", "function_ids": ["12", "40"], "preview": true}',
    },
    "looks_options": {
        "use": "See what the Looks builder offers for this show before `build_looks`.",
        "args": [],
        "returns": "Fixture groups, palettes, patterns (all, alternate, chase, pingpong, buildup, random), "
                   "note lengths (1/1 to 1/16), positions.",
    },
    "build_looks": {
        "use": "Build looks (scenes) and chasers with their Virtual Console buttons.",
        "args": [("looks", "[{group, colours, level, position}]: group from `looks_options`, colours as names or #RRGGBB, level 0 to 1."),
                 ("chasers", "[{group, pattern, colours, bpm, note, fade, fade_pct, name}]."),
                 ("matrices", "RGB matrices, as in the Looks tool."),
                 ("folder", "Function folder (default `Look Builder`)."),
                 ("vc_page", "Page for the buttons (made when missing)."),
                 ("nomenclature", "`plain` (default) or a naming profile."),
                 ("check_only", "true: check and change nothing.")],
        "returns": "What was built and the Doctor counts after.",
        "example": '{"looks": [{"group": "all", "colours": ["amber", "blue"], "level": 1}], '
                   '"chasers": [{"group": "all", "pattern": "pingpong", "colours": ["red"], "bpm": 120}], "vc_page": "Looks"}',
    },
    "vc_pages": {
        "use": "List the Virtual Console pages and their frames (ids you need for `edit_vc`).",
        "args": [],
        "returns": "`pages` [{caption, id, frames [{caption, id, depth}]}] and `duplicate_ids`.",
    },
    "edit_vc": {
        "use": "One Virtual Console edit (one History step each). Read `guide` with `edit_vc:<op>` for one operation.",
        "args": [("op", "The operation, see below."),
                 ("…", "The arguments of that operation, at the same level as `op`.")],
        "returns": "`result` with the new ids (`new_ids`, `page_id`), what was wired, and the Doctor counts.",
        "example": '{"op": "create", "parent_id": "9704", "kind": "Button", "caption": "AD · Rock Loop", '
                   '"x": 10, "y": 40, "w": 260, "h": 90, "func_id": "104", "bg_color": "#9ED8FF"}',
        "notes": "Positions are in pixels inside the parent; without x and y the first free spot is used. "
                 "A SoloFrame lets one button play at a time.",
    },
    "setlist": {
        "use": "Turn a setlist into the cue list chaser: songs are matched to the show's functions by name.",
        "args": [("songs", "Song titles in order."),
                 ("text", "Or a pasted list (numbering and set breaks are understood)."),
                 ("slot", "Which CueList slot (default the first)."),
                 ("rows", "Override the matches: [{txt_name, qxw_id, in, hold, out}]."),
                 ("apply", "false: only show the matches."),
                 ("target_chaser_id", "The chaser to fill (default the slot's own).")],
        "returns": "The matches, then what was built and `left_out` (songs with no function).",
        "notes": "Show the matches to the user before applying. Each cue note names the button that plays the same look.",
    },
    "compare": {
        "use": "Compare the show in progress with another .qxw (read only).",
        "args": [("path", "The other .qxw.")],
        "returns": "A plain-text report of the differences (cut at 9000 characters).",
    },
    "dictionary_context": {
        "use": "Read what every function is, to write the Dictionary.",
        "args": [("only_missing", "Only the functions without a description."),
                 ("skip_steps", "Hide helper steps (steps of a chaser or collection with no button)."),
                 ("type", "One function type."), ("query", "Name contains."), ("frame", "VC frame name contains."),
                 ("limit", "Page size (default 60); pages also stop before a reply would be cut."),
                 ("offset", "Use `next_offset`.")],
        "returns": "For each function: id, name, type, description, vc_button, vc_frames, facts (steps, colours "
                   "read from the fixture definitions, what a script starts), used_by.",
        "notes": "Write one short plain sentence per function, only from the facts and names. Show the user a "
                 "table before storing unless they asked you to just do it.",
    },
    "dictionary_set": {
        "use": "Store descriptions (in memory; `dictionary_save` writes the file).",
        "args": [("entries", "[{id, description}]."),
                 ("overwrite", "Replace descriptions that exist (default: keep them)."),
                 ("auto_steps", "Describe the helper steps: \"Step 3 of Rock Loop. Red on …\"."),
                 ("draft_missing", "Give every function still without a description the app's own first draft.")],
        "returns": "`set`, `kept_existing`, `unknown_ids`, how many were drafted.",
        "example": '{"entries": [{"id": "104", "description": "Three-step rock chase for driving songs."}], '
                   '"auto_steps": true, "draft_missing": true}',
    },
    "dictionary_load": {
        "use": "Load an existing dictionary .txt (ID|Name|Description) to extend it.",
        "args": [("path", "The .txt, in a shared folder.")],
        "returns": "How many descriptions were loaded.",
    },
    "dictionary_save": {
        "use": "Write the Dictionary as a NEW .txt (`<show>_dictionary.txt`, then `_v2` …).",
        "args": [("where", "A folder or a .txt path (default: next to the opened show).")],
        "returns": "`saved`: the path written.",
    },
    "show_history": {
        "use": "List the steps made so far on the show in progress.",
        "args": [],
        "returns": "Each step: tool, title, Doctor counts after it.",
    },
    "undo": {
        "use": "Go back to before step n (default: the last step).",
        "args": [("n", "The step number from `show_history`.")],
        "returns": "The show status after.",
    },
    "redo": {"use": "Redo what was undone.", "args": [], "returns": "The show status after."},
    "save_show": {
        "use": "Save the show in progress as a NEW .qxw with its report and recipe.",
        "args": [("where", "A folder or a .qxw path (default: next to the opened show).")],
        "returns": "`saved`, `report`, `recipe`, the Doctor counts.",
        "notes": "Never overwrites: a taken name becomes _v2, _v3. Setlist cue notes are brought up to date first.",
    },
}

# ── the operations of edit_vc ─────────────────────────────────────────────────

EDIT_VC_OPS: Dict[str, str] = {
    "create": "parent_id (page or frame id), kind (Button, Frame, SoloFrame, Slider, Label, CueList), caption, "
              "x, y, w, h (optional), func_id (wire a Button to a function), bg_color (#RRGGBB).",
    "wire": "widget_id, func_id: make a button start a function.",
    "delete": "ids: widgets to remove (with what is inside a frame).",
    "duplicate": "ids, keep_bindings (copy key and MIDI bindings too; default no).",
    "copy": "ids, target_id (page or frame), x, y, keep_bindings.",
    "move": "ids, target_id, x, y.",
    "new_page": "caption: an empty page styled like the first one; answers `page_id`.",
    "copy_page": "page_id, caption, keep_bindings.",
    "rename_page": "page_id, caption.",
    "move_page": "page_id, index (0 = first).",
    "delete_page": "page_id.",
    "label_panel": "parent_id, lines (texts), columns, title, label_w, label_h: a frame of labels, e.g. a legend.",
    "auto_arrange": "frame_id, profile (naming profile), columns: lay the buttons out in rows by name prefix.",
    "screen": "profile_id (macbook, fullhd, tablet, ipad), page_ids, scale: size pages for a screen.",
    "apply_template": "name, caption: add a saved VC template as a page.",
    "setlist_cuelist": "chaser_id, cuelist_id, page_id: show a setlist chaser in a CueList widget.",
    "fix_ids": "(no arguments): give duplicate widget ids new ones.",
}

WORKFLOWS = """Usual sequences:

- Check a show: list_shows → open_show → doctor_check → doctor_fix → save_show.
- Smaller venue: open_show → rig_fixtures → reduce_rig (preview) → reduce_rig → doctor_check → save_show.
- Bring looks from another show: source_functions → port_functions (preview) → port_functions → save_show.
- New looks and buttons: looks_options → build_looks (check_only) → build_looks → vc_pages → save_show.
- Buttons for existing functions: vc_pages → edit_vc new_page → edit_vc create (SoloFrame) → edit_vc create (Button, func_id) → save_show.
- Tonight's setlist: setlist (apply=false) → show the matches → setlist → save_show.
- Dictionary: dictionary_context → dictionary_set (auto_steps, draft_missing) → dictionary_save.

Every change is a History step (show_history, undo). Only save_show and dictionary_save write files, always new ones."""

# ── ready requests (MCP prompts) ──────────────────────────────────────────────

PROMPTS: List[dict] = [
    {"name": "write_dictionary", "title": "Write the Dictionary of a show",
     "description": "Describe every function of a show and save the dictionary next to it.",
     "arguments": [{"name": "show", "description": "Path or name of the .qxw", "required": True}],
     "text": ('Using the QLC+ Swiss Knife tool, open "{show}" and write its Dictionary. Call dictionary_context, '
              "write one short plain sentence for each function that has a button or that I would recognise on stage, "
              "then call dictionary_set with your entries, auto_steps=true and draft_missing=true so the rest gets a "
              "first draft. Show me the descriptions you wrote, then save with dictionary_save next to the show.")},
    {"name": "check_show", "title": "Check and fix a show",
     "description": "Run the Doctor, explain the findings, fix what is safe and save a new file.",
     "arguments": [{"name": "show", "description": "Path or name of the .qxw", "required": True}],
     "text": ('Using the QLC+ Swiss Knife tool, open "{show}", run the Doctor and tell me in plain words what is '
              "wrong. Fix what can be fixed safely, tell me what you left and why, and save it as a new file.")},
    {"name": "smaller_venue", "title": "Adapt a show to fewer fixtures",
     "description": "Keep some fixtures, preview what goes, then reduce and save.",
     "arguments": [{"name": "show", "description": "Path or name of the .qxw", "required": True},
                   {"name": "keep", "description": "The fixtures to keep (ids or names)", "required": True}],
     "text": ('Using the QLC+ Swiss Knife tool, open "{show}" and list its fixtures. I keep these: {keep}. '
              "Show me what would be removed, wait for my OK, then reduce the rig, fix what the Doctor finds and save.")},
    {"name": "song_buttons", "title": "Buttons for looks that have none",
     "description": "Find the chasers and scenes the setlist uses that have no button and put them on a page.",
     "arguments": [{"name": "show", "description": "Path or name of the .qxw", "required": True}],
     "text": ('Using the QLC+ Swiss Knife tool, open "{show}". Find the functions the setlist plays that no Virtual '
              "Console button starts. Show me the list, then add a page with a one-look-at-a-time frame and one button "
              "per function, in setlist order, and save.")},
]


def prompt_text(name: str, args: Optional[dict] = None) -> str:
    p = next((x for x in PROMPTS if x["name"] == name), None)
    if p is None:
        raise KeyError(name)
    vals = {a["name"]: str((args or {}).get(a["name"]) or f"<{a['name']}>") for a in p["arguments"]}
    return p["text"].format(**vals)


def dictionary_request(show: str, mode: str = "buttons", review: bool = True, dictionary: str = "") -> str:
    """The request the Dictionary's *Ask Claude…* window copies.  *mode*:
    ``buttons`` (own words for the functions with a button, a draft for the
    rest), ``missing`` (only the functions without a description) or ``all``
    (rewrite every description)."""
    parts = [f'Using the QLC+ Swiss Knife tool, open "{show}" and write its Dictionary.']
    if dictionary:
        parts.append(f'First load the dictionary "{dictionary}" with dictionary_load and keep what it says '
                     "unless I ask otherwise.")
    if mode == "missing":
        parts.append("Call dictionary_context with only_missing=true and write one short plain sentence for each of "
                     "those functions, then call dictionary_set with your entries and auto_steps=true. Keep every "
                     "description that is already there.")
    elif mode == "all":
        parts.append("Call dictionary_context and write one short plain sentence for every function, then call "
                     "dictionary_set with your entries, overwrite=true and auto_steps=true.")
    else:
        parts.append("Call dictionary_context, write one short plain sentence for each function that has a button "
                     "or that I would recognise on stage, then call dictionary_set with your entries, auto_steps=true "
                     "and draft_missing=true so the rest gets a first draft.")
    parts.append("Show me the descriptions you wrote and wait for my OK, then save with dictionary_save next to the show."
                 if review else "Then save with dictionary_save next to the show without asking me first.")
    return " ".join(parts)


PROMPTS[0]["text"] = dictionary_request("{show}")          # one text for the prompt and the app's window


# ── rendering ─────────────────────────────────────────────────────────────────

def tool_text(name: str, title: str = "", reads: Optional[bool] = None) -> str:
    g = GUIDE.get(name)
    if g is None:
        raise KeyError(name)
    head = f"{name}" + (f" ({title})" if title else "")
    if reads is not None:
        head += ", reads only" if reads else ", changes the show in progress"
    lines = [head, "", g["use"]]
    if g.get("args"):
        lines += ["", "Arguments:"] + [f"- {a}: {t}" for a, t in g["args"]]
    else:
        lines += ["", "No arguments."]
    if name == "edit_vc":
        lines += ["", "Operations:"] + [f"- {op}: {txt}" for op, txt in EDIT_VC_OPS.items()]
    if g.get("returns"):
        lines += ["", "Answers: " + g["returns"]]
    if g.get("example"):
        lines += ["", "Example: " + g["example"]]
    if g.get("notes"):
        lines += ["", "Note: " + g["notes"]]
    return "\n".join(lines)


def index_text(tools: List[dict], titles: Dict[str, str], read_only: set) -> str:
    out = ["QLC+ Swiss Knife: the tools. Call guide with a tool name for its arguments and an example.", ""]
    for t in tools:
        n = t["name"]
        out.append(f"- {n} ({titles.get(n, n)}, {'reads' if n in read_only else 'changes'}): {GUIDE[n]['use']}")
    out += ["", WORKFLOWS]
    return "\n".join(out)


def answer(topic: str, tools: List[dict], titles: Dict[str, str], read_only: set) -> str:
    topic = (topic or "").strip()
    if not topic or topic in ("index", "tools", "all"):
        return index_text(tools, titles, read_only)
    if topic == "workflows":
        return WORKFLOWS
    if topic.startswith("edit_vc:"):
        op = topic.split(":", 1)[1].strip()
        if op not in EDIT_VC_OPS:
            return f"Unknown operation {op!r}. Operations: {', '.join(EDIT_VC_OPS)}."
        return f'edit_vc op "{op}": {EDIT_VC_OPS[op]}\nCall edit_vc with {{"op": "{op}", …}}.'
    if topic in GUIDE:
        return tool_text(topic, titles.get(topic, ""), topic in read_only)
    return f"No guide for {topic!r}. Topics: {', '.join(GUIDE)}, workflows, edit_vc:<op>."


def wiki_page(tools: List[dict], titles: Dict[str, str], read_only: set) -> str:
    """The wiki page ``Claude-Tools.md``, from the same text Claude reads."""
    md = ["# 🤖 Claude's tools", "",
          "This page lists every tool Claude can use through the Swiss Knife connection: what it is for, "
          "its arguments, what it answers and an example. Claude reads the same text with the `guide` tool, "
          "so the two never differ. Setting up the connection is on [[Connect Claude to Swiss Knife]].", "",
          "*This page is written by `python tools/make_claude_tools_wiki.py`; edit `core/mcp_guide.py`, not this page.*", "",
          "## Ready requests", "",
          "Claude Desktop can offer these from the Swiss Knife connection. The Dictionary's **🤖 Ask Claude…** "
          "button copies the first one with your show filled in.", "",
          "| Request | What Claude does |", "|---|---|"]
    for p in PROMPTS:
        md.append(f"| {p['title']} | {p['description']} |")
    md += ["", "## Usual sequences", "", WORKFLOWS.split("\n", 2)[2], "",
           "## The tools", "",
           "*Reads* tools only look. *Changes* tools change the show in progress, which you can undo; "
           "only `save_show` and `dictionary_save` write a file, and always a new one.", "",
           "| Tool | Name in Claude | Kind | What it does |", "|---|---|---|---|"]
    for t in tools:
        n = t["name"]
        md.append(f"| `{n}` | {titles.get(n, n)} | {'Reads' if n in read_only else 'Changes'} | {GUIDE[n]['use']} |")
    for t in tools:
        n = t["name"]
        g = GUIDE[n]
        md += ["", f"### `{n}`", "", g["use"], ""]
        if g.get("args"):
            md += ["| Argument | Meaning |", "|---|---|"] + [f"| `{a}` | {txt} |" for a, txt in g["args"]]
        else:
            md.append("No arguments.")
        if n == "edit_vc":
            md += ["", "| Operation | Arguments |", "|---|---|"] + [f"| `{op}` | {txt} |" for op, txt in EDIT_VC_OPS.items()]
        if g.get("returns"):
            md += ["", "Answers: " + g["returns"]]
        if g.get("example"):
            md += ["", "```json", g["example"], "```"]
        if g.get("notes"):
            md += ["", g["notes"]]
    return "\n".join(md) + "\n"
