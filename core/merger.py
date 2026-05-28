"""
core/merger.py
==============
QXW file merger: load two workspaces independently, browse their elements,
and copy Fixtures / Fixture Groups / Functions from source into destination
with safe ID remapping.

All state is kept in two independent dictionaries (_src, _dst) so this
module never touches the main workspace singleton in core/workspace.py.

Public API
----------
load_src(path)       → dict  (summary of what is in the source QXW)
load_dst(path)       → dict  (summary of what is in the destination QXW)
get_src_summary()    → dict
get_dst_summary()    → dict
list_src_fixtures()  → list[dict]
list_src_groups()    → list[dict]
list_src_functions() → list[dict]
list_dst_fixtures()  → list[dict]   (to detect name clashes)
list_dst_functions() → list[dict]
copy_elements(fixture_ids, group_ids, function_ids) → dict (warnings)
export_dst()         → (suggested_filename: str, xml_bytes: bytes)
clear_src()          / clear_dst()
get_state()          → dict {src_loaded, dst_loaded, src_name, dst_name}
"""

from __future__ import annotations

import os
import re
import copy
from xml.etree import ElementTree as ET

# ── Module-level state ────────────────────────────────────────────────────────

_src: dict = {'loaded': False, 'path': None, 'name': None, 'tree': None, 'root': None}
_dst: dict = {'loaded': False, 'path': None, 'name': None, 'tree': None, 'root': None}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_qxw(path: str) -> tuple[ET.ElementTree, ET.Element]:
    """Parse a QXW file; return (tree, root)."""
    tree = ET.parse(path)
    root = tree.getroot()
    return tree, root


def _short_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _engine(root: ET.Element) -> ET.Element | None:
    return root.find('Engine')


def _max_id(root: ET.Element) -> int:
    """Find the highest numeric ID used anywhere in the Engine block."""
    engine = _engine(root)
    if engine is None:
        return 0
    hi = 0
    for el in engine.iter():
        for attr in ('ID', 'id'):
            val = el.get(attr, '')
            if val.isdigit():
                hi = max(hi, int(val))
    return hi


def _collect_fixtures(engine: ET.Element) -> list[ET.Element]:
    return engine.findall('Fixture')


def _collect_groups(engine: ET.Element) -> list[ET.Element]:
    return engine.findall('FixtureGroup')


def _collect_functions(engine: ET.Element) -> list[ET.Element]:
    return engine.findall('Function')


def _fixture_summary(el: ET.Element) -> dict:
    return {
        'id':       el.get('ID', ''),
        'name':     el.get('Name', ''),
        'model':    el.get('Model', ''),
        'universe': el.get('Universe', '0'),
        'address':  el.get('Address', '0'),
        'channels': el.get('Channels', ''),
        'mode':     el.get('Mode', ''),
    }


def _group_summary(el: ET.Element) -> dict:
    members = [c.text or '' for c in el.findall('FixtureGroupMember')]
    return {
        'id':      el.get('ID', ''),
        'name':    el.get('Name', ''),
        'size':    el.get('Size', ''),
        'members': members,
    }


def _function_summary(el: ET.Element) -> dict:
    return {
        'id':   el.get('ID', ''),
        'name': el.get('Name', ''),
        'type': el.get('Type', ''),
    }


def _make_summary(root: ET.Element) -> dict:
    engine = _engine(root)
    if engine is None:
        return {'fixtures': 0, 'groups': 0, 'functions': 0}
    return {
        'fixtures':  len(_collect_fixtures(engine)),
        'groups':    len(_collect_groups(engine)),
        'functions': len(_collect_functions(engine)),
    }


# ── Public load / clear ───────────────────────────────────────────────────────

def load_src(path: str) -> dict:
    global _src
    tree, root = _parse_qxw(path)
    _src = {'loaded': True, 'path': path, 'name': _short_name(path),
             'tree': tree, 'root': root}
    return _make_summary(root)


def load_dst(path: str) -> dict:
    global _dst
    tree, root = _parse_qxw(path)
    _dst = {'loaded': True, 'path': path, 'name': _short_name(path),
             'tree': tree, 'root': root}
    return _make_summary(root)


def clear_src():
    global _src
    _src = {'loaded': False, 'path': None, 'name': None, 'tree': None, 'root': None}


def clear_dst():
    global _dst
    _dst = {'loaded': False, 'path': None, 'name': None, 'tree': None, 'root': None}


def get_state() -> dict:
    return {
        'src_loaded': _src['loaded'],
        'dst_loaded': _dst['loaded'],
        'src_name':   _src['name'],
        'dst_name':   _dst['name'],
    }


