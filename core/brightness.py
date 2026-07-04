"""
core/brightness.py
==================
Per-fixture brightness scaling for QLC+ workspaces.

Scales the Master Dimmer channel in every Scene function that references
a targeted fixture.  Colour channel ratios (R/G/B/W) are preserved.
"""

import copy
import os
import re
import xml.etree.ElementTree as ET

from core.workspace import _state, NS, QLC_NS_URI

# ── QXF fixture-definition namespace ─────────────────────────────────────────
_QXF_NS = 'http://www.qlcplus.org/FixtureDefinition'

# Presets whose values we scale as "master dimmer"
_DIMMER_PRESETS = frozenset({
    'IntensityMasterDimmer',
    'IntensityDimmer',
})

# Presets we treat as colour/intensity (informational only)
_COLOUR_PRESETS = frozenset({
    'IntensityRed', 'IntensityGreen', 'IntensityBlue', 'IntensityWhite',
    'IntensityAmber', 'IntensityCyan', 'IntensityMagenta',
    'IntensityYellow', 'IntensityUV', 'IntensityIndigo',
})


# =============================================================================
# QXF PARSING
# =============================================================================

def _qlc_fixture_dirs() -> list[str]:
    """Return a list of directories that may contain QXF fixture definition files."""
    dirs = []
    home = os.path.expanduser('~')
    # macOS app bundle
    dirs.append('/Applications/QLC+.app/Contents/Resources/Fixtures')
    # macOS / Linux user fixture dirs
    for sub in ('QLC+/Fixtures', 'QLC+/UserFixtures', '.qlcplus/fixtures'):
        dirs.append(os.path.join(home, sub))
    # Linux system install
    dirs.append('/usr/share/qlcplus/fixtures')
    # Current workspace folder (user can drop QXFs here)
    ws_path = _state.get('path') or _state.get('original_name') or ''
    if ws_path:
        dirs.append(os.path.dirname(ws_path))
    # Script directory (for development)
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return [d for d in dirs if d and os.path.isdir(d)]


def _find_qxf(manufacturer: str, model: str) -> str | None:
    """Search known directories for a QXF file matching the given fixture."""
    safe = lambda s: re.sub(r'[^\w\-. ]', '', s)
    candidates = [
        f'{safe(manufacturer)}-{safe(model)}.qxf',
        f'{safe(model)}.qxf',
    ]
    for search_dir in _qlc_fixture_dirs():
        for root_dir, _dirs, files in os.walk(search_dir):
            for fname in files:
                if not fname.lower().endswith('.qxf'):
                    continue
                for cand in candidates:
                    if fname.lower() == cand.lower():
                        return os.path.join(root_dir, fname)
    return None


def _parse_qxf(qxf_path: str, mode_name: str) -> dict:
    """
    Parse a QXF file and return a channel map for the given mode.

    Returns {offset (int, 0-indexed): {'name': str, 'preset': str}}
    or empty dict on failure.
    """
    try:
        root = ET.parse(qxf_path).getroot()
    except Exception:
        return {}

    # Build channel-name → preset map from top-level <Channel> elements
    ch_preset: dict[str, str] = {}
    for ch in root.findall(f'{{{_QXF_NS}}}Channel'):
        ch_preset[ch.get('Name', '')] = ch.get('Preset', '')

    # Find the target mode
    for mode in root.findall(f'{{{_QXF_NS}}}Mode'):
        if mode.get('Name', '') != mode_name:
            continue
        ch_els = mode.findall(f'{{{_QXF_NS}}}Channel')
        if not ch_els:
            return {}
        # Detect whether Numbers are 0-indexed or 1-indexed
        nums = [int(e.get('Number', '0')) for e in ch_els]
        index_offset = 1 if nums and min(nums) == 1 else 0
        result = {}
        for el in ch_els:
            offset = int(el.get('Number', '0')) - index_offset
            name   = el.text or ''
            result[offset] = {
                'name':   name,
                'preset': ch_preset.get(name, ''),
            }
        return result

    return {}


# =============================================================================
# PUBLIC API
# =============================================================================

# Cache: (manufacturer, model, mode) → (channel_map, qxf_found)
_ch_cache: dict = {}


def _get_channel_map(manufacturer: str, model: str, mode: str) -> tuple[dict, bool]:
    key = (manufacturer, model, mode)
    if key not in _ch_cache:
        qxf_path = _find_qxf(manufacturer, model)
        if qxf_path:
            ch_map = _parse_qxf(qxf_path, mode)
            _ch_cache[key] = (ch_map, bool(ch_map))
        else:
            _ch_cache[key] = ({}, False)
    return _ch_cache[key]


def invalidate_cache():
    """Clear the QXF channel-map cache (call after loading a new workspace)."""
    _ch_cache.clear()


