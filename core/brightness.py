"""
core/brightness.py
==================
Per-fixture brightness scaling for QLC+ workspaces.

Scales the Master Dimmer channel in every Scene function that references
a targeted fixture.  Colour channel ratios (R/G/B/W) are preserved.
"""

import copy
import json
import os
import re
import tempfile
import urllib.request
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

# GitHub repository for QLC+ fixture definitions
_GITHUB_API  = 'https://api.github.com/repos/mcallegari/qlcplus/contents/resources/fixtures'
_GITHUB_RAW  = 'https://raw.githubusercontent.com/mcallegari/qlcplus/master/resources/fixtures'
_HTTP_HEADERS = {'User-Agent': 'qlc-swiss-knife/1.0'}


# =============================================================================
# NAME NORMALISATION
# =============================================================================

def _norm(s: str) -> str:
    """Normalise a name for fuzzy filename matching.

    Lowercases, then collapses any run of non-alphanumeric characters into a
    single hyphen.  This makes 'LED 4C-12 Silent Slim Spot' and
    'LED-4C-12-Silent-Slim-Spot' identical after normalisation.
    """
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# =============================================================================
# QXF PARSING
# =============================================================================

def _qlc_fixture_dirs() -> list[str]:
    """Return a list of directories that may contain QXF fixture definition files."""
    dirs = []
    home = os.path.expanduser('~')

    # macOS app bundle (most common install location)
    dirs.append('/Applications/QLC+.app/Contents/Resources/Fixtures')

    # macOS / Linux user fixture dirs
    for sub in ('QLC+/Fixtures', 'QLC+/UserFixtures', '.qlcplus/fixtures'):
        dirs.append(os.path.join(home, sub))

    # Linux system install
    dirs.append('/usr/share/qlcplus/fixtures')

    # Windows default install paths
    dirs.append(r'C:\QLC+\Fixtures')
    dirs.append(os.path.join(os.environ.get('PROGRAMFILES', ''), 'QLC+', 'Fixtures'))
    dirs.append(os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'QLC+', 'Fixtures'))
    # Windows user fixtures
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        dirs.append(os.path.join(appdata, 'QLC+', 'Fixtures'))

    # Current workspace folder (user can drop QXFs here)
    ws_path = _state.get('path') or _state.get('original_name') or ''
    if ws_path:
        dirs.append(os.path.dirname(ws_path))

    # Script directory (development / portable use)
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    return [d for d in dict.fromkeys(dirs) if d and os.path.isdir(d)]


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

    # Find the target mode (try exact match, then case-insensitive)
    target_modes = [
        m for m in root.findall(f'{{{_QXF_NS}}}Mode')
        if m.get('Name', '') == mode_name
    ]
    if not target_modes:
        target_modes = [
            m for m in root.findall(f'{{{_QXF_NS}}}Mode')
            if m.get('Name', '').lower() == mode_name.lower()
        ]
    if not target_modes:
        # Fall back to the first mode in the file
        target_modes = root.findall(f'{{{_QXF_NS}}}Mode')

    for mode in target_modes:
        ch_els = mode.findall(f'{{{_QXF_NS}}}Channel')
        if not ch_els:
            continue
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
# CONTENT-BASED QXF INDEX  (phase-2 fallback for filename mismatches)
# =============================================================================

# Maps (manufacturer, model) in both raw and normalised form → absolute QXF path.
# Built lazily, per-directory, so large installs are not scanned unless needed.
_qxf_content_index: dict  = {}   # (mfr, model) → path  (both raw & norm keys)
_qxf_indexed_dirs:  set   = set()


