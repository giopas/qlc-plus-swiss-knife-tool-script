"""core/mcp_server.py — Swiss Knife as an MCP server (WORKPLAN Phase 4, v2.9.0).

Lets Claude (Desktop, Code…) drive the same tools you use in the window:
open a show, run the Doctor, reduce a rig, port functions, build looks,
edit the Virtual Console, apply a setlist, compare, undo — and save the
result as a **new** file.  The original is never touched.

* Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP "stdio").
  No third-party package: the protocol part Swiss Knife needs is small.
* stdout carries the protocol only.  Anything a tool prints goes to stderr.
* Every tool calls the app's own API in-process (``create_app().test_client()``),
  so each change is a step in History *and* in the recipe — the saved file
  comes with ``<name>.recipe.json`` and ``python -m core.recipe replay``
  rebuilds it byte for byte.
* One show in progress per server.  Only the folders listed in
  Settings › Connect to Claude (``~/.qlc_swiss_knife/mcp.json``) can be read
  or written.

Run:  ``python -m core.mcp_server``   (or ``QLC-Swiss-Knife --mcp``)
      ``--folder DIR``   share DIR for this run only
      ``--selftest``     start, talk to itself, exit 0/1 (used by the release build)
"""

from __future__ import annotations

import io
import json
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

from core import mcp_config

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_TEXT = 14000                       # characters returned by one tool call


class ToolError(Exception):
    """A tool failed in a way Claude should read and act on."""


def _version() -> str:
    from core.workspace import VERSION
    return VERSION


def _text(obj: Any) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if len(s) > MAX_TEXT:
        s = s[:MAX_TEXT] + f"\n… (cut: {len(s) - MAX_TEXT} more characters; ask for less, or filter)"
    return s


