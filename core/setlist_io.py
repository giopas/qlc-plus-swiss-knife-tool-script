"""
core/setlist_io.py — setlist import and the tablet page (v2.6.0)
================================================================
* :func:`parse` reads a setlist from whatever people have: a pasted list
  (numbered or not), a .txt, a .csv / .tsv exported from a spreadsheet, with
  optional set breaks (``--- Set 2 ---``, ``Encore``) and optional timing
  columns.  It returns the sets and the notes about what it did.
* :func:`tablet_page` renders the setlists as ONE self-contained HTML file
  for a tablet on stage: big type, tap a song to tick it off, set tabs, a
  text-size control, dark and high-contrast.  No network, no server.
"""

from __future__ import annotations

import csv
import html
import io
import re
from typing import Dict, List, Optional

HOLD_INFINITE = "4294967294"                 # QLC+'s "wait for Go" sentinel

_NUM = re.compile(r"^\s*(?:\(?\d{1,3}\)|\d{1,3}\s*[.):\-–—]|0\d\s+(?=\D)|[-*•·▪►>]+)\s*")
_SET = re.compile(r"^\s*[\[\(\-=#*~ ]*\s*((?:set|part|act)\s*(?:\d+|[ivx]+|one|two|three)?|encore|bis|bonus|"
                  r"soundcheck|intro|intermission|pause|break)\b[^\w]*(.*?)[\]\)\-=#*~ ]*\s*$", re.I)
_TIME = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")
_HEAD = {
    "name": ("song", "title", "name", "track", "songs", "titre", "titolo", "canzone", "brano", "morceau"),
    "set": ("set", "slot", "part", "section", "act"),
    "in": ("fade in", "fadein", "in", "fade_in"),
    "hold": ("hold", "duration", "length", "time", "durata", "durée", "dur"),
    "out": ("fade out", "fadeout", "out", "fade_out"),
}


def _ms(v: str, default: str = "0") -> str:
    """'3:45' / '225' / '2.5' / '2,5s' → milliseconds as a string."""
    v = (v or "").strip().lower().replace(",", ".").rstrip("s").strip()
    if not v:
        return default
    m = _TIME.match(v)
    if m:
        h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
        return str((h * 3600 + mi * 60 + s) * 1000)
    try:
        return str(int(round(float(v) * 1000)))
    except ValueError:
        return default


def _clean(line: str) -> str:
    line = line.replace("﻿", "").strip()
    line = _NUM.sub("", line, count=1) if _NUM.match(line) and not re.match(r"^\d{1,3}\s*$", line) else line
    return re.sub(r"\s+", " ", line).strip(" \t\"'")


def _sniff(text: str) -> Optional[str]:
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")][:20]
    if len(lines) < 1:
        return None
    for d in ("\t", ";", ","):
        counts = [l.count(d) for l in lines]
        if min(counts) >= 1 and len(set(counts)) <= 2 and (max(counts) <= 6):
            return d
    return None


def _set_break(line: str) -> Optional[str]:
    """The name of a set break (``--- Set 2 ---``), else None.  Only short
    lines that are *mostly* the keyword count: 'Set Fire to the Rain' is a song."""
    s = line.strip()
    m = _SET.match(s)
    if not m:
        return None
    kw, rest = m.group(1).strip(), m.group(2).strip()
    deco = bool(re.match(r"^[\[\(\-=#*~]", s))
    if rest and not deco:
        return None
    if re.match(r"^(set|part|act)$", kw, re.I) and not deco and not rest:
        return None
    name = (kw + (" " + rest if rest else "")).strip()
    return name[:1].upper() + name[1:]