def get_fixture_info() -> list:
    """
    Return brightness-relevant info for every fixture in the loaded workspace.

    Each entry::

        {
            'id':            str,   # fixture ID in QLC+
            'name':          str,
            'manufacturer':  str,
            'model':         str,
            'mode':          str,
            'channels':      int,
            'dimmer_offset': int|None,  # 0-indexed channel offset of Master Dimmer
            'color_offsets': [int],     # R/G/B/W etc. (informational)
            'qxf_found':     bool,
        }
    """
    if not _state.get('loaded'):
        return []

    root   = _state['qxw_root']
    engine = root.find('q:Engine', NS)
    result = []

    for fx in engine.findall('q:Fixture', NS):
        def txt(tag):
            el = fx.find(f'q:{tag}', NS)
            return el.text if el is not None else ''

        fid   = txt('ID')
        fname = txt('Name')
        mfr   = txt('Manufacturer')
        model = txt('Model')
        mode  = txt('Mode')
        nchan = int(txt('Channels') or 0)

        ch_map, qxf_found = _get_channel_map(mfr, model, mode)

        dimmer_offset  = None
        color_offsets  = []
        for offset, info in ch_map.items():
            p = info.get('preset', '')
            if p in _DIMMER_PRESETS:
                dimmer_offset = offset
            elif p in _COLOUR_PRESETS:
                color_offsets.append(offset)

        result.append({
            'id':            fid,
            'name':          fname,
            'manufacturer':  mfr,
            'model':         model,
            'mode':          mode,
            'channels':      nchan,
            'dimmer_offset': dimmer_offset,
            'color_offsets': sorted(color_offsets),
            'qxf_found':     qxf_found,
        })

    return result


def preview_scales(scales: dict) -> dict:
    """
    Count how many scenes and channel values would be affected by the given scales.

    scales: {fixture_id_str: float}
    Returns {'scenes': int, 'values': int, 'fixtures_active': int}
    """
    if not _state.get('loaded'):
        return {'scenes': 0, 'values': 0, 'fixtures_active': 0}

    root   = _state['qxw_root']
    engine = root.find('q:Engine', NS)
    fi_map = {fi['id']: fi for fi in get_fixture_info()}

    scenes_hit  = 0
    values_hit  = 0
    fids_active = set()

    for func in engine.findall('q:Function', NS):
        if func.get('Type') != 'Scene':
            continue
        scene_touched = False
        for fv in func.findall('q:FixtureVal', NS):
            fid = fv.get('ID', '')
            if fid not in scales or abs(scales[fid] - 1.0) < 0.001:
                continue
            fi = fi_map.get(fid, {})
            doff = fi.get('dimmer_offset')
            if doff is None:
                continue
            raw = (fv.text or '').strip()
            if not raw:
                continue
            try:
                pairs = raw.split(',')
                for i in range(0, len(pairs) - 1, 2):
                    if int(pairs[i]) == doff:
                        values_hit  += 1
                        fids_active.add(fid)
                        scene_touched = True
            except (ValueError, IndexError):
                continue
        if scene_touched:
            scenes_hit += 1

    return {
        'scenes':          scenes_hit,
        'values':          values_hit,
        'fixtures_active': len(fids_active),
    }


def apply_brightness_scales(
    scales: dict,
    manual_dimmer_offsets: dict | None = None,
) -> tuple:
    """
    Apply per-fixture brightness scales to a deep copy of the loaded workspace.

    scales:                {fixture_id_str: float}  (1.0 = no change)
    manual_dimmer_offsets: {fixture_id_str: int}    override dimmer offset
                           for fixtures whose QXF was not found.

    Returns (suggested_filename: str, xml_bytes: bytes, stats: dict)
    """
    if not _state.get('loaded') or not _state['qxw_root']:
        raise RuntimeError('No workspace loaded.')
    if not scales:
        raise ValueError('No brightness scales provided.')

    root_copy = copy.deepcopy(_state['qxw_root'])
    engine    = root_copy.find('q:Engine', NS)

    fi_map = {fi['id']: fi for fi in get_fixture_info()}
    manual  = manual_dimmer_offsets or {}

    scenes_modified = 0
    values_changed  = 0

    for func in engine.findall('q:Function', NS):
        if func.get('Type') != 'Scene':
            continue
        scene_touched = False

        for fv in func.findall('q:FixtureVal', NS):
            fid   = fv.get('ID', '')
            scale = scales.get(fid)
            if scale is None or abs(scale - 1.0) < 0.001:
                continue

            fi   = fi_map.get(fid, {})
            doff = fi.get('dimmer_offset')
            if doff is None and fid in manual:
                doff = manual[fid]
            if doff is None:
                continue  # skip — unknown channel layout

            raw = (fv.text or '').strip()
            if not raw:
                continue

            try:
                parts = [int(x) for x in raw.split(',')]
            except ValueError:
                continue
            changed = False
            for i in range(0, len(parts) - 1, 2):
                if parts[i] == doff:
                    old_val = parts[i + 1]
                    new_val = max(0, min(255, round(old_val * scale)))
                    if new_val != old_val:
                        parts[i + 1] = new_val
                        values_changed += 1
                        changed = True

            if changed:
                fv.text = ','.join(str(x) for x in parts)
                scene_touched = True

        if scene_touched:
            scenes_modified += 1

    # Build suggested output filename
    orig = _state.get('original_name')
    src  = orig or _state.get('path') or 'workspace.qxw'
    obn  = os.path.splitext(os.path.basename(src))[0]
    m    = re.search(r'(\d+)$', obn)
    bn   = (
        obn[:m.start()] + str(int(m.group(1)) + 1).zfill(len(m.group(1)))
        if m else f'{obn}_BRIGHTNESS'
    )
    suggested_filename = bn + '.qxw'

    xb  = ET.tostring(root_copy, encoding='utf-8').decode('utf-8')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xb
    return suggested_filename, xml.encode('utf-8'), {
        'scenes_modified': scenes_modified,
        'values_changed':  values_changed,
    }