def _brief(obj: Any, depth: int = 0) -> Any:
    """A short view of a big state dict: scalars kept, lists counted."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            elif isinstance(v, list):
                out[k] = (v if len(v) <= 8 and all(isinstance(x, (str, int, float)) for x in v)
                          else f"{len(v)} items")
            elif isinstance(v, dict) and depth < 1:
                out[k] = _brief(v, depth + 1)
            elif isinstance(v, dict):
                out[k] = f"{len(v)} entries"
        return out
    return obj


# ── tool table ──────────────────────────────────────────────────────────────

def _obj(props: Optional[dict] = None, required: Optional[list] = None) -> dict:
    d: dict = {"type": "object", "properties": props or {}}
    if required:
        d["required"] = required
    return d


_S = {"type": "string"}
_IDS = {"type": "array", "items": {"type": "string"}}

TOOLS: List[dict] = [
    {"name": "list_shows", "handler": "t_list_shows",
     "description": "List the .qxw shows in the folders shared with Claude (newest first).",
     "inputSchema": _obj()},
    {"name": "open_show", "handler": "t_open_show",
     "description": "Open a .qxw show to work on. Starts a fresh History; the file itself is never changed.",
     "inputSchema": _obj({"path": _S}, ["path"])},
    {"name": "show_summary", "handler": "t_show_summary",
     "description": "What is open now: name, how many steps and unsaved changes, Doctor counts, and a short overview of the show.",
     "inputSchema": _obj()},
    {"name": "doctor_check", "handler": "t_doctor_check",
     "description": "Run the Doctor on the show in progress and list the findings (key, code, severity, location, message, fixable, hint).",
     "inputSchema": _obj()},
    {"name": "doctor_fix", "handler": "t_doctor_fix",
     "description": "Fix Doctor findings. Without `keys`, fixes every finding the Doctor ticks by default. `options` are the Doctor's fix options.",
     "inputSchema": _obj({"keys": _IDS, "options": {"type": "object"}})},
    {"name": "rig_fixtures", "handler": "t_rig_fixtures",
     "description": "List the fixtures of the show in progress (ids, names, universe, address) — use before reduce_rig.",
     "inputSchema": _obj()},
    {"name": "reduce_rig", "handler": "t_reduce_rig",
     "description": "Shrink the rig to the fixtures in `keep` (ids), dropping what only they-not-kept used. `repatch` maps id → {name, universe, address}. With preview=true nothing changes.",
     "inputSchema": _obj({"keep": _IDS, "repatch": {"type": "object"}, "preview": {"type": "boolean"}}, ["keep"])},
    {"name": "source_functions", "handler": "t_source_functions",
     "description": "Open another show as the source for porting and list its functions (id, name, type, path). Filter with `query` (name contains) and `type` (Scene, Chaser, …).",
     "inputSchema": _obj({"source_path": _S, "query": _S, "type": _S}, ["source_path"])},
    {"name": "port_functions", "handler": "t_port_functions",
     "description": "Port functions (and what they need) from another show into the show in progress. `strategy` maps the source fixtures onto yours: fan_in (default), same_id or all. `options` are extra Porter plan fields (name_prefix, vc, drop_unmapped, …). With preview=true only validates.",
     "inputSchema": _obj({"source_path": _S, "function_ids": _IDS,
                          "strategy": {"type": "string", "enum": ["fan_in", "same_id", "all"]},
                          "options": {"type": "object"}, "preview": {"type": "boolean"}},
                         ["source_path", "function_ids"])},
    {"name": "looks_options", "handler": "t_looks_options",
     "description": "What the Looks & Chasers builder offers for this show: fixture groups, palettes, patterns, notes, positions.",
     "inputSchema": _obj()},
    {"name": "build_looks", "handler": "t_build_looks",
     "description": "Build looks (scenes) and chasers, with their Virtual Console buttons. Body as in the Looks tool: looks [{group, colours, level, position}], chasers [{group, pattern, colours, bpm, note, fade, fade_pct, name}], matrices, folder, vc_page, nomenclature. With check_only=true only checks.",
     "inputSchema": _obj({"looks": {"type": "array"}, "chasers": {"type": "array"}, "matrices": {"type": "array"},
                          "folder": _S, "vc_page": _S, "nomenclature": _S, "check_only": {"type": "boolean"}})},
    {"name": "vc_pages", "handler": "t_vc_pages",
     "description": "List the Virtual Console pages and their widgets.",
     "inputSchema": _obj()},
    {"name": "edit_vc", "handler": "t_edit_vc",
     "description": "One Virtual Console edit. `op` is one of: copy, move, new_page, fix_ids, copy_page, create, delete, duplicate, wire, rename_page, move_page, delete_page, label_panel, auto_arrange, screen, apply_template, setlist_cuelist; the other fields are that op's arguments (the same as the VC tool).",
     "inputSchema": {"type": "object", "properties": {"op": _S}, "required": ["op"],
                     "additionalProperties": True}},
    {"name": "setlist", "handler": "t_setlist",
     "description": "Turn a setlist into a chaser. Give `songs` (titles, in order) or `text` (pasted list). Songs are matched to the show's functions; `rows` may override with {txt_name, qxw_id, in, hold, out}. With apply=false only shows the matches.",
     "inputSchema": _obj({"songs": _IDS, "text": _S, "slot": _S, "rows": {"type": "array"},
                          "apply": {"type": "boolean"}, "target_chaser_id": _S})},
    {"name": "compare", "handler": "t_compare",
     "description": "Compare the show in progress with another .qxw and return the differences (read only).",
     "inputSchema": _obj({"path": _S}, ["path"])},
    {"name": "dictionary_context", "handler": "t_dictionary_context",
     "description": "For writing the Dictionary (ID → description of each function): lists the functions of the show in progress with id, name, type, current description, the Virtual Console button caption/frames that trigger it and short facts (chaser steps, scene fixture count, collection members). Also gives `used_by` (the chasers, collections and scripts that start it) and, for scripts, what they start and stop. Use only_missing=true for the undescribed ones and skip_steps=true to hide helper steps (they are named by dictionary_set auto_steps). Read-only. To DRAFT descriptions: call this, write ONE short plain sentence per function (what it looks like or when it is used — only from the facts and names given; say \"unclear\" rather than guess; mention the button only when it adds something, not on every line), show the proposal to the user as a compact table, and call dictionary_set once they agree (or straight away if they asked you to just do it).",
     "inputSchema": _obj({"only_missing": {"type": "boolean"}, "skip_steps": {"type": "boolean"}, "type": _S, "query": _S, "frame": _S,
                          "limit": {"type": "integer"}, "offset": {"type": "integer"}})},
    {"name": "dictionary_set", "handler": "t_dictionary_set",
     "description": "Store descriptions in the Dictionary: entries [{id, description}]. An existing description is kept unless overwrite=true. auto_steps=true also describes the helper steps (functions that are only steps of a chaser or collection and have no button) as \"Step n of …\" / \"Part of …\". Nothing is written to a file until dictionary_save; the show itself is never changed.",
     "inputSchema": _obj({"entries": {"type": "array", "items": _obj({"id": _S, "description": _S}, ["id", "description"])},
                          "overwrite": {"type": "boolean"}, "auto_steps": {"type": "boolean"}}, ["entries"])},
    {"name": "dictionary_load", "handler": "t_dictionary_load",
     "description": "Load an existing dictionary .txt (ID|Name|Description) from a shared folder, to extend it.",
     "inputSchema": _obj({"path": _S}, ["path"])},
    {"name": "dictionary_save", "handler": "t_dictionary_save",
     "description": "Write the Dictionary as a NEW .txt in a shared folder (never overwrites: _v2, _v3…). `where` is a folder or a .txt path; default: next to the opened show.",
     "inputSchema": _obj({"where": _S})},
    {"name": "show_history", "handler": "t_show_history",
     "description": "The steps made so far on the show in progress (what each did, Doctor counts after it).",
     "inputSchema": _obj()},
    {"name": "undo", "handler": "t_undo",
     "description": "Go back to before step n (default: undo the last step).",
     "inputSchema": _obj({"n": {"type": "integer"}})},
    {"name": "redo", "handler": "t_redo",
     "description": "Redo what was undone.", "inputSchema": _obj()},
    {"name": "save_show", "handler": "t_save_show",
     "description": "Save the show in progress as a NEW .qxw (+ report + recipe) in a shared folder. Never overwrites: a taken name becomes _v2, _v3… `where` is a folder or a .qxw path; default: next to the opened file.",
     "inputSchema": _obj({"where": _S})},
]

# MCP tool annotations: they let the client group the tools ("reads" vs "changes") and
# ask once per group instead of once per tool.  None of the tools deletes or overwrites a file.
READ_ONLY = {"list_shows", "show_summary", "doctor_check", "rig_fixtures", "source_functions",
             "looks_options", "vc_pages", "compare", "dictionary_context", "show_history"}
TITLES = {
    "list_shows": "List shows", "open_show": "Open a show", "show_summary": "Show summary",
    "doctor_check": "Doctor: check", "doctor_fix": "Doctor: fix", "rig_fixtures": "List fixtures",
    "reduce_rig": "Reduce the rig", "source_functions": "Porter: source functions",
    "port_functions": "Porter: port functions", "looks_options": "Looks: options",
    "build_looks": "Build looks and chasers", "vc_pages": "Virtual Console pages",
    "edit_vc": "Edit the Virtual Console", "setlist": "Setlist to chaser", "compare": "Compare shows",
    "dictionary_context": "Dictionary: read functions", "dictionary_set": "Dictionary: set descriptions",
    "dictionary_load": "Dictionary: load", "dictionary_save": "Dictionary: save as new file",
    "show_history": "History", "undo": "Undo", "redo": "Redo", "save_show": "Save as a new file",
}


def _annotations(name: str) -> dict:
    ro = name in READ_ONLY
    a = {"title": TITLES.get(name, name), "readOnlyHint": ro, "openWorldHint": False}
    if not ro:
        a["destructiveHint"] = False          # works on the show in progress or writes a NEW file
    return a


INSTRUCTIONS = (
    "QLC+ Swiss Knife edits QLC+ show files (.qxw). Open a show with open_show, "
    "look at it (show_summary, doctor_check), change it with the tools, and finish "
    "with save_show, which writes a NEW file — the original is never modified. "
    "Every change is a History step you can show_history or undo. "
    "The show is open only in this server's own session, not in the Swiss Knife window: tell the user to open the saved file in the app. "
    "To describe functions in the Dictionary, use dictionary_context, propose the descriptions to the user, "
    "then dictionary_set and dictionary_save (the Dictionary is a separate .txt, not part of the show). "
    "Only folders the user shared in Swiss Knife (Settings › Connect to Claude) are reachable."
)


class Server:
    def __init__(self, allow: Optional[mcp_config.Allowlist] = None):
        self.allow = allow or mcp_config.Allowlist()
        self._client = None
        self.opened_path = ""

    # ── plumbing ────────────────────────────────────────────────────────────
    @property
    def client(self):
        if self._client is None:
            try:
                import app as _app
            except ModuleNotFoundError as e:
                raise ToolError(f"Swiss Knife's Python is missing a package ({e.name}). Install the "
                                f"requirements (pip install flask) for {sys.executable}.")
            self._client = _app.create_app().test_client()
        return self._client

    def api(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        fn = getattr(self.client, method.lower())
        r = fn(path, json=body) if method.upper() != "GET" else fn(path)
        try:
            data = r.get_json(silent=True)
        except Exception:  # noqa: BLE001
            data = None
        if r.status_code >= 400:
            msg = (data or {}).get("error") if isinstance(data, dict) else None
            extra = ""
            if isinstance(data, dict) and data.get("findings"):
                extra = " Findings: " + json.dumps(data["findings"], ensure_ascii=False)[:1500]
            raise ToolError((msg or f"{path} failed ({r.status_code})") + extra)
        return data

    def need_show(self) -> None:
        st = self.api("GET", "/api/show/status?doctor=0")
        if not st.get("active"):
            raise ToolError("No show is open. Call open_show first.")

    def _written(self, data: dict, what: str) -> dict:
        """The answer of a tool that changed the show: its step and the Doctor's counts."""
        from routes.show_routes import doctor_counts
        hist = self.api("GET", "/api/show/history")
        steps = hist.get("steps") or []
        out: Dict[str, Any] = {"done": what, "doctor": doctor_counts()}
        if steps:
            out["step"] = steps[-1]
        out["unsaved_steps"] = (hist.get("show") or {}).get("unsaved")
        out["note"] = "Not saved yet — call save_show to write a new file."
        return out

    # ── tools ───────────────────────────────────────────────────────────────
    def t_list_shows(self, a: dict) -> Any:
        problems: list = []
        shows = self.allow.list_shows(problems=problems)
        if not self.allow.folders():
            return {"folders": [], "shows": [],
                    "hint": "No folder is shared yet: Swiss Knife › Settings › Connect to Claude."}
        out: dict = {"folders": self.allow.folders(), "shows": shows}
        if problems:
            out["problems"] = problems[:10]
            out["hint"] = ("Some folders could not be read, so the list may be incomplete. On a Mac, allow "
                           "Claude and Swiss Knife to read the folder under System Settings › Privacy & Security › Files and Folders.")
        return out

    def t_open_show(self, a: dict) -> Any:
        p = self.allow.check(a.get("path", ""))
        if not p.lower().endswith(".qxw"):
            raise ToolError("Open a .qxw file.")
        self.api("POST", "/api/load", {"path": p})
        self.opened_path = p
        return self.t_show_summary({})

    def t_show_summary(self, a: dict) -> Any:
        st = self.api("GET", "/api/show/status")
        if not st.get("active"):
            return {"open": False, "hint": "Call open_show."}
        ws = self.api("GET", "/api/status")
        return {"open": True, "show": st, "overview": _brief(ws)}

    def t_doctor_check(self, a: dict) -> Any:
        self.need_show()
        d = self.api("GET", "/api/doctor/check")
        f = d.get("findings") or []
        keep = ("key", "code", "severity", "location", "message", "fixable", "default")
        order = {"error": 0, "warning": 1}
        f = sorted(f, key=lambda x: order.get(x.get("severity"), 2))
        slim = [{k: x.get(k) for k in keep if k in x} for x in f]
        for x in slim:
            if len(x.get("message", "")) > 160:
                x["message"] = x["message"][:160] + "…"
        by: Dict[str, int] = {}
        for x in f:
            by[x.get("code", "?")] = by.get(x.get("code", "?"), 0) + 1
        out: Dict[str, Any] = {"total": len(f), "by_code": by, "findings": slim[:30]}
        if len(f) > 30:
            out["note"] = f"Showing the first 30 of {len(f)}; doctor_fix fixes the default-ticked ones."
        return out

    def t_doctor_fix(self, a: dict) -> Any:
        self.need_show()
        keys = a.get("keys")
        if not keys:
            d = self.api("GET", "/api/doctor/check")
            keys = [f["key"] for f in d.get("findings", []) if f.get("default") and f.get("fixable", True)]
            if not keys:
                return {"done": "Nothing to fix by default.", "doctor": self._counts()}
        body = {"keys": [str(k) for k in keys]}
        if a.get("options"):
            body["options"] = a["options"]
        r = self.api("POST", "/api/doctor/apply", body)
        return self._written(r, f"Doctor fixed {len(keys)} finding(s)")

    def _counts(self) -> dict:
        from routes.show_routes import doctor_counts
        return doctor_counts()

    def t_rig_fixtures(self, a: dict) -> Any:
        self.need_show()
        return self.api("GET", "/api/reducer/fixtures")

    def t_reduce_rig(self, a: dict) -> Any:
        self.need_show()
        body = {"keep": [str(k) for k in a.get("keep") or []], "repatch": a.get("repatch") or {}}
        if a.get("preview"):
            return self.api("POST", "/api/reducer/preview", body)
        r = self.api("POST", "/api/reducer/apply", body)
        return self._written(r, "Rig reduced")

    def t_source_functions(self, a: dict) -> Any:
        self.need_show()
        p = self.allow.check(a.get("source_path", ""))
        self.api("POST", "/api/porter/source/load", {"path": p})
        fns = self.api("GET", "/api/porter/source/functions")
        q = str(a.get("query") or "").lower()
        typ = str(a.get("type") or "").lower()
        rows = [{k: f.get(k) for k in ("id", "name", "type", "path") if f.get(k) not in (None, "")}
                for f in fns
                if (not q or q in str(f.get("name", "")).lower())
                and (not typ or typ == str(f.get("type", "")).lower())]
        out: Dict[str, Any] = {"count": len(fns), "matching": len(rows), "functions": rows[:120]}
        if len(rows) > 120:
            out["note"] = "Showing 120; narrow with `query` (name contains) or `type` (Scene, Chaser…)."
        return out

    def t_port_functions(self, a: dict) -> Any:
        self.need_show()
        p = self.allow.check(a.get("source_path", ""))
        ids = [str(i) for i in a.get("function_ids") or []]
        if not ids:
            raise ToolError("function_ids is empty. Use source_functions to see the ids.")
        opts = dict(a.get("options") or {})
        for q in (opts.get("qxf_paths") or []):
            self.allow.check(q)
        if opts.get("import_path"):
            self.allow.check(opts["import_path"])
        strategy = a.get("strategy") or "fan_in"
        self.api("POST", "/api/porter/source/load", {"path": p})
        self.api("POST", "/api/porter/target/show", {})
        cl = self.api("POST", "/api/porter/resolve", {"seed_ids": ids})
        mapping = (self.api("POST", "/api/porter/auto-map",
                            {"fixture_ids": cl.get("fixture_ids") or [], "strategy": strategy})
                   if cl.get("fixture_ids") else {})
        plan = {"closure": cl, "fixture_mapping": mapping, "drop_unmapped": True}
        if strategy == "fan_in":
            plan["fanout_mode"] = "fan_in"
        plan.update(opts)
        if a.get("preview"):
            return self.api("POST", "/api/porter/validate", plan)
        r = self.api("POST", "/api/porter/apply", plan)
        return self._written(r, f"Ported {len(ids)} function(s) with what they need")

    def t_looks_options(self, a: dict) -> Any:
        self.need_show()
        return self.api("GET", "/api/looks/options")

    def t_build_looks(self, a: dict) -> Any:
        self.need_show()
        body = {k: v for k, v in a.items() if k != "check_only"}
        if a.get("check_only"):
            return self.api("POST", "/api/looks/check", body)
        r = self.api("POST", "/api/looks/apply", body)
        return self._written(r, "Looks and chasers built")

    def t_vc_pages(self, a: dict) -> Any:
        self.need_show()
        return self.api("GET", "/api/vc/pages")

    def t_edit_vc(self, a: dict) -> Any:
        self.need_show()
        r = self.api("POST", "/api/vc/op", dict(a))
        w = self._written(r, f"Virtual Console: {a.get('op')}")
        if isinstance(r, dict):
            w["result"] = _brief({k: v for k, v in r.items() if k not in ("show", "step")})
        return w

    def t_setlist(self, a: dict) -> Any:
        self.need_show()
        songs = [str(s) for s in a.get("songs") or []]
        if not songs and a.get("text"):
            songs = [s["txt_name"] for s in self.api("POST", "/api/setlist/parse", {"text": a["text"]})["songs"]]
        slots = self.api("GET", "/api/setlist/slots")
        slot = a.get("slot") or ((slots[0].get("id") or slots[0].get("slot_id")) if slots else "")
        if not slot:
            raise ToolError("The show has no setlist cuelist slot to fill.")
        matches = self.api("POST", "/api/setlist/auto-match", {"songs": songs})
        rows = a.get("rows")
        if not rows:
            rows = [{"txt_name": m["txt_name"], "qxw_id": m.get("matched_id") or "",
                     "qxw_name": m.get("matched_name") or "", "in": 0, "hold": 0, "out": 0}
                    for m in matches]
        if a.get("apply") is False:
            return {"slot": slot, "matches": matches}
        self.api("POST", f"/api/setlist/{slot}/songs", {"songs": songs})
        self.api("POST", f"/api/setlist/{slot}/details", {"rows": rows})
        body = {"target_chaser_id": a["target_chaser_id"]} if a.get("target_chaser_id") else {}
        r = self.api("POST", f"/api/setlist/{slot}/apply", body)
        w = self._written(r, f"Setlist of {len(rows)} song(s) built")
        w["left_out"] = (r or {}).get("skipped") or []
        return w

    def t_compare(self, a: dict) -> Any:
        self.need_show()
        p = self.allow.check(a.get("path", ""))
        r = self.api("POST", "/api/compare/run", {"path": p})
        rep = r.get("report") or ""
        out = {"a": r.get("a"), "b": r.get("b"), "report": rep[:9000]}
        if len(rep) > 9000:
            out["note"] = f"Report cut at 9000 of {len(rep)} characters."
        return out

    # ── dictionary (descriptions; never part of the .qxw) ───────────────────
    def _facts(self) -> Dict[str, dict]:
        """{function id: {facts, used_by, helper, auto}} read from the show in progress."""
        import copy
        from core import qxw_io, script_cmds, workspace
        root = workspace._state.get("qxw_root")
        if root is None:
            return {}
        root = qxw_io.strip_ns(copy.deepcopy(root))
        names = workspace._state.get("func_by_id", {})
        eng = root.find("Engine")                      # not the <Function ID=…/> references of VC buttons
        funcs = [(f.get("ID", ""), f.get("Type", ""), f)
                 for f in (eng.findall("Function") if eng is not None else [])]
        types = {fid: typ for fid, typ, _f in funcs}
        parents: Dict[str, list] = {}                 # child id → [(parent id, type, step number)]
        out: Dict[str, dict] = {}
        for fid, typ, f in funcs:
            info: Dict[str, Any] = {}
            if typ in ("Chaser", "Collection", "Sequence"):
                kids = [(st.text or "").strip() for st in f.iter("Step")]
                kids = [k for k in kids if k.isdigit()]
                for n, k in enumerate(kids, 1):
                    parents.setdefault(k, []).append((fid, typ, n))
                if kids:
                    info["facts"] = (f"{len(kids)} step(s): " + ", ".join(names.get(k, "?") for k in kids[:6])
                                     + ("…" if len(kids) > 6 else ""))
            elif typ == "Scene":
                vals = []
                for fv in f.iter("FixtureVal"):
                    p_ = (fv.text or "").split(",")
                    vals += [int(x) for x in p_[1::2] if x.strip().lstrip("-").isdigit()]
                n = len(list(f.iter("FixtureVal")))
                if not n:
                    info["facts"] = "no fixture values"
                else:
                    up = sum(1 for v in vals if v > 0)
                    info["facts"] = (f"{n} fixture(s); " + ("all values 0 (blackout/neutral)" if not up
                                                           else f"{up} of {len(vals)} channel values above 0"))
            elif typ == "EFX":
                al = f.find("Algorithm")
                info["facts"] = f"EFX {al.text}" if al is not None and al.text else "EFX"
            elif typ == "RGBMatrix":
                al = f.find("Algorithm")
                sp = f.find("Speed")
                bits = [f"pattern '{al.text}'" if al is not None and al.text else "matrix"]
                if sp is not None and sp.get("Duration"):
                    bits.append(f"{sp.get('Duration')} ms per step")
                info["facts"] = ", ".join(bits)
            elif typ == "Script":
                starts, stops = [], []
                for c in f.iter("Command"):
                    for verb, ref in script_cmds.func_refs(c.text):
                        (starts if verb == "start" else stops).append(ref)
                bits = []
                if starts:
                    bits.append("starts " + ", ".join(names.get(r, "?") for r in dict.fromkeys(starts)))
                if stops:
                    bits.append(f"stops {len(set(stops))} function(s)")
                info["facts"] = "script: " + ("; ".join(bits) if bits else "no start/stop commands")
                for r in dict.fromkeys(starts):
                    parents.setdefault(r, []).append((fid, typ, 0))
            out[fid] = info
        for kid, plist in parents.items():
            if kid not in out:
                continue
            out[kid]["used_by"] = [f"{names.get(pid, '?')} ({pt})" for pid, pt, _n in plist][:4]
            only_steps = all(pt in ("Chaser", "Collection", "Sequence") for _pid, pt, _n in plist)
            out[kid]["_only_steps"] = only_steps
            pid, pt, n = plist[0]
            out[kid]["_auto"] = (f"Step {n} of {names.get(pid, '?')}" if pt == "Chaser" and n
                                 else f"Part of {names.get(pid, '?')}" if pt in ("Collection", "Sequence")
                                 else "")
        return out

    def t_dictionary_context(self, a: dict) -> Any:
        self.need_show()
        rows = self.api("GET", "/api/dictionary/")
        facts = self._facts()
        q = str(a.get("query") or "").lower()
        typ = str(a.get("type") or "").lower()
        frame = str(a.get("frame") or "").lower()
        out, hidden = [], 0
        for r in rows:
            fx = facts.get(r["id"], {})
            if a.get("only_missing") and (r.get("desc") or "").strip():
                continue
            if typ and typ != str(r.get("type", "")).lower():
                continue
            if q and q not in str(r.get("name", "")).lower():
                continue
            if frame and not any(frame in str(x).lower() for x in r.get("vc_frames") or []):
                continue
            if a.get("skip_steps") and fx.get("_only_steps") and not r.get("vc_button"):
                hidden += 1                         # a helper: dictionary_set(auto_steps=true) names it
                continue
            row = {"id": r["id"], "name": r["name"], "type": r["type"]}
            if r.get("desc"):
                row["description"] = r["desc"]
            if r.get("vc_button"):
                row["vc_button"] = r["vc_button"]
            if r.get("vc_frames"):
                row["vc_frames"] = r["vc_frames"]
            if fx.get("facts"):
                row["facts"] = fx["facts"]
            if fx.get("used_by"):
                row["used_by"] = fx["used_by"]
            out.append(row)
        limit = max(1, min(int(a.get("limit") or 60), 150))
        off = max(0, int(a.get("offset") or 0))
        res: Dict[str, Any] = {"total": len(rows), "matching": len(out),
                               "described": sum(1 for r in rows if (r.get("desc") or "").strip()),
                               "functions": out[off:off + limit]}
        if hidden:
            res["helper_steps_hidden"] = hidden
            res["note"] = ("Helper steps (functions that only exist as steps of a chaser or collection, with no "
                           "button) are hidden; dictionary_set(auto_steps=true) describes them as \"Step n of …\".")
        if len(out) > off + limit:
            res["next_offset"] = off + limit
        return res

    def t_dictionary_set(self, a: dict) -> Any:
        self.need_show()
        known = {r["id"]: r for r in self.api("GET", "/api/dictionary/")}
        entries = [dict(e) for e in a.get("entries") or []]
        auto = 0
        if a.get("auto_steps"):
            given = {str(e.get("id", "")).strip() for e in entries}
            for fid, fx in self._facts().items():
                if (fid in known and fid not in given and fx.get("_only_steps") and fx.get("_auto")
                        and not known[fid].get("vc_button")):
                    entries.append({"id": fid, "description": fx["_auto"]})
                    auto += 1
        done, kept, unknown = [], [], []
        for e in entries:
            fid = str(e.get("id", "")).strip()
            desc = " ".join(str(e.get("description", "")).split())[:400]
            if fid not in known:
                unknown.append(fid)
            elif not desc:
                continue
            elif (known[fid].get("desc") or "").strip() and not a.get("overwrite"):
                kept.append(fid)
            else:
                self.api("PATCH", f"/api/dictionary/{fid}", {"desc": desc})
                done.append(fid)
        out: Dict[str, Any] = {"set": len(done), "kept_existing": kept, "unknown_ids": unknown,
                               "note": "Held in memory — call dictionary_save to write the .txt."}
        if auto:
            out["auto_steps_named"] = auto
        return out

    def t_dictionary_load(self, a: dict) -> Any:
        self.need_show()
        p = self.allow.check(a.get("path", ""))
        if not p.lower().endswith(".txt"):
            raise ToolError("A dictionary is a .txt file.")
        return self.api("POST", "/api/dictionary/load", {"path": p})

    def t_dictionary_save(self, a: dict) -> Any:
        self.need_show()
        st = self.api("GET", "/api/show/status?doctor=0")
        where = a.get("where") or (os.path.dirname(self.opened_path) if self.opened_path else "")
        if not where:
            raise ToolError("Say where to save: a shared folder or a .txt path.")
        stem = os.path.splitext(st.get("source_name") or "Show.qxw")[0]
        try:
            path = self.allow.new_file_path(where, f"{stem}_dictionary.txt", ext=".txt")
        except mcp_config.NotAllowed as e:
            raise ToolError(str(e))
        self.api("POST", "/api/dictionary/save", {"path": path})
        return {"saved": path, "note": "A new file; the show and any earlier dictionary are untouched."}

    def t_show_history(self, a: dict) -> Any:
        self.need_show()
        return self.api("GET", "/api/show/history")

    def t_undo(self, a: dict) -> Any:
        self.need_show()
        body = {"n": int(a["n"])} if a.get("n") else {}
        self.api("POST", "/api/show/undo", body)
        return {"done": "Undone", "show": self.api("GET", "/api/show/status")}

    def t_redo(self, a: dict) -> Any:
        self.need_show()
        self.api("POST", "/api/show/redo", {})
        return {"done": "Redone", "show": self.api("GET", "/api/show/status")}

    def t_save_show(self, a: dict) -> Any:
        self.need_show()
        st = self.api("GET", "/api/show/status?doctor=0")
        where = a.get("where") or (os.path.dirname(self.opened_path) if self.opened_path else "")
        if not where:
            raise ToolError("Say where to save: a shared folder or a .qxw path.")
        name = st.get("suggested_name") or "Show.qxw"
        try:
            path = self.allow.new_file_path(where, name)
        except mcp_config.NotAllowed as e:
            raise ToolError(str(e))
        if os.path.abspath(path) == os.path.abspath(self.opened_path or "?"):
            raise ToolError("That would overwrite the opened show; pick another name.")
        r = self.api("POST", "/api/show/save", {"path": path})
        no_change = not st.get("steps")
        return {"saved": r.get("path") or path, "no_changes": no_change, "report": r.get("report_path"),
                "recipe": r.get("recipe_path"), "doctor": self._counts(),
                "note": ("No changes were made, so this is an identical copy. " if no_change else "")
                        + "The original file was not changed. The recipe replays this to the same file: "
                        "python -m core.recipe replay <recipe>"}

    # ── protocol ────────────────────────────────────────────────────────────
    def call_tool(self, name: str, args: dict) -> dict:
        spec = next((t for t in TOOLS if t["name"] == name), None)
        if spec is None:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        try:
            res = getattr(self, spec["handler"])(args or {})
            return {"content": [{"type": "text", "text": _text(res)}]}
        except (ToolError, mcp_config.NotAllowed) as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except Exception as e:  # noqa: BLE001 — never let a tool kill the server
            print(traceback.format_exc(), file=sys.stderr)
            return {"content": [{"type": "text",
                                 "text": f"Swiss Knife could not do that: {type(e).__name__}: {e}"}],
                    "isError": True}

    def handle(self, msg: dict) -> Optional[dict]:
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if mid is None:                                  # notification: no answer
            return None

        def ok(result):
            return {"jsonrpc": "2.0", "id": mid, "result": result}

        def err(code, text):
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": text}}

        if method == "initialize":
            want = params.get("protocolVersion")
            return ok({"protocolVersion": want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                       "capabilities": {"tools": {"listChanged": False}},
                       "serverInfo": {"name": "qlc-swiss-knife", "version": _version()},
                       "instructions": INSTRUCTIONS})
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": [dict({k: t[k] for k in ("name", "description", "inputSchema")},
                                      title=TITLES.get(t["name"], t["name"]),
                                      annotations=_annotations(t["name"])) for t in TOOLS]})
        if method == "tools/call":
            return ok(self.call_tool(params.get("name", ""), params.get("arguments") or {}))
        if method in ("resources/list", "resources/templates/list"):
            return ok({"resources": []} if method == "resources/list" else {"resourceTemplates": []})
        if method == "prompts/list":
            return ok({"prompts": []})
        return err(-32601, f"Method not found: {method}")