# ── List helpers ──────────────────────────────────────────────────────────────

def get_src_summary() -> dict:
    if not _src['loaded']:
        return {}
    return _make_summary(_src['root'])


def get_dst_summary() -> dict:
    if not _dst['loaded']:
        return {}
    return _make_summary(_dst['root'])


def list_src_fixtures() -> list[dict]:
    if not _src['loaded']:
        return []
    engine = _engine(_src['root'])
    if engine is None:
        return []
    return [_fixture_summary(e) for e in _collect_fixtures(engine)]


def list_src_groups() -> list[dict]:
    if not _src['loaded']:
        return []
    engine = _engine(_src['root'])
    if engine is None:
        return []
    return [_group_summary(e) for e in _collect_groups(engine)]


def list_src_functions() -> list[dict]:
    if not _src['loaded']:
        return []
    engine = _engine(_src['root'])
    if engine is None:
        return []
    return [_function_summary(e) for e in _collect_functions(engine)]


def list_dst_fixtures() -> list[dict]:
    if not _dst['loaded']:
        return []
    engine = _engine(_dst['root'])
    if engine is None:
        return []
    return [_fixture_summary(e) for e in _collect_fixtures(engine)]


def list_dst_functions() -> list[dict]:
    if not _dst['loaded']:
        return []
    engine = _engine(_dst['root'])
    if engine is None:
        return []
    return [_function_summary(e) for e in _collect_functions(engine)]


# ── Core copy logic ───────────────────────────────────────────────────────────

def copy_elements(
    fixture_ids:  list[str],
    group_ids:    list[str],
    function_ids: list[str],
) -> dict:
    """
    Copy the selected elements from source into destination, remapping IDs.

    Returns a dict:
      {
        'ok': True,
        'copied': {'fixtures': N, 'groups': N, 'functions': N},
        'warnings': [str, ...],     # name conflicts, missing fixtures, etc.
        'id_map': {'old_id': 'new_id', ...},   # full src→dst ID mapping
      }
    """
    if not _src['loaded']:
        raise RuntimeError('Source QXW not loaded.')
    if not _dst['loaded']:
        raise RuntimeError('Destination QXW not loaded.')

    src_engine = _engine(_src['root'])
    dst_engine = _engine(_dst['root'])
    if src_engine is None or dst_engine is None:
        raise RuntimeError('Could not locate Engine block in one or both QXW files.')

    warnings: list[str] = []
    id_counter = _max_id(_dst['root'])
    id_map: dict[str, str] = {}   # src_old_id → dst_new_id (str→str)

    def _next_id() -> str:
        nonlocal id_counter
        id_counter += 1
        return str(id_counter)

    # Index existing destination names to detect conflicts
    dst_fixture_names  = {e.get('Name', '') for e in _collect_fixtures(dst_engine)}
    dst_group_names    = {e.get('Name', '') for e in _collect_groups(dst_engine)}
    dst_function_names = {e.get('Name', '') for e in _collect_functions(dst_engine)}

    copied_fixtures  = 0
    copied_groups    = 0
    copied_functions = 0

    # ── 1. Fixtures ────────────────────────────────────────────────────────────
    fixture_id_set = set(fixture_ids)
    for el in _collect_fixtures(src_engine):
        old_id = el.get('ID', '')
        if old_id not in fixture_id_set:
            continue
        new_id   = _next_id()
        id_map[old_id] = new_id
        new_el   = copy.deepcopy(el)
        new_el.set('ID', new_id)
        name = new_el.get('Name', '')
        if name in dst_fixture_names:
            warnings.append(f'Fixture name already exists in destination: "{name}" (copied anyway)')
        dst_engine.append(new_el)
        dst_fixture_names.add(name)
        copied_fixtures += 1

    # ── 2. Fixture Groups ──────────────────────────────────────────────────────
    group_id_set = set(group_ids)
    for el in _collect_groups(src_engine):
        old_id = el.get('ID', '')
        if old_id not in group_id_set:
            continue
        new_id   = _next_id()
        id_map[old_id] = new_id
        new_el   = copy.deepcopy(el)
        new_el.set('ID', new_id)
        # Remap FixtureGroupMember fixture IDs if those fixtures were copied too
        for member in new_el.findall('FixtureGroupMember'):
            # FixtureGroupMember format: "fixtureID headIndex"
            raw = (member.get('Fixture') or member.text or '').strip()
            parts = raw.split()
            if parts:
                fid = parts[0]
                if fid in id_map:
                    new_val = id_map[fid] + (' ' + ' '.join(parts[1:]) if len(parts) > 1 else '')
                    if member.get('Fixture') is not None:
                        member.set('Fixture', new_val)
                    else:
                        member.text = new_val
                else:
                    warnings.append(
                        f'Group "{new_el.get("Name", old_id)}" references fixture ID {fid} '
                        f'which was not copied — member skipped.'
                    )
                    new_el.remove(member)
        name = new_el.get('Name', '')
        if name in dst_group_names:
            warnings.append(f'Fixture Group name already exists in destination: "{name}" (copied anyway)')
        dst_engine.append(new_el)
        dst_group_names.add(name)
        copied_groups += 1

    # ── 3. Functions (all types) ───────────────────────────────────────────────
    # Two-pass: first assign new IDs for all selected functions,
    # then deep-copy and rewrite all internal ID references.
    function_id_set = set(function_ids)
    selected_fns: list[ET.Element] = []
    for el in _collect_functions(src_engine):
        old_id = el.get('ID', '')
        if old_id not in function_id_set:
            continue
        new_id = _next_id()
        id_map[old_id] = new_id
        selected_fns.append(el)

    for el in selected_fns:
        old_id = el.get('ID', '')
        new_id = id_map[old_id]
        new_el = copy.deepcopy(el)
        new_el.set('ID', new_id)

        # Rewrite any attribute or text that is a pure numeric ID in id_map
        _remap_ids_in_element(new_el, id_map)

        # Check for fixture references not in dst
        _warn_missing_fixtures(new_el, dst_fixture_names, warnings)

        name = new_el.get('Name', '')
        if name in dst_function_names:
            warnings.append(f'Function name already exists in destination: "{name}" (copied anyway)')
        dst_engine.append(new_el)
        dst_function_names.add(name)
        copied_functions += 1

    return {
        'ok': True,
        'copied': {
            'fixtures':  copied_fixtures,
            'groups':    copied_groups,
            'functions': copied_functions,
        },
        'warnings': warnings,
        'id_map': id_map,
    }


