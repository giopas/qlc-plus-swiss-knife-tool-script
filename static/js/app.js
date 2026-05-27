/* =============================================================================
   QLC+ Swiss Knife — Web UI  app.js
   =============================================================================
   Single-page application logic:
     - Tab / sub-tab switching
     - Workspace loading (path or file upload, drag-and-drop)
     - ID Browser: Functions + VC Widgets tables (Grid.js)
     - Client-side CSV export
   ============================================================================= */

'use strict';

// ── Cached data (module-level, re-fetched on every workspace load) ────────────
let _fnData  = [];   // raw functions array from /api/functions
let _vcData  = [];   // raw vc-widgets array from /api/vc-widgets
let _fnGrid  = null; // Grid.js instance for Functions table
let _vcGrid  = null; // Grid.js instance for VC Widgets table

// ── Type → emoji map ──────────────────────────────────────────────────────────
const TYPE_ICON = {
  Chaser: '🔄', Scene: '🎬', Sequence: '📋', EFX: '✨',
  Script: '📝', Show: '🎭', Audio: '🎵', Collection: '📦',
  RGBMatrix: '🌈', Button: '🔘', Slider: '🎚', Knob: '🔩',
  Frame: '🖼', SoloFrame: '⬜', CueList: '📑', Label: '🏷',
  XYPad: '🕹', Clock: '🕐', VUMeter: '📊',
  AudioTrigger: '🔊', Animation: '🎞', SpeedDial: '⏩',
};
const icon = t => TYPE_ICON[t] || '◻';

// =============================================================================
// TAB NAVIGATION
// =============================================================================

function showTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === `tab-${tabId}`);
  });

  // Lazy-load tab data on first visit (each module guards with its own flag)
  switch (tabId) {
    case 'id-browser': _ensureIdBrowserLoaded(); break;
    case 'setlist':    ensureSetlistLoaded();     break;
    case 'dictionary': ensureDictionaryLoaded();  break;
    case 'checklist':  ensureChecklistLoaded();   break;
    case 'triggers':   ensureTriggersLoaded();    break;
    case 'fixture':    ensureFixturesLoaded();    break;
  }
}

function showSubtab(subtabId) {
  document.querySelectorAll('.subtab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.subtab === subtabId);
  });
  document.querySelectorAll('.subtab-panel').forEach(p => {
    p.classList.toggle('active', p.id === `subtab-${subtabId}`);
  });
}

// =============================================================================
// WORKSPACE LOADING
// =============================================================================

async function loadFromPath() {
  const path = document.getElementById('path-input').value.trim();
  if (!path) { setStatus('Paste a .qxw file path first.', 'warn'); return; }
  await _doLoad({ method: 'POST', headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ path }) });
}

function loadFromInput(input) {
  if (!input.files.length) return;
  const form = new FormData();
  form.append('file', input.files[0]);
  _doLoad({ method: 'POST', body: form });
}

async function reloadWorkspace() {
  await _apiJson('/api/reload', { method: 'POST' });
  await _refreshAfterLoad();
}

async function _doLoad(fetchOpts) {
  setStatus('Loading…');
  try {
    const res  = await fetch('/api/load', fetchOpts);
    const data = await res.json();
    if (!res.ok || data.error) {
      const msg = data.error || 'Load failed.';
      setStatus(msg, 'error');
      // Also log to console so the terminal/devtools shows what went wrong
      console.error('[QLC Swiss Knife] Load error:', msg);
      return;
    }
    _updateHeader(data);
    _invalidateAllTabs();
    setStatus(`Loaded: ${data.path ? data.path.split(/[\\/]/).pop() : 'workspace'}`);

    // If ID Browser tab is already open, refresh it
    if (document.querySelector('.tab-btn.active')?.dataset.tab === 'id-browser') {
      _ensureIdBrowserLoaded();
    }
  } catch (e) {
    setStatus('Network error: ' + e.message, 'error');
  }
}

async function _refreshAfterLoad() {
  const data = await _apiJson('/api/status');
  _updateHeader(data);
  _invalidateAllTabs();
}

// ── Invalidate all tab caches after a workspace load ─────────────────────────
function _invalidateAllTabs() {
  _invalidateIdBrowser();
  if (typeof invalidateSetlist    === 'function') invalidateSetlist();
  if (typeof invalidateDictionary === 'function') invalidateDictionary();
  if (typeof invalidateChecklist  === 'function') invalidateChecklist();
  if (typeof invalidateTriggers   === 'function') invalidateTriggers();
  if (typeof invalidateFixtures   === 'function') invalidateFixtures();
  // Re-load whichever tab is currently visible
  const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
  if (activeTab) showTab(activeTab);
}