def serve(inp, out, server: Optional[Server] = None) -> None:
    """Read one JSON message per line from *inp*, answer on *out*."""
    srv = server or Server()
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp: Optional[dict] = {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700, "message": "Parse error"}}
        else:
            if isinstance(msg, list):                     # batches are not used by MCP clients
                resp = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": "Batches are not supported"}}
            else:
                resp = srv.handle(msg)
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=True) + "\n")
            out.flush()


def selftest() -> int:
    """Talk to ourselves over the same loop the real client uses."""
    import tempfile
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSIONS[0], "capabilities": {},
                    "clientInfo": {"name": "selftest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "list_shows", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "show_summary", "arguments": {}}},
    ]
    bad = []
    with tempfile.TemporaryDirectory() as td:
        srv = Server(mcp_config.Allowlist([td]))
        out = io.StringIO()
        serve(io.StringIO("\n".join(json.dumps(r) for r in reqs) + "\n"), out, srv)
        got = {}
        for ln in out.getvalue().splitlines():
            m = json.loads(ln)
            got[m["id"]] = m
        if got.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") != "qlc-swiss-knife":
            bad.append("initialize")
        if len(got.get(2, {}).get("result", {}).get("tools", [])) != len(TOOLS):
            bad.append("tools/list")
        if got.get(3, {}).get("result", {}).get("isError"):
            bad.append("list_shows")
        if '"open":' not in got.get(4, {}).get("result", {}).get("content", [{}])[0].get("text", ""):
            bad.append("show_summary")
    for b in bad:
        print("SELFTEST FAIL:", b, file=sys.stderr)
    print(f"MCP SELFTEST {'OK' if not bad else 'FAILED'} — v{_version()}, {len(TOOLS)} tools")
    return 1 if bad else 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="qlc-swiss-knife --mcp",
                                 description="QLC+ Swiss Knife as an MCP server (stdio)")
    ap.add_argument("--folder", action="append", default=[], help="share this folder for this run")
    ap.add_argument("--selftest", action="store_true", help="check the protocol loop and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    real_out = sys.stdout
    try:
        stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", newline="\n")
        stdout = io.TextIOWrapper(real_out.buffer, encoding="utf-8", newline="\n", write_through=True)
    except AttributeError:                                  # not a real console (tests)
        stdin, stdout = sys.stdin, real_out
    sys.stdout = sys.stderr                                 # stdout is the protocol, nothing else
    print(f"[qsk-mcp] v{_version()} started, pid {os.getpid()}, python {sys.executable}, "
          f"folders {args.folder}", file=sys.stderr, flush=True)
    try:
        serve(stdin, stdout, Server(mcp_config.Allowlist(args.folder)))
    except BaseException:                                   # noqa: BLE001 — say why before dying
        print("[qsk-mcp] crashed:\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return 1
    print("[qsk-mcp] input closed, exiting", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
