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

import os
import re
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
    'path':               None,
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
    return {
        'path':            _state['path'],
        'loaded':          _state['loaded'],
        'func_count':      len(_state['func_detailed']),
        'fixture_count':   len(_state['fixture_map']),
        'vc_widget_count': len(_state['vc_widgets']),
        'vc_button_count': len(_state['vc_buttons']),
        'error':           _state['error'],
    }


def load_qxw(path: str) -> dict:
    """
    Parse a .qxw workspace file and populate the shared state.
    Returns get_state() on success, raises on failure.
    """
    _reset()
    tree = _safe_parse_xml(path)
    root = tree.getroot()
    _state['path']     = path
    _state['loaded']   = True
    _state['xml_tree'] = tree
    _state['qxw_root'] = root
    _parse_shared_data(root)
    _parse_triggers(root)
    _parse_cuelist_slots(root)
    _state['error'] = None
    return get_state()


def get_functions() -> list:
    """Return func_detailed as a sorted list of dicts (by int ID)."""
    rows = []
    for fid, info in _state['func_detailed'].items():
        rows.append({
            'id':       fid,
            'name':     info['name'],
            'type':     info['type'],
            'contains': info['contains'],
        })
    rows.sort(key=lambda r: _int(r['id']))
    return rows


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
    if not _state['loaded'] or not _state['path']:
        raise RuntimeError('No workspace loaded.')
    _state['xml_tree'].write(
        _state['path'],
        encoding='utf-8',
        xml_declaration=True,
    )
    return _state['path']


# ── Dictionary Manager ────────────────────────────────────────────────────────

def get_dictionary() -> list:
    """Return shared_descriptions merged with func_detailed as a list."""
    rows = []
    for fid, info in _state['func_detailed'].items():
        if '(Auto-Clone)' in info['name'] or '(Setlist)' in info['name']:
            continue
        rows.append({
            'id':   fid,
            'name': info['name'],
            'type': info['type'],
            'desc': _state['shared_descriptions'].get(fid, ''),
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


# In-memory song lists per slot (not persisted to QXW — user loads/saves TXT)
_slot_songs: dict = {}   # slot_id -> [song strings]


def get_slot_songs(slot_id: str) -> list:
    return list(_slot_songs.get(slot_id, []))


def set_slot_songs(slot_id: str, songs: list):
    _slot_songs[slot_id] = [s for s in songs if s.strip()]


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _reset():
    _state['path']               = None
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
    for fix in qxw_root.findall('q:Engine/q:Fixture', NS):
        f_id_node = fix.find('q:ID', NS)
        f_id = fix.get('ID')
        if f_id_node is not None:
            f_id = f_id_node.text or f_id

        f_name_node = fix.find('q:Name', NS)
        f_name = (f_name_node.text or "").strip() if f_name_node is not None else ""
        if not f_name:
            f_name = f"Fixture {f_id}"

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