function _updateHeader(state) {
  const nameEl    = document.getElementById('ws-name');
  const reloadBtn = document.getElementById('btn-reload');
  const pathInput = document.getElementById('path-input');

  if (state.loaded) {
    // Path mode: show path in input and enable Reload
    if (state.path) {
      const name = state.path.split(/[\\/]/).pop();
      nameEl.textContent  = name;
      nameEl.className    = '';
      pathInput.value     = state.path;
      reloadBtn.disabled  = false;

    // Upload mode: show original filename, leave path input alone, disable Reload
    } else if (state.original_name) {
      nameEl.textContent = state.original_name + '  (uploaded)';
      nameEl.className   = '';
      reloadBtn.disabled = true;
    }
  } else {
    nameEl.textContent = 'No workspace loaded';
    nameEl.className   = 'ws-unloaded';
    reloadBtn.disabled = true;
  }

  document.getElementById('status-counts').textContent =
    `Functions: ${state.func_count ?? '—'}  |  ` +
    `Fixtures: ${state.fixture_count ?? '—'}  |  ` +
    `VC Widgets: ${state.vc_widget_count ?? '—'}`;

  // Sync output directory field from server state
  const outdirInput  = document.getElementById('outdir-input');
  const outdirStatus = document.getElementById('outdir-status');
  if (outdirInput && state.output_dir !== undefined) {
    outdirInput.value = state.output_dir || '';
    if (outdirStatus) outdirStatus.textContent = state.output_dir ? '✓ custom' : '';
  }
}

// =============================================================================
// OUTPUT DIRECTORY SELECTOR
// =============================================================================

async function applyOutputDir() {
  const input = document.getElementById('outdir-input');
  if (!input) return;
  const path = input.value.trim();
  const res = await _apiJson('/api/output-dir', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  const statusEl = document.getElementById('outdir-status');
  if (res.error) {
    setStatus('Output dir error: ' + res.error, 'error');
    if (statusEl) statusEl.textContent = '✗ error';
    return;
  }
  if (statusEl) statusEl.textContent = path ? '✓ custom' : '';
  setStatus(path ? `Output dir set → ${path}` : 'Output dir reset to default.', 'ok');
}

async function clearOutputDir() {
  const input = document.getElementById('outdir-input');
  if (input) input.value = '';
  const res = await _apiJson('/api/output-dir', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: '' }),
  });
  const statusEl = document.getElementById('outdir-status');
  if (res.error) {
    setStatus('Reset error: ' + res.error, 'error');
    return;
  }
  if (statusEl) statusEl.textContent = '';
  setStatus('Output dir reset to default.', 'ok');
}

// =============================================================================
// ID BROWSER — Functions
// =============================================================================

const FN_COLS = [
  { id: 'id',       name: 'ID',            width: '70px' },
  { id: 'type_icon',name: '',              width: '28px', sort: false },
  { id: 'type',     name: 'Type',          width: '110px' },
  { id: 'name',     name: 'Name',          width: '35%' },
  { id: 'contains', name: 'Contains / Steps' },
];

function _buildFnRows(data) {
  return data.map(f => [
    f.id,
    icon(f.type),
    _badge(f.type),
    f.name,
    f.contains || '—',
  ]);
}

async function _loadFunctions() {
  const res  = await fetch('/api/functions');
  if (!res.ok) { setStatus('Could not load functions.', 'error'); return; }
  _fnData = await res.json();
  _renderFnTable(_fnData);
}

// ── Dynamic page-limit helper ─────────────────────────────────────────────────
// Compute how many rows fit in the wrapper without overflow.
// Grid.js row ≈ 36 px · header ≈ 36 px · pagination footer ≈ 44 px.
function _pageLimit(wrapId) {
  const el = document.getElementById(wrapId);
  const h  = el ? el.clientHeight : 600;
  return Math.max(10, Math.floor((h - 36 - 44) / 36));
}

function _renderFnTable(data) {
  const rows  = _buildFnRows(data);
  const wrap  = document.getElementById('fn-table-wrap');
  const limit = _pageLimit('fn-table-wrap');
  const h     = wrap ? Math.max(200, wrap.clientHeight - 44) : 500;

  if (_fnGrid) { _fnGrid.destroy(); _fnGrid = null; }

  _fnGrid = new gridjs.Grid({
    columns: FN_COLS.map(c => ({
      id:    c.id,
      name:  c.name,
      width: c.width,
      sort:  c.sort !== false,
      formatter: c.id === 'type_icon' ? (cell) => gridjs.html(cell)
               : c.id === 'type'      ? (cell) => gridjs.html(cell)
               : undefined,
    })),
    data:        rows,
    sort:        true,
    fixedHeader: true,
    height:      h + 'px',
    pagination:  { limit, summary: true },
    style:       { table: { 'width': '100%' } },
  }).render(wrap);
}