def _read_qxf_identity(path: str) -> tuple[str, str]:
    """Quick-parse the first 3 KB of a QXF to extract Manufacturer and Model."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(3072).decode('utf-8', errors='ignore')
    except OSError:
        return '', ''
    mfr   = (re.search(r'<Manufacturer>(.*?)</Manufacturer>', chunk) or [None, ''])[1].strip()
    model = (re.search(r'<Model>(.*?)</Model>',               chunk) or [None, ''])[1].strip()
    return mfr, model


def _build_content_index(search_dirs: list) -> None:
    """Walk directories not yet indexed and populate _qxf_content_index."""
    for d in search_dirs:
        if d in _qxf_indexed_dirs:
            continue
        _qxf_indexed_dirs.add(d)
        for root_dir, _dirs, files in os.walk(d):
            for fname in files:
                if not fname.lower().endswith('.qxf'):
                    continue
                path = os.path.join(root_dir, fname)
                mfr, model = _read_qxf_identity(path)
                if mfr and model:
                    # Store both exact and normalised keys
                    _qxf_content_index[(mfr, model)]               = path
                    _qxf_content_index[(_norm(mfr), _norm(model))] = path


# User-forced QXF assignments: (mfr_norm, model_norm) → absolute QXF path.
# Takes priority over all automatic detection.
_forced_qxf: dict = {}


def force_qxf_for_fixture(manufacturer: str, model: str, qxf_path: str) -> None:
    """Explicitly assign a QXF file to a fixture group, bypassing all auto-detection.

    The mapping is keyed by normalised (manufacturer, model) and is checked
    first in every subsequent _find_qxf call.  Clears the channel cache so
    get_fixture_info() immediately reflects the new assignment.
    """
    _forced_qxf[(_norm(manufacturer), _norm(model))] = qxf_path
    invalidate_cache()


def _find_qxf(manufacturer: str, model: str) -> str | None:
    """Search for a QXF file matching the given fixture.

    Priority order:
      0. User-forced assignment (_forced_qxf) — always wins.
      1. Fast filename normalisation — zero overhead for well-named files.
      2. Content-based fallback — reads <Manufacturer>/<Model> from the
         first 3 KB of each QXF; handles filenames that diverge from the
         internal model declaration.

    Returns the absolute path if found, or None.
    """
    # ── Phase 0: user-forced assignment ──────────────────────────────────────
    forced = _forced_qxf.get((_norm(manufacturer), _norm(model)))
    if forced and os.path.isfile(forced):
        return forced

    dirs    = _qlc_fixture_dirs()
    targets = {_norm(f'{manufacturer}-{model}'), _norm(model)}

    # ── Phase 1: filename normalisation ──────────────────────────────────────
    for search_dir in dirs:
        for root_dir, _dirs, files in os.walk(search_dir):
            for fname in files:
                if not fname.lower().endswith('.qxf'):
                    continue
                if _norm(fname[:-4]) in targets:
                    return os.path.join(root_dir, fname)

    # ── Phase 2: content-based index ─────────────────────────────────────────
    _build_content_index(dirs)
    for key in ((manufacturer, model), (_norm(manufacturer), _norm(model))):
        path = _qxf_content_index.get(key)
        if path:
            return path

    return None


# =============================================================================
# PUBLIC API
# =============================================================================

# Cache: (manufacturer, model, mode) → (channel_map, qxf_found, qxf_path)
_ch_cache: dict = {}


def _get_channel_map(manufacturer: str, model: str, mode: str) -> tuple[dict, bool, str]:
    """Return (channel_map, qxf_found, qxf_path)."""
    key = (manufacturer, model, mode)
    if key not in _ch_cache:
        qxf_path = _find_qxf(manufacturer, model)
        if qxf_path:
            ch_map = _parse_qxf(qxf_path, mode)
            _ch_cache[key] = (ch_map, bool(ch_map), qxf_path)
        else:
            _ch_cache[key] = ({}, False, '')
    return _ch_cache[key]


def invalidate_cache(reset_forced: bool = False):
    """Clear the QXF channel-map cache.

    reset_forced=True also clears user-forced QXF assignments (use when a
    new workspace is loaded; leave False on simple QXF uploads so the user's
    manual picks survive).
    """
    _ch_cache.clear()
    _qxf_content_index.clear()
    _qxf_indexed_dirs.clear()
    if reset_forced:
        _forced_qxf.clear()


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
            'qxf_path':      str,       # absolute path to QXF, or ''
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

        ch_map, qxf_found, qxf_path = _get_channel_map(mfr, model, mode)

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
            'qxf_path':      qxf_path,
        })

    return result


# =============================================================================
# LOCAL SCAN
# =============================================================================

def scan_local_fixtures() -> dict:
    """
    Scan all standard QLC+ fixture directories and report what was found.

    Forces a cache invalidation so re-matched fixtures are detected immediately.

    Returns::

        {
            'dirs':            [{'path': str, 'exists': bool, 'qxf_count': int}],
            'total_qxf_files': int,
            'fixtures_matched': [{'fixture_name': str, 'model': str, 'qxf_path': str}],
            'fixtures_missing': [{'fixture_name': str, 'manufacturer': str, 'model': str}],
        }
    """
    dirs_checked = []
    total_found  = 0

    for d in _qlc_fixture_dirs():
        count = 0
        for _, _, files in os.walk(d):
            count += sum(1 for f in files if f.lower().endswith('.qxf'))
        dirs_checked.append({'path': d, 'exists': True, 'qxf_count': count})
        total_found += count

    # Re-detect with fresh cache
    invalidate_cache()
    matched = []
    missing = []
    for fx in get_fixture_info():
        if fx['qxf_found']:
            matched.append({
                'fixture_name': fx['name'],
                'model':        fx['model'],
                'qxf_path':     fx['qxf_path'],
            })
        else:
            missing.append({
                'fixture_name': fx['name'],
                'manufacturer': fx['manufacturer'],
                'model':        fx['model'],
            })

    return {
        'dirs':             dirs_checked,
        'total_qxf_files':  total_found,
        'fixtures_matched': matched,
        'fixtures_missing': missing,
    }


# =============================================================================
# GITHUB FETCH  (internet access — always flagged to caller)
# =============================================================================

def _gh_get(url: str) -> list | dict:
    """GET from GitHub API, return parsed JSON.  Raises on error."""
    req = urllib.request.Request(url, headers=_HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())


def fetch_fixtures_from_github(missing_fixtures: list, save_dir: str) -> dict:
    """
    Try to download QXF definitions from the official QLC+ GitHub repository
    for fixtures that have no local QXF file.

    ⚠  This function makes outbound HTTP requests to github.com and
       raw.githubusercontent.com.  Always disclose this to the user before
       calling.

    missing_fixtures: [{'manufacturer': str, 'model': str, 'fixture_name': str}, ...]
    save_dir:         directory where downloaded QXF files are written

    Returns::

        {
            'source':     'https://github.com/mcallegari/qlcplus',
            'downloaded': [{'fixture_name', 'filename', 'manufacturer', 'model', 'url'}],
            'not_found':  [{'fixture_name', 'manufacturer', 'model', 'reason'}],
            'errors':     [str],
        }
    """
    downloaded = []
    not_found  = []
    errors     = []

    # Step 1 — fetch top-level manufacturer directory list
    try:
        top_entries = _gh_get(_GITHUB_API)
    except Exception as e:
        return {
            'source':     _GITHUB_API,
            'downloaded': [],
            'not_found':  [],
            'errors':     [f'Cannot reach GitHub API: {e}'],
        }

    mfr_map = {_norm(e['name']): e['name']
               for e in top_entries if e.get('type') == 'dir'}

    # Deduplicate by (manufacturer, model) so we don't re-download
    seen: set = set()
    deduped = []
    for fx in missing_fixtures:
        key = (_norm(fx['manufacturer']), _norm(fx['model']))
        if key not in seen:
            seen.add(key)
            deduped.append(fx)

    for fx in deduped:
        mfr   = fx['manufacturer']
        model = fx['model']
        fname = fx.get('fixture_name', f'{mfr} {model}')

        # ── Find manufacturer directory ───────────────────────────────────
        mfr_norm   = _norm(mfr)
        gh_mfr_dir = mfr_map.get(mfr_norm)
        if not gh_mfr_dir:
            # Partial match: accept if one fully contains the other
            for k, v in mfr_map.items():
                if mfr_norm in k or k in mfr_norm:
                    gh_mfr_dir = v
                    break

        if not gh_mfr_dir:
            not_found.append({
                'fixture_name': fname,
                'manufacturer': mfr,
                'model':        model,
                'reason':       'Manufacturer directory not found on GitHub',
            })
            continue

        # ── List files in that directory ──────────────────────────────────
        try:
            mfr_entries = _gh_get(f'{_GITHUB_API}/{gh_mfr_dir}')
        except Exception as e:
            errors.append(f'{mfr}/{model}: listing directory failed — {e}')
            continue

        # ── Find best matching QXF ────────────────────────────────────────
        targets = {_norm(f'{mfr}-{model}'), _norm(model)}
        matched_entry = None
        for entry in mfr_entries:
            n = entry.get('name', '')
            if n.lower().endswith('.qxf') and _norm(n[:-4]) in targets:
                matched_entry = entry
                break

        if not matched_entry:
            not_found.append({
                'fixture_name': fname,
                'manufacturer': mfr,
                'model':        model,
                'reason':       f'No matching QXF found in {gh_mfr_dir}/ on GitHub',
            })
            continue

        # ── Download ──────────────────────────────────────────────────────
        raw_url = f'{_GITHUB_RAW}/{gh_mfr_dir}/{matched_entry["name"]}'
        dest    = os.path.join(save_dir, matched_entry['name'])
        try:
            req = urllib.request.Request(raw_url, headers=_HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            with open(dest, 'wb') as f:
                f.write(data)
            downloaded.append({
                'fixture_name': fname,
                'manufacturer': mfr,
                'model':        model,
                'filename':     matched_entry['name'],
                'url':          raw_url,
            })
        except Exception as e:
            errors.append(f'{mfr}/{model}: download failed — {e}')

    if downloaded:
        invalidate_cache()

    return {
        'source':     'https://github.com/mcallegari/qlcplus',
        'downloaded': downloaded,
        'not_found':  not_found,
        'errors':     errors,
    }


# =============================================================================
# PREVIEW / APPLY
# =============================================================================

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
            fi   = fi_map.get(fid, {})
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