def _remap_ids_in_element(el: ET.Element, id_map: dict[str, str]):
    """
    Walk the element tree and remap all pure-numeric IDs found in
    common QXW attribute names and text content.
    """
    # Attributes that typically hold function / fixture IDs
    ID_ATTRS = {
        'Function', 'FunctionID', 'Fixture', 'FixtureID',
        'SceneID', 'ChaserID', 'ID',
    }
    _remap_el(el, id_map, ID_ATTRS)


def _remap_el(el: ET.Element, id_map: dict[str, str], id_attrs: set):
    for attr in list(el.attrib):
        val = el.get(attr, '')
        if attr in id_attrs and val in id_map:
            el.set(attr, id_map[val])
        elif attr in id_attrs and val.isdigit() and val in id_map:
            el.set(attr, id_map[val])
    # Text content that might be a plain numeric ID (e.g. Step/Function elements)
    if el.text and el.text.strip() in id_map:
        el.text = id_map[el.text.strip()]
    for child in el:
        _remap_el(child, id_map, id_attrs)


def _warn_missing_fixtures(fn_el: ET.Element, dst_fixture_names: set, warnings: list):
    """Flag if a Scene references fixture IDs not present in destination."""
    if fn_el.get('Type') != 'Scene':
        return
    for channel in fn_el.findall('FixtureVal'):
        fid = channel.get('Fixture', '')
        # If fid is purely numeric and not remapped it means it wasn't copied
        if fid.isdigit():
            # We can't check by name here since we only have destination names;
            # the route layer can do deeper checks if needed.
            # Emit a generic warning.
            warnings.append(
                f'Scene "{fn_el.get("Name", "?")}" references fixture ID {fid} '
                f'which may not exist in the destination.'
            )


# ── Export ────────────────────────────────────────────────────────────────────

def export_dst() -> tuple[str, bytes]:
    """Serialise the (modified) destination tree and return (filename, bytes)."""
    if not _dst['loaded']:
        raise RuntimeError('Destination QXW not loaded.')
    name = _dst['name'] or 'merged'
    # Suggest name: appended with _merged
    m = re.search(r'(\d+)$', name)
    if m:
        suggested = name[:m.start()] + str(int(m.group(1)) + 1).zfill(len(m.group(1))) + '.qxw'
    else:
        suggested = name + '_merged.qxw'
    xml_str   = ET.tostring(_dst['root'], encoding='unicode')
    xml_bytes = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xml_str).encode('utf-8')
    return suggested, xml_bytes
