"""
core/workspace.py
=================
Shared workspace state and QXW parsing logic.

This module is the single source of truth for the loaded workspace.
All Flask routes read from (and write to) the _state dict below.
It is a module-level singleton — safe for a single-user local tool.

Porting note
------------
This file contains the parsing logic extracted verbatim from the
monolithic qlc_swiss_knife_0.7.3.py.  The tkinter-specific parts
(UI updates, messagebox, etc.) have been removed; the XML parsing
is identical.
"""

import copy
import difflib
import os
import re
import string
import xml.etree.ElementTree as ET  # nosec B405

# ── QLC+ XML namespace ────────────────────────────────────────────────────────
QLC_NS_URI = 'http://www.qlcplus.org/Workspace'
NS = {'q': QLC_NS_URI}
ET.register_namespace('', QLC_NS_URI)

VERSION = "1.0-dev"

# ── Safety limits (same as the tkinter version) ───────────────────────────────
_MAX_XML_BYTES = 50 * 1024 * 1024   # 50 MB
_MAX_TXT_BYTES =  5 * 1024 * 1024   #  5 MB

# ── Module-level singleton state ──────────────────────────────────────────────
_state: dict = {
    'path':               None,   # real file path (path mode) or temp path (upload mode)
    'original_name':      None,   # original filename (upload mode only, else None)
    'output_dir':         None,   # user-selected output directory (persists across loads)
    'loaded':             False,
    # Raw XML (kept alive for trigger save-back and QXW generation)
    'xml_tree':           None,
    'qxw_root':           None,
    # Parsed maps
    'fixture_map':        {},   # fid -> {name, universe, address, groups, pos}
    'group_map':          {},   # group_id -> group_name
    'fixture_groups_map': {},   # fid -> [group_names]
    'func_by_name':       {},   # name -> fid
    'func_by_id':         {},   # fid -> name
    'func_detailed':      {},   # fid -> {name, type, contains}
    'vc_buttons':         {},   # fid -> {captions, frames}
    'vc_widgets':         [],   # list of widget dicts (ID Browser)
    'trigger_items':      {},   # uid -> {type, caption, func, key, uni, ch, _node}
    'available_frames':   set(),
    'chasers':            {},   # chaser_name -> fid
    'cuelist_slots':      [],   # [{id, caption, chaser_id, chaser_name}]
    'highest_func_id':    0,
    'shared_descriptions': {},  # fid -> description string (Dictionary Manager)
    'dict_file':          None, # path to loaded dictionary .txt
    'error':              None,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_state() -> dict:
    """Return a JSON-safe snapshot of the current state."""
    # In upload mode, original_name is set and _state['path'] is a temp path.
    # Expose the original filename to the client rather than the temp path.
    upload_mode = bool(_state.get('original_name'))
    return {
        'path':            None if upload_mode else _state['path'],
        'original_name':   _state.get('original_name'),
        'output_dir':      _state.get('output_dir') or '',
        'loaded':          _state['loaded'],
        'func_count':      len(_state['func_detailed']),
        'fixture_count':   len(_state['fixture_map']),
        'vc_widget_count': len(_state['vc_widgets']),
        'vc_button_count': len(_state['vc_buttons']),
        'error':           _state['error'],
    }


def get_output_dir() -> str:
    """Return the user-configured output directory, or empty string (= default)."""
    return _state.get('output_dir') or ''


def set_output_dir(path: str):
    """
    Set a custom output directory for generated QXW/PDF files.
    Pass an empty string to reset to the default (file's own directory).
    Raises ValueError if the path is non-empty and is not an existing directory.
    """
    p = (path or '').strip()
    if p and not os.path.isdir(p):
        raise ValueError(f'Not a directory: {p}')
    _state['output_dir'] = p or None


def load_qxw(path: str) -> dict:
    """
    Parse a .qxw workspace file and populate the shared state.
    Returns get_state() on success, raises on failure.
    """
    _reset()
    tree = _safe_parse_xml(path)
    root = tree.getroot()
    _state['path']          = path
    _state['original_name'] = None   # caller sets this for upload mode
    _state['loaded']        = True
    _state['xml_tree']      = tree
    _state['qxw_root']      = root
    _parse_shared_data(root)
    _parse_triggers(root)
    _parse_cuelist_slots(root)
    _state['error'] = None
    return get_state()


def set_original_name(name: str):
    """
    Mark the current workspace as loaded from an uploaded file.
    Stores the user-visible original filename so output filenames are
    derived from it (not from the temp path used internally).
    """
    _state['original_name'] = name or None


def get_functions() -> list:
    """Return func_detailed as a sorted list of dicts (by int ID), enriched with VC button and description."""
    rows = []
    for fid, info in _state['func_detailed'].items():
        vc    = _state['vc_buttons'].get(fid, {})
        capts = vc.get('captions', [])
        desc  = _state['shared_descriptions'].get(fid, '')
        rows.append({
            'id':        fid,
            'name':      info['name'],
            'type':      info['type'],
            'contains':  info['contains'],
            'vc_button': ', '.join(capts) if capts else '',
            'desc':      desc,
        })
    rows.sort(key=lambda r: _int(r['id']))
    return rows


def find_best_match(query: str):
    """
    Find the best-matching QLC+ function for a given query string.
    Uses a 4-stage algorithm: exact → single substring → token overlap → difflib fuzzy.
    Returns (matched_name, matched_id) tuple, or ('', '') if no match found.
    Ported verbatim from qlc_swiss_knife_0.7.3.py find_best_match().
    """
    fbn = _state['func_by_name']   # name -> fid
    if not fbn:
        return '', ''

    # Stage 1: exact match
    if query in fbn:
        return query, fbn[query]

    # Stage 2: single substring match (case-insensitive)
    q_lower = query.lower()
    matches = [(n, i) for n, i in fbn.items() if q_lower in n.lower()]
    if len(matches) == 1:
        return matches[0]

    # Stage 3: token overlap scoring
    _trans   = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
    q_tokens = set(query.translate(_trans).lower().split())
    best, best_id, max_ov = '', '', 0
    for name, fid in fbn.items():
        n_tokens = set(name.translate(_trans).lower().split())
        ov = len(q_tokens & n_tokens)
        if ov > max_ov:
            max_ov, best, best_id = ov, name, fid
    min_ov = min(2, len(q_tokens)) if q_tokens else 1
    if max_ov >= min_ov:
        return best, best_id
    if matches:
        return matches[0]

    # Stage 4: difflib fuzzy match
    all_names = list(fbn.keys())
    close = difflib.get_close_matches(q_lower, [n.lower() for n in all_names], n=1, cutoff=0.6)
    if close:
        for name, fid in fbn.items():
            if name.lower() == close[0]:
                return name, fid

    return '', ''


def get_vc_widgets() -> list:
    """Return a copy of the vc_widgets list sorted by widget ID."""
    rows = sorted(_state['vc_widgets'], key=lambda w: _int(w.get('widget_id', '0')))
    return rows


def get_fixtures() -> list:
    """Return fixture_map as a sorted list of dicts (by int ID)."""
    rows = []
    for fid, info in _state['fixture_map'].items():
        rows.append({'id': fid, **info})
    rows.sort(key=lambda r: _int(r['id']))
    return rows


def get_triggers(assigned_only: bool = False) -> list:
    """Return trigger_items as a sorted JSON-safe list (no _node)."""
    rows = []
    for uid, d in _state['trigger_items'].items():
        has = bool(d['key'] or (d['uni'] and d['ch']))
        if assigned_only and not has:
            continue
        rows.append({
            'uid':     uid,
            'type':    d['type'],
            'caption': d['caption'],
            'func':    d['func'],
            'key':     d['key'],
            'uni':     d['uni'],
            'ch':      d['ch'],
            'has':     has,
        })
    return rows


def update_trigger(uid: str, key: str, universe: str, channel: str) -> bool:
    """
    Update Key / MIDI Input on the in-memory XML node for one trigger.
    Returns True on success, False if uid not found.
    """
    d = _state['trigger_items'].get(uid)
    if d is None:
        return False
    node = d['_node']

    # Key
    kn = node.find(f'{{{QLC_NS_URI}}}Key')
    if key:
        if kn is None:
            kn = ET.SubElement(node, f'{{{QLC_NS_URI}}}Key')
        kn.text = key
    elif kn is not None:
        node.remove(kn)

    # MIDI Input
    inp = node.find(f'{{{QLC_NS_URI}}}Input')
    if universe and channel:
        if inp is None:
            inp = ET.SubElement(node, f'{{{QLC_NS_URI}}}Input', {'ID': '0'})
        inp.set('Universe', universe)
        inp.set('Channel', channel)
    elif inp is not None:
        node.remove(inp)

    d['key'] = key
    d['uni'] = universe
    d['ch']  = channel
    return True


def save_triggers() -> str:
    """Write the modified XML tree back to the .qxw file. Returns path."""
    if not _state['loaded']:
        raise RuntimeError('No workspace loaded.')
    if _state.get('original_name'):
        raise RuntimeError(
            'Triggers cannot be saved: the workspace was loaded via file upload. '
            'Use "Load by path" to enable this feature (paste the full .qxw path '
            'in the path field and click Load).'
        )
    if not _state['path']:
        raise RuntimeError('No workspace path available.')
    _state['xml_tree'].write(
        _state['path'],
        encoding='utf-8',
        xml_declaration=True,
    )
    return _state['path']


# ── Dictionary Manager ────────────────────────────────────────────────────────

def get_dictionary() -> list:
    """Return shared_descriptions merged with func_detailed as a list (includes vc_button)."""
    rows = []
    for fid, info in _state['func_detailed'].items():
        if '(Auto-Clone)' in info['name'] or '(Setlist)' in info['name']:
            continue
        vc    = _state['vc_buttons'].get(fid, {})
        capts = vc.get('captions', [])
        rows.append({
            'id':        fid,
            'name':      info['name'],
            'type':      info['type'],
            'desc':      _state['shared_descriptions'].get(fid, ''),
            'vc_button': ', '.join(capts) if capts else '',
        })
    rows.sort(key=lambda r: _int(r['id']))
    return rows


def update_description(fid: str, desc: str):
    _state['shared_descriptions'][fid] = desc


def load_dictionary(path: str) -> int:
    """Parse a pipe-delimited dictionary TXT. Returns count of entries loaded."""
    lines = _safe_read_txt(path)
    count = 0
    for line in lines:
        cl = line.strip()
        if not cl or cl.startswith('ID|'):
            continue
        parts = cl.split('|')
        if len(parts) >= 3 and parts[0].isdigit():
            fid  = parts[0].strip()
            desc = '|'.join(parts[2:]).strip().replace('\\n', '\n')
            _state['shared_descriptions'][fid] = desc
            count += 1
    _state['dict_file'] = path
    return count


def save_dictionary(path: str):
    """Write shared_descriptions to a pipe-delimited TXT file."""
    import csv, io
    lines = ['ID|Name|Description\n']
    for fid in sorted(_state['shared_descriptions'], key=lambda x: _int(x)):
        name = _state['func_by_id'].get(fid, '')
        desc = _state['shared_descriptions'].get(fid, '').replace('\n', '\\n')
        lines.append(f'{fid}|{name}|{desc}\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


# ── Setlist slots ─────────────────────────────────────────────────────────────

def get_cuelist_slots() -> list:
    return list(_state['cuelist_slots'])


# In-memory song lists per slot (simple string list, for TXT load/save)
_slot_songs: dict = {}    # slot_id -> [song strings]

# Detailed slot data: full song rows with func assignment and timing
_slot_details: dict = {}  # slot_id -> [{txt_name, qxw_id, qxw_name, in, hold, out}]


def get_slot_songs(slot_id: str) -> list:
    return list(_slot_songs.get(slot_id, []))


def set_slot_songs(slot_id: str, songs: list):
    _slot_songs[slot_id] = [s for s in songs if s.strip()]


def get_slot_details(slot_id: str) -> list:
    """Return the detailed song list for a slot."""
    return list(_slot_details.get(slot_id, []))


def set_slot_details(slot_id: str, rows: list):
    """
    Replace the detailed song list for a slot.
    Each row must be a dict with keys:
      txt_name, qxw_id, qxw_name, in, hold, out
    """
    _slot_details[slot_id] = list(rows)
    # Keep the simple string list in sync
    _slot_songs[slot_id] = [r.get('txt_name', '') for r in rows]


def update_song_detail(slot_id: str, row_idx: int, patch: dict):
    """Merge patch into a single song row."""
    rows = _slot_details.setdefault(slot_id, [])
    while len(rows) <= row_idx:
        rows.append({'txt_name': '', 'qxw_id': '', 'qxw_name': '', 'in': '0', 'hold': '4294967294', 'out': '0'})
    rows[row_idx].update(patch)


def get_available_chasers() -> list:
    """Return [{'id': fid, 'name': name}] for all Chaser functions."""
    rows = []
    for name, fid in _state['chasers'].items():
        rows.append({'id': fid, 'name': name})
    rows.sort(key=lambda r: _int(r['id']))
    return rows


def generate_slot_qxw(slot_id: str, target_chaser_id: str = None) -> str:
    """
    Clone each song's base function, build/update a Chaser with the cloned steps,
    then write a new QXW file (incrementing the filename).

    Parameters
    ----------
    slot_id           : str   — CueList widget ID
    target_chaser_id  : str | None
        Existing chaser function ID to target. If None or empty, creates a new one.

    Returns
    -------
    str  — path of the newly written .qxw file
    """
    if not _state['loaded'] or not _state['qxw_root']:
        raise RuntimeError('No workspace loaded.')

    songs = _slot_details.get(slot_id, [])
    if not songs:
        raise ValueError('No song details loaded for this slot.')

    root   = _state['qxw_root']
    engine = root.find('q:Engine', NS)
    if engine is None:
        raise ValueError('Template has no <Engine> element.')

    linked = False
    create_new = not target_chaser_id or target_chaser_id == '__new__'

    if create_new:
        _state['highest_func_id'] += 1
        mc_id = str(_state['highest_func_id'])
        master = ET.SubElement(
            engine, f'{{{QLC_NS_URI}}}Function',
            {'ID': mc_id, 'Type': 'Chaser',
             'Name': f'Setlist Chaser Slot{slot_id} (Auto)'}
        )
        ET.SubElement(master, f'{{{QLC_NS_URI}}}Speed',
                      {'FadeIn': '0', 'FadeOut': '0', 'Duration': '4294967294'})
        ET.SubElement(master, f'{{{QLC_NS_URI}}}Direction').text = 'Forward'
        ET.SubElement(master, f'{{{QLC_NS_URI}}}RunOrder').text  = 'Loop'
        ET.SubElement(master, f'{{{QLC_NS_URI}}}SpeedModes',
                      {'FadeIn': 'PerStep', 'FadeOut': 'PerStep', 'Duration': 'Common'})
        # Auto-link to the corresponding CueList widget
        slot_info = next((s for s in _state['cuelist_slots'] if s['id'] == slot_id), None)
        cap = slot_info['caption'] if slot_info else None
        linked_cl = None
        if cap:
            for cl in root.findall('.//q:CueList', NS):
                if cl.get('Caption', '') == cap:
                    linked_cl = cl; break
        if linked_cl is None:
            for cl in root.findall('.//q:CueList', NS):
                cn = cl.find('q:Chaser', NS)
                if cn is not None and cn.text in ('4294967295', '-1'):
                    linked_cl = cl; break
        if linked_cl is not None:
            cn = linked_cl.find('q:Chaser', NS)
            if cn is not None:
                cn.text = mc_id; linked = True
    else:
        mc_id  = target_chaser_id
        master = _find_by_id(engine, 'Function', mc_id)
        if master is None:
            raise ValueError(f'Chaser ID {mc_id} not found in workspace.')
        for step in master.findall('q:Step', NS):
            master.remove(step)
        spd = master.find('q:Speed', NS)
        if spd is not None:
            spd.set('Duration', '4294967294')
        spm = master.find('q:SpeedModes', NS)
        if spm is not None:
            spm.set('FadeIn', 'PerStep'); spm.set('FadeOut', 'PerStep'); spm.set('Duration', 'Common')

    # Clone base functions and add steps
    step_count = 0
    active_ids: set = set()
    for d in songs:
        bid = d.get('qxw_id', '')
        if not bid:
            continue
        base = _find_by_id(engine, 'Function', bid)
        if base is None:
            continue
        txt_n = d.get('txt_name') or f'Step {step_count}'
        _state['highest_func_id'] += 1
        cid = str(_state['highest_func_id'])
        active_ids.add(cid)
        clone = copy.deepcopy(base)
        clone.set('ID', cid)
        clone.set('Name', f'{txt_n} (Setlist)')
        engine.append(clone)
        sa = {
            'Number':  str(step_count),
            'FadeIn':  str(d.get('in', '0')),
            'Hold':    str(d.get('hold', '4294967294')),
            'FadeOut': str(d.get('out', '0')),
        }
        step_el = ET.SubElement(master, f'{{{QLC_NS_URI}}}Step', sa)
        step_el.text = cid
        step_count += 1

    # Remove stale Setlist clones no longer referenced
    used_by_others: set = set()
    for f in engine.findall('q:Function', NS):
        if f.get('ID') == mc_id:
            continue
        for step in f.findall('q:Step', NS):
            if step.text:
                used_by_others.add(step.text)
    for func in engine.findall('q:Function', NS):
        fn  = func.get('Name', '')
        fid = func.get('ID')
        if ('(Setlist)' in fn) and (fid not in active_ids) and (fid not in used_by_others):
            engine.remove(func)

    # Determine output filename
    # Priority:
    #   1. user-set output_dir override (persists across loads)
    #   2. upload mode → CWD (same as script directory)
    #   3. path mode → directory of the loaded .qxw file (v0.7.3 parity)
    orig_name       = _state.get('original_name')
    output_dir_override = _state.get('output_dir')
    if output_dir_override:
        odir = output_dir_override
        src  = orig_name or _state['path'] or 'workspace.qxw'
    elif orig_name:
        odir = os.getcwd()
        src  = orig_name
    else:
        src  = _state['path'] or 'workspace.qxw'
        odir = os.path.dirname(os.path.abspath(src))
    obn  = os.path.splitext(os.path.basename(src))[0]
    m    = re.search(r'(\d+)$', obn)
    if m:
        bn = obn[:m.start()] + str(int(m.group(1)) + 1).zfill(len(m.group(1)))
    else:
        bn = f'{obn}_GIG_READY'

    nf = os.path.join(odir, bn + '.qxw')
    counter = 0
    while os.path.exists(nf):
        counter += 1
        m2 = re.search(r'(\d+)$', bn)
        if m2:
            bn = bn[:m2.start()] + str(int(m2.group(1)) + 1).zfill(len(m2.group(1)))
        else:
            bn = f'{bn}_{counter}'
        nf = os.path.join(odir, bn + '.qxw')

    xb = ET.tostring(root, encoding='utf-8').decode('utf-8')
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xb
    with open(nf, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    # Do NOT update _state['path'] here.  The source workspace stays the
    # originally loaded file so that repeated generate calls keep producing
    # correctly-numbered outputs (matching v0.7.3 behaviour where
    # app.current_qxw_file never changes after a generate).
    return nf


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _reset():
    _state['path']               = None
    _state['original_name']      = None
    _state['loaded']             = False
    _state['xml_tree']           = None
    _state['qxw_root']           = None
    _state['fixture_map']        = {}
    _state['group_map']          = {}
    _state['fixture_groups_map'] = {}
    _state['func_by_name']       = {}
    _state['func_by_id']         = {}
    _state['func_detailed']      = {}
    _state['vc_buttons']         = {}
    _state['vc_widgets']         = []
    _state['trigger_items']      = {}
    _state['available_frames']   = set()
    _state['chasers']            = {}
    _state['cuelist_slots']      = []
    _state['highest_func_id']    = 0
    _state['error']              = None
    _slot_songs.clear()
    _slot_details.clear()


def _int(s, default=0) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _safe_parse_xml(path: str) -> ET.ElementTree:
    """Parse XML with a 50 MB size cap to mitigate billion-laughs DoS."""
    size = os.path.getsize(path)
    if size > _MAX_XML_BYTES:
        raise ValueError(
            f"File too large ({size // (1024*1024)} MB). "
            f"Max allowed: {_MAX_XML_BYTES // (1024*1024)} MB."
        )
    return ET.parse(path)  # nosec B314


def _safe_read_txt(path: str) -> list:
    """Read a text file with a 5 MB size cap."""
    size = os.path.getsize(path)
    if size > _MAX_TXT_BYTES:
        raise ValueError(
            f"File too large ({size // 1024} KB). "
            f"Max allowed: {_MAX_TXT_BYTES // 1024} KB."
        )
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()


def _find_by_id(parent, tag_local: str, fid, ns_uri=QLC_NS_URI):
    """XPath-injection-safe element lookup by ID attribute."""
    tag_full = f"{{{ns_uri}}}{tag_local}"
    for child in parent:
        if child.tag == tag_full and child.get("ID") == str(fid):
            return child
    return None


def _findall_by_id(parent, tag_local: str, fid, ns_uri=QLC_NS_URI) -> list:
    tag_full = f"{{{ns_uri}}}{tag_local}"
    return [c for c in parent if c.tag == tag_full and c.get("ID") == str(fid)]


# =============================================================================
# PARSING  (extracted verbatim from QLCSwissKnife._parse_shared_data)
# =============================================================================

def _parse_shared_data(qxw_root: ET.Element):
    """Populate all shared maps from the loaded XML root element."""

    # ── Fixture Groups ────────────────────────────────────────────────────────
    for group in qxw_root.findall('q:Engine/q:FixtureGroup', NS):
        g_id = group.get('ID')
        g_name_node = group.find('q:Name', NS)
        g_name = (g_name_node.text or "").strip() if g_name_node is not None else f"Group {g_id}"
        if not g_name:
            g_name = f"Group {g_id}"
        if g_id:
            _state['group_map'][g_id] = g_name
        for head in group.findall('q:Head', NS):
            f_id = head.get('Fixture')
            if f_id:
                _state['fixture_groups_map'].setdefault(f_id, [])
                if g_name not in _state['fixture_groups_map'][f_id]:
                    _state['fixture_groups_map'][f_id].append(g_name)

    # ── 3D Monitor positions ──────────────────────────────────────────────────
    monitor_pos = {}
    for fx_item in qxw_root.findall('.//q:Monitor/q:FxItem', NS):
        f_id = fx_item.get('ID')
        monitor_pos[f_id] = (
            float(fx_item.get('XPos', '0')),
            float(fx_item.get('YPos', '0')),
            float(fx_item.get('ZPos', '0')),
        )

    # ── Fixtures ──────────────────────────────────────────────────────────────
    _COLOR_PALETTE = ["#00e5ff", "#ff007f", "#39ff14", "#ffff00",
                      "#ff8c00", "#b026ff", "#ff3333"]
    _model_color_map: dict = {}

    for fix in qxw_root.findall('q:Engine/q:Fixture', NS):
        f_id_node = fix.find('q:ID', NS)
        f_id = fix.get('ID')
        if f_id_node is not None:
            f_id = f_id_node.text or f_id

        f_name_node = fix.find('q:Name', NS)
        f_name = (f_name_node.text or "").strip() if f_name_node is not None else ""
        if not f_name:
            f_name = f"Fixture {f_id}"

        mfg_node   = fix.find('q:Manufacturer', NS)
        model_node = fix.find('q:Model',        NS)
        mode_node  = fix.find('q:Mode',         NS)
        mfg   = mfg_node.text   if mfg_node   is not None else "Unknown"
        model = model_node.text if model_node  is not None else "Unknown"
        mode  = mode_node.text  if mode_node   is not None else "Default"

        if model not in _model_color_map:
            _model_color_map[model] = _COLOR_PALETTE[len(_model_color_map) % len(_COLOR_PALETTE)]
        color = _model_color_map[model]

        uni_node  = fix.find('q:Universe', NS)
        addr_node = fix.find('q:Address', NS)
        universe  = max(0, min(255, int(uni_node.text)))  if uni_node  is not None else 0
        address   = max(0, min(511, int(addr_node.text))) if addr_node is not None else 0

        groups    = _state['fixture_groups_map'].get(f_id, [])
        group_str = ", ".join(groups) if groups else "—"
        pos       = monitor_pos.get(f_id, (0, 0, 0))
        pos_str   = f"X:{pos[0]:.0f} Y:{pos[1]:.0f} Z:{pos[2]:.0f}"

        if f_id:
            _state['fixture_map'][f_id] = {
                'name':     f_name,
                'universe': universe + 1,
                'address':  address  + 1,
                'groups':   group_str,
                'pos':      pos_str,
                # Fixture type info
                'manufacturer': mfg,
                'model':    f"{mfg} {model}",
                'mode':     mode,
                'patch':    f"U{universe+1}.{address+1:03d}",
                'color':    color,
                # Raw 3D coords for blueprint PDF
                'x_mm':     pos[0],
                'y_mm':     pos[1],
                'z_mm':     pos[2],
                'in_3d':    pos[0] != 0 or pos[1] != 0 or pos[2] != 0,
            }

    # ── Functions ─────────────────────────────────────────────────────────────
    for func in qxw_root.findall('q:Engine/q:Function', NS):
        f_name = func.get('Name')
        f_id   = func.get('ID')
        f_type = func.get('Type')

        if f_id:
            int_id = _int(f_id)
            if int_id > _state['highest_func_id']:
                _state['highest_func_id'] = int_id

        if f_name and f_id:
            _state['func_by_name'][f_name] = f_id
            _state['func_by_id'][f_id]     = f_name

            if f_type == 'Chaser':
                _state['chasers'][f_name] = f_id

            contains = [s.text for s in func.findall('q:Step', NS) if s.text]
            _state['func_detailed'][f_id] = {
                'name':     f_name,
                'type':     f_type or '',
                'contains': ", ".join(contains),
            }

    # ── Virtual Console ───────────────────────────────────────────────────────
    vc_root = qxw_root.find('q:VirtualConsole', NS)
    if vc_root is not None:
        _parse_vc_node(vc_root, [])


_WIDGET_TYPES = {
    "Button", "Slider", "Knob", "SpeedDial", "XYPad",
    "Label", "Clock", "VUMeter", "AudioTrigger", "Animation",
    "Frame", "SoloFrame", "CueList",
}


def _parse_vc_node(node: ET.Element, frame_ancestry: list):
    """
    Recursively walk the Virtual Console XML tree.
    Populates _state['vc_buttons'] and _state['vc_widgets'].
    Extracted verbatim from QLCSwissKnife._parse_vc_node.
    """
    tag_name = node.tag.replace(f"{{{QLC_NS_URI}}}", "")

    if tag_name in ("Frame", "SoloFrame"):
        caption = node.get('Caption', frame_ancestry[-1] if frame_ancestry else "[No Frame]")
        _state['available_frames'].add(caption)
        frame_ancestry = frame_ancestry + [caption]

    if tag_name in _WIDGET_TYPES:
        wid     = node.get('ID', '')
        caption = node.get('Caption', '').replace('\n', ' ').strip()
        wx, wy  = node.get('X', ''), node.get('Y', '')
        ww, wh  = node.get('Width', ''), node.get('Height', '')

        func_node = node.find('q:Function', NS)
        if func_node is not None:
            fid = func_node.get('ID', '')
            if fid in ("4294967295", "-1"):
                fid = ''
        else:
            chaser_node = node.find('q:Chaser', NS)
            fid = (chaser_node.text or '').strip() if chaser_node is not None else ''
            if fid in ("4294967295", "-1"):
                fid = ''

        fname      = _state['func_by_id'].get(fid, '') if fid else ''
        frame_path = " › ".join(frame_ancestry) if frame_ancestry else "[Root]"

        if wid:
            _state['vc_widgets'].append({
                'widget_id':   wid,
                'type':        tag_name,
                'caption':     caption,
                'func_id':     fid,
                'func_name':   fname,
                'frame_path':  frame_path,
                'x': wx, 'y': wy, 'w': ww, 'h': wh,
            })

        # Legacy vc_buttons (keeps other tabs working)
        if tag_name == "Button":
            key_node = node.find('q:KeySequence', NS)
            key      = key_node.text if key_node is not None else ''
            input_node = node.find('q:Input', NS)
            midi_uni = midi_chan = ''
            if input_node is not None:
                midi_uni  = input_node.get('Universe', '')
                midi_chan = input_node.get('Channel', '')

            if fid:
                _state['vc_buttons'].setdefault(fid, {'captions': [], 'frames': []})
                if caption:
                    _state['vc_buttons'][fid]['captions'].append(caption)
                if frame_ancestry:
                    _state['vc_buttons'][fid]['frames'].extend(frame_ancestry)

    for child in node:
        _parse_vc_node(child, frame_ancestry)


# =============================================================================
# TRIGGER PARSING  (extracted from TriggerManagerTab._parse_triggers)
# =============================================================================

def _parse_triggers(qxw_root: ET.Element):
    """Walk VC XML and populate _state['trigger_items'] with Key/MIDI data."""
    _state['trigger_items'].clear()
    vc_root = qxw_root.find('q:VirtualConsole', NS)
    if vc_root is not None:
        _walk_triggers(vc_root)


def _walk_triggers(node: ET.Element):
    tag = node.tag.replace(f'{{{QLC_NS_URI}}}', '')

    if tag == 'Button':
        wid = node.get('ID', '')
        cap = node.get('Caption', 'Unnamed').replace('\n', ' ').strip()
        fn  = node.find('q:Function', NS)
        fid = fn.get('ID') if fn is not None else None
        if fid and fid not in ('4294967295', '-1'):
            fname = _state['func_by_id'].get(fid, f'ID {fid}')
        else:
            fname = ''
        kn  = node.find('q:Key', NS)
        inp = node.find('q:Input', NS)
        _state['trigger_items'][f'btn_{wid}'] = {
            'type': 'Button', 'caption': cap, 'func': fname,
            'key': kn.text if kn is not None and kn.text else '',
            'uni': inp.get('Universe', '') if inp is not None else '',
            'ch':  inp.get('Channel',  '') if inp is not None else '',
            '_node': node,
        }

    elif tag == 'CueList':
        wid = node.get('ID', '')
        cap = node.get('Caption', 'Unnamed CueList').replace('\n', ' ').strip()
        cn  = node.find('q:Chaser', NS)
        fid = (cn.text or '').strip() if cn is not None else ''
        fname = _state['func_by_id'].get(fid, f'ID {fid}') if fid and fid not in ('4294967295', '-1') else 'Empty'
        for action in ('Next', 'Previous', 'Stop'):
            tn = node.find(f'q:{action}', NS)
            if tn is not None:
                kn  = tn.find('q:Key', NS)
                inp = tn.find('q:Input', NS)
                _state['trigger_items'][f'cl_{wid}_{action}'] = {
                    'type': f'CueList ({action})', 'caption': cap, 'func': fname,
                    'key': kn.text if kn is not None and kn.text else '',
                    'uni': inp.get('Universe', '') if inp is not None else '',
                    'ch':  inp.get('Channel',  '') if inp is not None else '',
                    '_node': tn,
                }

    elif tag in ('Slider', 'Knob', 'SpeedDial'):
        wid = node.get('ID', '')
        cap = node.get('Caption', f'Unnamed {tag}').replace('\n', ' ').strip()
        fn  = node.find('q:Function', NS)
        fid = fn.get('ID') if fn is not None else None
        fname = _state['func_by_id'].get(fid, f'{tag} (Level)') if fid and fid not in ('4294967295', '-1') else f'{tag} (Level)'
        inp   = node.find('q:Input', NS)
        has   = inp is not None and inp.get('Universe', '')
        if fid and fid not in ('4294967295', '-1') or has:
            _state['trigger_items'][f'{tag.lower()}_{wid}'] = {
                'type': tag, 'caption': cap, 'func': fname,
                'key': '',
                'uni': inp.get('Universe', '') if inp is not None else '',
                'ch':  inp.get('Channel',  '') if inp is not None else '',
                '_node': node,
            }

    for child in node:
        _walk_triggers(child)


# =============================================================================
# CUELIST / SETLIST SLOT PARSING
# =============================================================================

def _parse_cuelist_slots(qxw_root: ET.Element):
    """Find all CueList widgets in VC and pair them with their Chaser."""
    _state['cuelist_slots'].clear()
    vc_root = qxw_root.find('q:VirtualConsole', NS)
    if vc_root is None:
        return
    _collect_cuelist_slots(vc_root)


def _collect_cuelist_slots(node: ET.Element):
    tag = node.tag.replace(f'{{{QLC_NS_URI}}}', '')
    if tag == 'CueList':
        wid = node.get('ID', '')
        cap = node.get('Caption', f'CueList {wid}').replace('\n', ' ').strip()
        cn  = node.find('q:Chaser', NS)
        chaser_id   = (cn.text or '').strip() if cn is not None else ''
        chaser_name = _state['func_by_id'].get(chaser_id, '') if chaser_id else ''
        _state['cuelist_slots'].append({
            'id':          wid,
            'caption':     cap,
            'chaser_id':   chaser_id,
            'chaser_name': chaser_name,
        })
    for child in node:
        _collect_cuelist_slots(child)