function filterFunctions(q) {
  if (!_fnData.length) return;
  q = q.toLowerCase();
  const filtered = q
    ? _fnData.filter(f =>
        f.id.includes(q) || f.name.toLowerCase().includes(q) ||
        (f.type || '').toLowerCase().includes(q) ||
        (f.contains || '').toLowerCase().includes(q))
    : _fnData;
  _renderFnTable(filtered);
}

// =============================================================================
// ID BROWSER — VC Widgets
// =============================================================================

const VC_COLS = [
  { id: 'widget_id',  name: 'Widget ID',  width: '80px' },
  { id: 'type_icon',  name: '',           width: '28px', sort: false },
  { id: 'type',       name: 'Type',       width: '100px' },
  { id: 'caption',    name: 'Caption',    width: '18%' },
  { id: 'func_id',    name: 'Func ID',    width: '70px' },
  { id: 'func_name',  name: 'Func Name',  width: '20%' },
  { id: 'frame_path', name: 'Frame Path', width: '22%' },
  { id: 'x',  name: 'X',  width: '52px' },
  { id: 'y',  name: 'Y',  width: '52px' },
  { id: 'w',  name: 'W',  width: '52px' },
  { id: 'h',  name: 'H',  width: '52px' },
];

function _buildVcRows(data) {
  return data.map(w => [
    w.widget_id,
    icon(w.type),
    _badge(w.type),
    w.caption  || '—',
    w.func_id  || '—',
    w.func_name|| '—',
    w.frame_path,
    w.x || '—', w.y || '—', w.w || '—', w.h || '—',
  ]);
}

async function _loadVcWidgets() {
  const res = await fetch('/api/vc-widgets');
  if (!res.ok) { setStatus('Could not load VC widgets.', 'error'); return; }
  _vcData = await res.json();
  _renderVcTable(_vcData);
}

function _renderVcTable(data) {
  const rows  = _buildVcRows(data);
  const wrap  = document.getElementById('vc-table-wrap');
  const limit = _pageLimit('vc-table-wrap');
  const h     = wrap ? Math.max(200, wrap.clientHeight - 44) : 500;

  if (_vcGrid) { _vcGrid.destroy(); _vcGrid = null; }

  _vcGrid = new gridjs.Grid({
    columns: VC_COLS.map(c => ({
      id:    c.id,
      name:  c.name,
      width: c.width,
      sort:  c.sort !== false,
      formatter: (c.id === 'type_icon' || c.id === 'type')
        ? (cell) => gridjs.html(cell)
        : undefined,
    })),
    data:        rows,
    sort:        true,
    fixedHeader: true,
    height:      h + 'px',
    pagination:  { limit, summary: true },
  }).render(wrap);
}

function filterVcWidgets(q) {
  if (!_vcData.length) return;
  q = q.toLowerCase();
  const filtered = q
    ? _vcData.filter(w =>
        Object.values(w).some(v => String(v).toLowerCase().includes(q)))
    : _vcData;
  _renderVcTable(filtered);
}

// ── Shared ID Browser helpers ─────────────────────────────────────────────────
let _idBrowserLoaded = false;

function _invalidateIdBrowser() { _idBrowserLoaded = false; }

async function _ensureIdBrowserLoaded() {
  if (_idBrowserLoaded) return;
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  _idBrowserLoaded = true;
  await Promise.all([_loadFunctions(), _loadVcWidgets()]);
  _attachIdBrowserResizeObserver();
}

// Re-render tables when the wrapper changes size (window resize, panel resize).
// Debounced so it doesn't hammer on every pixel of a resize drag.
function _attachIdBrowserResizeObserver() {
  let _roTimer = null;
  const rerender = () => {
    clearTimeout(_roTimer);
    _roTimer = setTimeout(() => {
      if (_fnData.length)  _renderFnTable(_fnData);
      if (_vcData.length)  _renderVcTable(_vcData);
    }, 120);
  };
  const ro = new ResizeObserver(rerender);
  ['fn-table-wrap', 'vc-table-wrap'].forEach(id => {
    const el = document.getElementById(id);
    if (el) ro.observe(el);
  });
}

// =============================================================================
// CSV EXPORT  (client-side — no server round-trip)
// =============================================================================