def parse(text: str, name_hint: str = "") -> dict:
    """``{sets: [{name, songs: [{txt_name, in, hold, out}]}], songs: n, notes: [..], format}``."""
    text = (text or "").replace("﻿", "")
    notes: List[str] = []
    sets: List[Dict] = []

    def cur(nm: str = "") -> Dict:
        if nm:
            hit = next((s for s in sets if s["name"] == nm), None)
            if hit:
                return hit
            sets.append({"name": nm, "songs": []})
            return sets[-1]
        if not sets:
            sets.append({"name": name_hint or "Setlist", "songs": []})
        return sets[-1]

    delim = _sniff(text)
    if delim:
        first = next((l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")), "")
        heads = [c.strip().lower() for c in first.split(delim)]
        known = any(h in names for h in heads for names in _HEAD.values())
        # a comma in a song title ("Hello, Goodbye") must not turn a list into a table
        if not (known or delim == "\t" or name_hint.lower().endswith((".csv", ".tsv"))):
            delim = None
    fmt = "list"
    if delim:
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)
                if r and any(c.strip() for c in r) and not r[0].lstrip().startswith("#")]
        head = [c.strip().lower() for c in rows[0]] if rows else []
        idx = {k: next((i for i, h in enumerate(head) if h in names), None) for k, names in _HEAD.items()}
        has_head = idx["name"] is not None
        if has_head:
            rows = rows[1:]
            fmt = "table"
        else:                                   # no header: the first column is the song, unless numbers
            first_num = all(re.fullmatch(r"\s*\d{1,3}\s*", r[0]) for r in rows if r)
            idx = {"name": 1 if first_num and len(rows[0]) > 1 else 0, "set": None, "in": None, "hold": None, "out": None}
            fmt = "table (no header)"
        for r in rows:
            def g(k):
                i = idx.get(k)
                return r[i].strip() if i is not None and i < len(r) else ""
            nm = _clean(g("name"))
            if not nm:
                continue
            s = cur(g("set")) if g("set") else cur()
            s["songs"].append({"txt_name": nm, "in": _ms(g("in")), "hold": _ms(g("hold"), HOLD_INFINITE) if g("hold") else HOLD_INFINITE,
                               "out": _ms(g("out"))})
        if has_head:
            used = [k for k in ("set", "in", "hold", "out") if idx[k] is not None]
            if used:
                notes.append("Columns used: song" + "".join(f", {k}" for k in used) + " (times in seconds or m:ss).")
    else:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if set(line) <= set("-=_*~ "):
                continue                         # a ruler
            br = _set_break(line)
            if br:
                cur(br)
                continue
            nm = _clean(line)
            if nm:
                cur()["songs"].append({"txt_name": nm, "in": "0", "hold": HOLD_INFINITE, "out": "0"})
    sets = [s for s in sets if s["songs"]]
    n = sum(len(s["songs"]) for s in sets)
    if len(sets) > 1:
        notes.append(f"{len(sets)} sets found: " + ", ".join(f"{s['name']} ({len(s['songs'])})" for s in sets) + ".")
    dup = {}
    for s in sets:
        for so in s["songs"]:
            dup[so["txt_name"].casefold()] = dup.get(so["txt_name"].casefold(), 0) + 1
    twice = sorted(k for k, v in dup.items() if v > 1)
    if twice:
        notes.append("Listed more than once: " + ", ".join(twice[:6]) + ("…" if len(twice) > 6 else "") + ".")
    return {"sets": sets, "songs": n, "notes": notes, "format": fmt}


# ── the tablet page ──────────────────────────────────────────────────────────

_CSS = """
:root{--bg:#101114;--fg:#f2f2f2;--dim:#8b8f99;--acc:#7ee0a0;--card:#1b1d22;--line:#2b2e35}
@media (prefers-color-scheme: light){body.auto{--bg:#fafafa;--fg:#14161a;--dim:#6a6f7a;--acc:#157a43;--card:#fff;--line:#d9dce2}}
body.light{--bg:#fafafa;--fg:#14161a;--dim:#6a6f7a;--acc:#157a43;--card:#fff;--line:#d9dce2}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,system-ui,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
h1{font-size:18px;margin:0 auto 0 0}
button{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px;min-width:48px}
button.on{border-color:var(--acc);color:var(--acc)}
.tabs{display:flex;gap:8px;padding:10px 16px;overflow-x:auto}
ol{list-style:none;margin:0;padding:0 16px 80px}
li{display:flex;gap:14px;align-items:baseline;padding:.55em .2em;border-bottom:1px solid var(--line);font-size:var(--fs,34px);line-height:1.15;cursor:pointer;user-select:none}
li .n{color:var(--dim);font-size:.6em;min-width:2.2em;text-align:right}
li .t{flex:1}
li small{display:block;color:var(--dim);font-size:.5em;margin-top:.2em}
li.done{opacity:.35;text-decoration:line-through}
li.next .t{color:var(--acc)}
.set{display:none}.set.show{display:block}
.foot{position:fixed;bottom:0;left:0;right:0;background:var(--bg);border-top:1px solid var(--line);padding:8px 16px;color:var(--dim);font-size:13px;display:flex;justify-content:space-between}
"""

