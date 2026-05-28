/**
 * merger.js — QXW Merger tab
 *
 * Two-column browser: Source (left) | Destination (right)
 * User selects fixtures / groups / functions from source,
 * clicks "Copy → Destination", then exports the merged QXW.
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

let _srcLoaded = false;
let _dstLoaded = false;
let _srcName   = '';
let _dstName   = '';

// Lists fetched from API
let _srcFixtures  = [];
let _srcGroups    = [];
let _srcFunctions = [];
let _dstFixtures  = [];
let _dstFunctions = [];

// Active category tab: 'fixtures' | 'groups' | 'functions'
let _activeCategory = 'functions';

// Search/filter strings
let _srcSearch = '';
let _fnTypeFilter = '';

// ── Init ──────────────────────────────────────────────────────────────────────

async function mergerInit() {
  await _refreshState();
}

// ── Status helpers ─────────────────────────────────────────────────────────────

function _setMergerStatus(msg, type = 'info') {
  const el = document.getElementById('merger-status');
  if (!el) return;
  el.textContent = msg;
  el.className   = `status-bar status-${type}`;
}

// ── State refresh ─────────────────────────────────────────────────────────────

async function _refreshState() {
  try {
    const r = await fetch('/api/merger/state');
    if (!r.ok) return;
    const s = await r.json();
    _srcLoaded = s.src_loaded;
    _dstLoaded = s.dst_loaded;
    _srcName   = s.src_name || '';
    _dstName   = s.dst_name || '';
    _updatePanelHeaders();
    if (_srcLoaded) await _fetchSrcElements();
    if (_dstLoaded) await _fetchDstElements();
    _renderAll();
  } catch (e) {
    _setMergerStatus('Error refreshing state: ' + e.message, 'error');
  }
}

function _updatePanelHeaders() {
  const srcH = document.getElementById('merger-src-name');
  const dstH = document.getElementById('merger-dst-name');
  if (srcH) srcH.textContent = _srcLoaded ? _srcName : '— not loaded —';
  if (dstH) dstH.textContent = _dstLoaded ? _dstName : '— not loaded —';

  // Enable/disable action buttons
  const copyBtn   = document.getElementById('merger-copy-btn');
  const exportBtn = document.getElementById('merger-export-btn');
  if (copyBtn)   copyBtn.disabled   = !(_srcLoaded && _dstLoaded);
  if (exportBtn) exportBtn.disabled = !_dstLoaded;
}

// ── Load src / dst ────────────────────────────────────────────────────────────

async function mergerLoadSrc() {
  const inp = document.getElementById('merger-src-path');
  const path = (inp?.value || '').trim();
  if (!path) { _setMergerStatus('Enter the source .qxw file path.', 'error'); return; }
  _setMergerStatus('Loading source…', 'info');
  try {
    const r = await fetch('/api/merger/src/load', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const d = await r.json();
    if (!r.ok) { _setMergerStatus('Source load error: ' + d.error, 'error'); return; }
    _srcLoaded = true;
    _srcName   = d.name;
    _setMergerStatus(`Source loaded: ${d.name}  (${_summaryText(d.summary)})`, 'ok');
    await _fetchSrcElements();
    _updatePanelHeaders();
    _renderAll();
  } catch (e) {
    _setMergerStatus('Network error: ' + e.message, 'error');
  }
}

async function mergerLoadDst() {
  const inp = document.getElementById('merger-dst-path');
  const path = (inp?.value || '').trim();
  if (!path) { _setMergerStatus('Enter the destination .qxw file path.', 'error'); return; }
  _setMergerStatus('Loading destination…', 'info');
  try {
    const r = await fetch('/api/merger/dst/load', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const d = await r.json();
    if (!r.ok) { _setMergerStatus('Destination load error: ' + d.error, 'error'); return; }
    _dstLoaded = true;
    _dstName   = d.name;
    _setMergerStatus(`Destination loaded: ${d.name}  (${_summaryText(d.summary)})`, 'ok');
    await _fetchDstElements();
    _updatePanelHeaders();
    _renderAll();
  } catch (e) {
    _setMergerStatus('Network error: ' + e.message, 'error');
  }
}

function _summaryText(s) {
  if (!s) return '';
  return `${s.fixtures || 0} fixtures · ${s.groups || 0} groups · ${s.functions || 0} functions`;
}

// ── Fetch elements ────────────────────────────────────────────────────────────

async function _fetchSrcElements() {
  const [fxR, grR, fnR] = await Promise.all([
    fetch('/api/merger/src/fixtures'),
    fetch('/api/merger/src/groups'),
    fetch('/api/merger/src/functions'),
  ]);
  _srcFixtures  = fxR.ok  ? await fxR.json()  : [];
  _srcGroups    = grR.ok  ? await grR.json()  : [];
  _srcFunctions = fnR.ok  ? await fnR.json()  : [];
}

async function _fetchDstElements() {
  const [fxR, fnR] = await Promise.all([
    fetch('/api/merger/dst/fixtures'),
    fetch('/api/merger/dst/functions'),
  ]);
  _dstFixtures  = fxR.ok ? await fxR.json() : [];
  _dstFunctions = fnR.ok ? await fnR.json() : [];
}

// ── Render ────────────────────────────────────────────────────────────────────

function _renderAll() {
  _renderSrcList();
  _renderDstList();
}

function mergerSetCategory(cat) {
  _activeCategory = cat;
  // Update tab buttons
  ['fixtures', 'groups', 'functions'].forEach(c => {
    const btn = document.getElementById(`merger-cat-${c}`);
    if (btn) btn.classList.toggle('active', c === cat);
  });
  _renderAll();
}

function mergerSrcSearch(val) {
  _srcSearch = (val || '').toLowerCase();
  _renderSrcList();
}

function mergerFnTypeFilter(val) {
  _fnTypeFilter = val || '';
  _renderSrcList();
}

function _matchesSearch(name) {
  return !_srcSearch || name.toLowerCase().includes(_srcSearch);
}

function _renderSrcList() {
  const container = document.getElementById('merger-src-list');
  if (!container) return;

  if (!_srcLoaded) {
    container.innerHTML = '<div class="merger-placeholder">Load a source .qxw file above</div>';
    return;
  }

  let items = [];

  if (_activeCategory === 'fixtures') {
    items = _srcFixtures
      .filter(f => _matchesSearch(f.name))
      .map(f => ({
        id: f.id, label: f.name,
        sub: `U${f.universe} · Ch${f.address} · ${f.channels}ch · ${f.model}`,
        type: 'fixture',
      }));
  } else if (_activeCategory === 'groups') {
    items = _srcGroups
      .filter(g => _matchesSearch(g.name))
      .map(g => ({
        id: g.id, label: g.name,
        sub: `${g.members?.length || 0} members`,
        type: 'group',
      }));
  } else {
    items = _srcFunctions
      .filter(f => _matchesSearch(f.name) && (!_fnTypeFilter || f.type === _fnTypeFilter))
      .map(f => ({
        id: f.id, label: f.name,
        sub: f.type,
        type: 'function',
      }));
  }

  if (!items.length) {
    container.innerHTML = '<div class="merger-placeholder">No items match</div>';
    return;
  }

  // Check which names clash in destination
  const dstFxNames = new Set(_dstFixtures.map(f => f.name));
  const dstFnNames = new Set(_dstFunctions.map(f => f.name));

  container.innerHTML = items.map(item => {
    const clashes = (item.type === 'fixture' && dstFxNames.has(item.label))
                 || (item.type === 'function' && dstFnNames.has(item.label));
    const clashHtml = clashes ? ' <span class="merger-clash" title="Name exists in destination">⚠</span>' : '';
    return `
      <label class="merger-row" data-type="${item.type}" data-id="${item.id}">
        <input type="checkbox" class="merger-check" value="${item.id}" data-type="${item.type}">
        <span class="merger-row-label">${_esc(item.label)}${clashHtml}</span>
        <span class="merger-row-sub">${_esc(item.sub)}</span>
      </label>`;
  }).join('');
}

function _renderDstList() {
  const container = document.getElementById('merger-dst-list');
  if (!container) return;

  if (!_dstLoaded) {
    container.innerHTML = '<div class="merger-placeholder">Load a destination .qxw file above</div>';
    return;
  }

  let items = [];
  if (_activeCategory === 'fixtures') {
    items = _dstFixtures.map(f => ({
      label: f.name,
      sub: `U${f.universe} · Ch${f.address} · ${f.channels}ch`,
    }));
  } else if (_activeCategory === 'groups') {
    items = [];   // no groups list endpoint for dst (can be added later)
  } else {
    items = _dstFunctions.map(f => ({
      label: f.name,
      sub: f.type,
    }));
  }

  if (!items.length) {
    container.innerHTML = '<div class="merger-placeholder">Empty</div>';
    return;
  }

  container.innerHTML = items.map(item =>
    `<div class="merger-row merger-row-dst">
       <span class="merger-row-label">${_esc(item.label)}</span>
       <span class="merger-row-sub">${_esc(item.sub)}</span>
     </div>`
  ).join('');
}

// ── Select all / none ─────────────────────────────────────────────────────────

function mergerSelectAll() {
  document.querySelectorAll('#merger-src-list .merger-check').forEach(cb => cb.checked = true);
}

function mergerSelectNone() {
  document.querySelectorAll('#merger-src-list .merger-check').forEach(cb => cb.checked = false);
}

// ── Copy ──────────────────────────────────────────────────────────────────────

async function mergerCopy() {
  const checks = Array.from(document.querySelectorAll('#merger-src-list .merger-check:checked'));
  if (!checks.length) {
    _setMergerStatus('Nothing selected — tick items in the source list first.', 'error');
    return;
  }

  const fixtureIds  = checks.filter(c => c.dataset.type === 'fixture') .map(c => c.value);
  const groupIds    = checks.filter(c => c.dataset.type === 'group')   .map(c => c.value);
  const functionIds = checks.filter(c => c.dataset.type === 'function').map(c => c.value);

  _setMergerStatus('Copying…', 'info');
  try {
    const r = await fetch('/api/merger/copy', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixture_ids: fixtureIds, group_ids: groupIds, function_ids: functionIds }),
    });
    const d = await r.json();
    if (!r.ok) { _setMergerStatus('Copy error: ' + d.error, 'error'); return; }

    const c = d.copied;
    let msg = `✓ Copied: ${c.fixtures} fixture(s), ${c.groups} group(s), ${c.functions} function(s).`;
    if (d.warnings?.length) {
      msg += `  ⚠ ${d.warnings.length} warning(s) — see console.`;
      console.warn('Merger warnings:', d.warnings);
    }
    _setMergerStatus(msg, 'ok');

    // Refresh destination lists
    await _fetchDstElements();
    _renderDstList();
  } catch (e) {
    _setMergerStatus('Network error: ' + e.message, 'error');
  }
}

// ── Export ────────────────────────────────────────────────────────────────────

async function mergerExport() {
  _setMergerStatus('Preparing export…', 'info');
  try {
    const resp = await fetch('/api/merger/export', { method: 'POST' });
    if (!resp.ok) {
      const d = await resp.json();
      _setMergerStatus('Export error: ' + d.error, 'error');
      return;
    }
    const blob          = await resp.blob();
    const suggestedName = resp.headers.get('X-Suggested-Filename') || 'merged.qxw';

    if (typeof window.showSaveFilePicker === 'function') {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          startIn: 'documents',
          types: [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        _setMergerStatus(`✓ Saved: ${handle.name}`, 'ok');
        return;
      } catch (e) {
        if (e.name === 'AbortError') return;
      }
    }
    // Fallback
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href = url; a.download = suggestedName;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 3000);
    _setMergerStatus(`✓ Downloaded: ${suggestedName}`, 'ok');
  } catch (e) {
    _setMergerStatus('Network error: ' + e.message, 'error');
  }
}

// ── Utilities ──────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