function exportCsv(which) {
  let headers, rows, filename;

  if (which === 'functions') {
    headers  = ['ID', 'Type', 'Name', 'Contains / Steps'];
    rows     = _fnData.map(f => [f.id, f.type, f.name, f.contains]);
    filename = 'functions.csv';
  } else {
    headers  = ['Widget ID','Type','Caption','Func ID','Func Name',
                 'Frame Path','X','Y','W','H'];
    rows     = _vcData.map(w => [
      w.widget_id, w.type, w.caption, w.func_id, w.func_name,
      w.frame_path, w.x, w.y, w.w, w.h,
    ]);
    filename = 'vc_widgets.csv';
  }

  if (!rows.length) { setStatus('Nothing to export — load a workspace first.', 'warn'); return; }

  const esc = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const csv = [headers.map(esc).join(','),
               ...rows.map(r => r.map(esc).join(','))].join('\r\n');

  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`Exported ${rows.length} rows → ${filename}`);
}

// =============================================================================
// HELPERS
// =============================================================================

function _badge(type) {
  const cls = `badge badge-${type || 'default'}`;
  return `<span class="${cls}">${type || '?'}</span>`;
}

async function _apiJson(url, opts = {}) {
  try {
    const res  = await fetch(url, opts);
    return await res.json();
  } catch { return {}; }
}

function setStatus(msg, level = 'ok') {
  const el = document.getElementById('status-msg');
  el.textContent = msg;
  el.style.color = level === 'error' ? 'var(--red)'
                 : level === 'warn'  ? 'var(--yellow)'
                 : 'var(--green)';
  // Auto-clear after 5 s
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.textContent = ''; }, 5000);
}

// =============================================================================
// DRAG-AND-DROP (whole-window)
// =============================================================================

const overlay = document.getElementById('drop-overlay');
let _dragCounter = 0;

document.addEventListener('dragenter', e => {
  if ([...e.dataTransfer.items].some(i => i.kind === 'file')) {
    _dragCounter++;
    overlay.classList.add('visible');
  }
});
document.addEventListener('dragleave', () => {
  if (--_dragCounter <= 0) { _dragCounter = 0; overlay.classList.remove('visible'); }
});
document.addEventListener('dragover', e => e.preventDefault());
document.addEventListener('drop', e => {
  e.preventDefault();
  _dragCounter = 0;
  overlay.classList.remove('visible');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  const form = new FormData();
  form.append('file', f);
  _doLoad({ method: 'POST', body: form });
});

// =============================================================================
// THEME TOGGLE  (dark = Catppuccin Mocha / light = Catppuccin Latte)
// =============================================================================

// Themes cycle: dark (Mocha) → grey (Macchiato) → light (Latte) → dark…
const _THEMES = ['dark', 'grey', 'light'];
const _THEME_ICONS = { dark: '🌙', grey: '🌤', light: '☀️' };
const _THEME_TITLES = { dark: 'Dark (Mocha)', grey: 'Grey (Macchiato)', light: 'Light (Latte)' };

function toggleTheme() {
  const current = _getCurrentTheme();
  const next    = _THEMES[(_THEMES.indexOf(current) + 1) % _THEMES.length];
  _applyTheme(next);
}

function _getCurrentTheme() {
  if (document.body.classList.contains('theme-light')) return 'light';
  if (document.body.classList.contains('theme-grey'))  return 'grey';
  return 'dark';
}

function _applyTheme(theme) {
  document.body.classList.remove('theme-light', 'theme-grey');
  if (theme === 'light') document.body.classList.add('theme-light');
  if (theme === 'grey')  document.body.classList.add('theme-grey');
  const btn = document.getElementById('btn-theme');
  if (btn) { btn.textContent = _THEME_ICONS[theme]; btn.title = _THEME_TITLES[theme]; }
  try { localStorage.setItem('qlc-theme', theme); } catch {}
  // Redraw canvas if fixture module is loaded
  if (typeof _drawCanvas === 'function') _drawCanvas();
}

// =============================================================================
// INIT
// =============================================================================

(async function init() {
  // Restore theme preference
  try {
    const saved = localStorage.getItem('qlc-theme');
    if (saved && _THEMES.includes(saved) && saved !== 'dark') _applyTheme(saved);
  } catch {}

  // Restore state if a workspace was already loaded in a previous request
  const state = await _apiJson('/api/status');
  _updateHeader(state);

  // Pre-fill output dir from server state (persists across page reloads)
  const outdirRes = await _apiJson('/api/output-dir');
  const outdirInput  = document.getElementById('outdir-input');
  const outdirStatus = document.getElementById('outdir-status');
  if (outdirInput && outdirRes.output_dir) {
    outdirInput.value = outdirRes.output_dir;
    if (outdirStatus) outdirStatus.textContent = '✓ custom';
  }
})();