_JS = """
(function(){
  var KEY='qsk-setlist:'+document.title, st={};
  function load(){try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){st={}}}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
  load();
  var sets=[].slice.call(document.querySelectorAll('.set'));
  var tabs=[].slice.call(document.querySelectorAll('.tabs button'));
  function show(i){sets.forEach(function(s,k){s.classList.toggle('show',k===i)});tabs.forEach(function(t,k){t.classList.toggle('on',k===i)});st.tab=i;save();window.scrollTo(0,0);mark()}
  function mark(){sets.forEach(function(s){var first=true;[].forEach.call(s.querySelectorAll('li'),function(li){li.classList.remove('next');if(!li.classList.contains('done')&&first){li.classList.add('next');first=false}})})}
  tabs.forEach(function(t,k){t.onclick=function(){show(k)}});
  [].forEach.call(document.querySelectorAll('li'),function(li){
    var id=li.getAttribute('data-id'); if(st[id])li.classList.add('done');
    li.onclick=function(){li.classList.toggle('done');st[id]=li.classList.contains('done')?1:0;save();mark()}});
  var fs=parseInt(st.fs||34,10);function size(d){fs=Math.max(18,Math.min(80,fs+d));document.documentElement.style.setProperty('--fs',fs+'px');st.fs=fs;save()}
  document.getElementById('bigger').onclick=function(){size(4)};document.getElementById('smaller').onclick=function(){size(-4)};size(0);
  var nt=document.getElementById('notes');if(nt)nt.onclick=function(){document.body.classList.toggle('shownotes');nt.classList.toggle('on')};
  document.getElementById('theme').onclick=function(){document.body.classList.toggle('light');st.light=document.body.classList.contains('light')?1:0;save()};
  if(st.light)document.body.classList.add('light');
  document.getElementById('reset').onclick=function(){if(confirm('Untick every song?')){st={fs:fs,tab:st.tab};save();[].forEach.call(document.querySelectorAll('li'),function(l){l.classList.remove('done')});mark()}};
  show(Math.min(st.tab||0,sets.length-1));
})();
"""


def tablet_page(title: str, sets: List[Dict], *, notes: bool = False, generated: str = "") -> str:
    """One self-contained HTML file.  *sets*: ``[{name, songs: [{name, note}]}]``
    (empty sets are skipped).  *notes*: include each song's note (the QLC+
    function) behind a Notes button."""
    sets = [s for s in sets if s.get("songs")]
    e = html.escape
    tabs = "".join(f'<button type="button">{e(s["name"])} <span style="color:var(--dim)">{len(s["songs"])}</span></button>'
                   for s in sets) if len(sets) > 1 else ""
    body = []
    for si, s in enumerate(sets):
        li = []
        for n, so in enumerate(s["songs"], 1):
            note = f'<small class="note">{e(so["note"])}</small>' if notes and so.get("note") else ""
            li.append(f'<li data-id="{si}-{n}"><span class="n">{n}</span><span class="t">{e(so["name"])}{note}</span></li>')
        body.append(f'<section class="set"><ol>{"".join(li)}</ol></section>')
    total = sum(len(s["songs"]) for s in sets)
    note_btn = '<button type="button" id="notes">Notes</button>' if notes else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes"><title>{e(title)}</title>
<style>{_CSS}.note{{display:none}}.shownotes .note{{display:block}}</style></head>
<body class="auto"><header><h1>{e(title)}</h1>{note_btn}
<button type="button" id="smaller">A−</button><button type="button" id="bigger">A+</button>
<button type="button" id="theme">◐</button><button type="button" id="reset">Reset</button></header>
<div class="tabs">{tabs}</div>
{"".join(body)}
<div class="foot"><span>{total} song(s) · tap a song to tick it off</span><span>{e(generated)}</span></div>
<script>{_JS}</script></body></html>
"""
