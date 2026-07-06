/* =============================================================================
   QLC+ Swiss Knife — Web UI  app.js   v1.1.1
   =============================================================================
   Single-page application logic:
     - Sidebar navigation with go() / showSubtab()
     - Workspace loading (path, file upload, drag-and-drop .qxw / .qsk)
     - ID Browser: Functions + VC Widgets tables (Grid.js)
     - Client-side CSV export
     - Theme cycling (dark / grey / light) via data-theme
     - Collapsible sidebar with localStorage persistence
     - Nav tooltips, greeting, recents
   ============================================================================= */

'use strict';

// ── Cached data (module-level, re-fetched on every workspace load) ────────────
let _fnData  = [];   // raw functions array from /api/functions
let _vcData  = [];   // raw vc-widgets array from /api/vc-widgets
let _fnGrid  = null; // Grid.js instance for Functions table
let _vcGrid  = null; // Grid.js instance for VC Widgets table

// ── Type → emoji map (kept for Grid.js cell rendering) ──────────────────────
const TYPE_ICON = {
  Chaser: '🔄', Scene: '🎬', Sequence: '📋', EFX: '✨',
  Script: '📝', Show: '🎭', Audio: '🎵', Collection: '📦',
  RGBMatrix: '🌈', Button: '🔘', Slider: '🎚', Knob: '🔩',
  Frame: '🖼', SoloFrame: '⬜', CueList: '📑', Label: '🏷',
  XYPad: '🕹', Clock: '🕐', VUMeter: '📊',
  AudioTrigger: '🔊', Animation: '🎞', SpeedDial: '⏩',
};
const icon = t => TYPE_ICON[t] || '◻';

// ── Screen-ID → lazy-load function map ──────────────────────────────────────
const _LAZY = {
  idbrowser:  () => _ensureIdBrowserLoaded(),
  setlist:    () => typeof ensureSetlistLoaded    === 'function' && ensureSetlistLoaded(),
  dictionary: () => typeof ensureDictionaryLoaded === 'function' && ensureDictionaryLoaded(),
  checklist:  () => typeof ensureChecklistLoaded  === 'function' && ensureChecklistLoaded(),
  triggers:   () => typeof ensureTriggersLoaded   === 'function' && ensureTriggersLoaded(),
  fixtures:   () => typeof ensureFixturesLoaded   === 'function' && ensureFixturesLoaded(),
  merger:     () => typeof mergerInit             === 'function' && mergerInit(),
  brightness: () => typeof ensureBrightnessLoaded === 'function' && ensureBrightnessLoaded(),
  vceditor:   () => typeof _vceLoad               === 'function' && _vceLoad(),
};

// =============================================================================
// NAVIGATION — go(screenId)
// =============================================================================

/** Navigate to a screen.  screenId matches the suffix of scr-{id} / sn-{id}. */
function go(screenId) {
  // Update sidebar
  document.querySelectorAll('.sn-item').forEach(b => {
    b.classList.toggle('active', b.id === `sn-${screenId}`);
  });
  // Update screens
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.toggle('active', s.id === `scr-${screenId}`);
  });
  // Lazy-load
  const loader = _LAZY[screenId];
  if (loader) loader();
  // Hide nav tooltip
  const tip = document.getElementById('nav-tip');
  if (tip) tip.style.display = 'none';
}

/** Backward-compat alias: old code may call showTab('setlist') etc. */
function showTab(tabId) {
  // Map old tab IDs to new screen IDs
  const map = {
    'id-browser':       'idbrowser',
    'vc-visual-editor': 'vceditor',
    'fixture':          'fixtures',
  };
  go(map[tabId] || tabId);
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
// SIDEBAR COLLAPSE / EXPAND
// =============================================================================

function toggleSidebar() {
  document.body.classList.toggle('nav-min');
  const collapsed = document.body.classList.contains('nav-min');
  try { localStorage.setItem('sk-nav-min', collapsed ? '1' : ''); } catch {}
}

function _restoreSidebar() {
  try {
    if (localStorage.getItem('sk-nav-min') === '1') {
      document.body.classList.add('nav-min');
    }
  } catch {}
}

// =============================================================================
// NAV TOOLTIPS
// =============================================================================

function _initNavTooltips() {
  const tip = document.getElementById('nav-tip');
  if (!tip) return;

  document.querySelectorAll('.sn-item').forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      const rect = btn.getBoundingClientRect();
      const name = btn.dataset.tip || '';
      const desc = btn.dataset.desc || '';
      const isMin = document.body.classList.contains('nav-min');

      tip.innerHTML = isMin
        ? `<b>${name}</b> — ${desc}`
        : desc;

      tip.style.display = 'block';
      tip.style.left = rect.right + 10 + 'px';
      tip.style.top  = rect.top + rect.height / 2 + 'px';
    });

    btn.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    btn.addEventListener('click',      () => { tip.style.display = 'none'; });
  });
}

// =============================================================================
// THEME CYCLING — data-theme on <html>
// =============================================================================

const _THEMES = ['dark', 'grey', 'light'];

function cycleTheme() {
  const html    = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next    = _THEMES[(_THEMES.indexOf(current) + 1) % _THEMES.length];
  _applyTheme(next);
}

/** Backward-compat alias */
function toggleTheme() { cycleTheme(); }

function _applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  // Also keep body classes for any legacy CSS
  document.body.classList.remove('theme-light', 'theme-grey');
  if (theme === 'light') document.body.classList.add('theme-light');
  if (theme === 'grey')  document.body.classList.add('theme-grey');
  try { localStorage.setItem('sk-theme', theme); } catch {}
  // Redraw canvas if fixture module is loaded
  if (typeof _drawCanvas === 'function') _drawCanvas();
}

function _restoreTheme() {
  try {
    const saved = localStorage.getItem('sk-theme');
    if (saved && _THEMES.includes(saved)) _applyTheme(saved);
  } catch {}
}

// =============================================================================
// QUIT APP
// =============================================================================

async function quitApp() {
  // Check for unsaved session changes
  if (typeof _sess !== 'undefined' && _sess.dirty) {
    if (!confirm('You have unsaved session changes.\n\nQuit anyway?')) return;
  }
  try {
    await fetch('/api/quit', { method: 'POST' });
  } catch { /* server is shutting down */ }
  // Give the server a moment, then close the window/tab
  setTimeout(() => {
    document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;' +
      'height:100vh;font-family:system-ui;color:#cdd6f4;background:#1e1e2e;flex-direction:column;gap:12px">' +
      '<div style="font-size:2rem">⚡</div>' +
      '<div>QLC+ Swiss Knife has been shut down.</div>' +
      '<div style="font-size:12px;opacity:.5">You can close this tab.</div></div>';
    try { window.close(); } catch {}
  }, 600);
}

// =============================================================================
// GREETING + SETTINGS
// =============================================================================

async function _initGreeting() {
  const el = document.getElementById('greeting');
  if (!el) return;

  let name = null;
  try {
    const r = await fetch('/api/settings');
    if (r.ok) {
      const d = await r.json();
      if (d.user_name) name = d.user_name;
    }
  } catch {}

  const h = new Date().getHours();
  const part = h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening';
  el.textContent = name
    ? `Good ${part}, ${name} 👋`
    : 'Welcome 👋';
}

// =============================================================================
// RECENTS
// =============================================================================

function _addRecent(path, type) {
  if (!path) return;
  try {
    let recents = JSON.parse(localStorage.getItem('sk-recents') || '[]');
    recents = recents.filter(r => r.path !== path);
    recents.unshift({ path, type: type || 'qxw', ts: Date.now() });
    if (recents.length > 5) recents.length = 5;
    localStorage.setItem('sk-recents', JSON.stringify(recents));
    _renderRecents();
  } catch {}
}

function _renderRecents() {
  const wrap = document.getElementById('recent-list');
  if (!wrap) return;
  try {
    const recents = JSON.parse(localStorage.getItem('sk-recents') || '[]');
    if (!recents.length) { wrap.innerHTML = ''; return; }
    wrap.innerHTML = '<div class="recents-title">Recent files</div>' +
      recents.map(r => {
        const name = r.path.split(/[\\/]/).pop();
        const ago  = _timeAgo(r.ts);
        return `<div class="recent-item" onclick="loadRecentFile('${r.path.replace(/'/g, "\\'")}', '${r.type}')">
          <svg class="ic"><use href="/static/icons.svg#clock"/></svg>
          <span class="recent-name">${name}</span>
          <span class="recent-ago">${ago}</span>
        </div>`;
      }).join('');
  } catch {}
}

function _timeAgo(ts) {
  const diff = (Date.now() - ts) / 1000;
  if (diff < 60)   return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function loadRecentFile(path, type) {
  if (type === 'qsk') {
    if (typeof sessionLoadFromPath === 'function') sessionLoadFromPath(path);
    return;
  }
  const inp = document.getElementById('path-input');
  if (inp) inp.value = path;
  _doLoad({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
}

// =============================================================================
// NATIVE FILE PICKER  (calls /api/picker/pick — gets real OS path)
// =============================================================================

let _pickerAvailable = null;

async function nativePick(title, types = [], initDir = '') {
  if (_pickerAvailable === null) {
    try {
      const r = await fetch('/api/picker/available');
      _pickerAvailable = (await r.json()).available;
    } catch { _pickerAvailable = false; }
  }
  if (!_pickerAvailable) return null;

  try {
    const r = await fetch('/api/picker/pick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, types, initial_dir: initDir }),
    });
    const d = await r.json();
    return d.cancelled ? null : (d.path || null);
  } catch {
    return null;
  }
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

async function browseWorkspace() {
  const path = await nativePick(
    'Select QLC+ workspace (.qxw)',
    [{ label: 'QLC+ Workspace', exts: ['.qxw'] }]
  );
  if (path) {
    const inp = document.getElementById('path-input');
    if (inp) inp.value = path;
    await _doLoad({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
  } else {
    document.getElementById('file-input').click();
  }
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
      console.error('[QLC Swiss Knife] Load error:', msg);
      return;
    }
    _updateHeader(data);
    _invalidateAllTabs();
    setStatus(`Loaded: ${data.path ? data.path.split(/[\\/]/).pop() : 'workspace'}`);
    // Track in session
    if (data.path && typeof sessionOnWorkspaceLoaded === 'function') {
      sessionOnWorkspaceLoaded(data.path);
    }
    // Add to recents
    if (data.path) _addRecent(data.path, 'qxw');
    // Refresh current screen if it's ID browser
    const activeScr = document.querySelector('.screen.active');
    if (activeScr && activeScr.id === 'scr-idbrowser') {
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
  if (typeof invalidateBrightness === 'function') invalidateBrightness();
  // Re-load whichever screen is currently visible
  const activeScr = document.querySelector('.screen.active');
  if (activeScr) {
    const scrId = activeScr.id.replace('scr-', '');
    const loader = _LAZY[scrId];
    if (loader) loader();
  }
}

function _updateHeader(state) {
  const nameEl    = document.getElementById('ws-name');
  const reloadBtn = document.getElementById('btn-reload');
  const pathInput = document.getElementById('path-input');

  if (state.loaded) {
    if (state.path) {
      const name = state.path.split(/[\\/]/).pop();
      if (nameEl) { nameEl.textContent = name; nameEl.className = ''; }
      if (pathInput) pathInput.value = state.path;
      if (reloadBtn) reloadBtn.disabled = false;
    } else if (state.original_name) {
      if (nameEl) { nameEl.textContent = state.original_name + '  (uploaded)'; nameEl.className = ''; }
      if (reloadBtn) reloadBtn.disabled = true;
    }
  } else {
    if (nameEl) { nameEl.textContent = 'No workspace loaded'; nameEl.className = 'ws-unloaded'; }
    if (reloadBtn) reloadBtn.disabled = true;
  }

  // Update counts in files panel (if element exists)
  const countsEl = document.getElementById('fp-counts');
  if (countsEl) {
    countsEl.textContent =
      `Fn: ${state.func_count ?? '—'}  Fix: ${state.fixture_count ?? '—'}  VC: ${state.vc_widget_count ?? '—'}`;
  }
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
  { id: 'caption',    name: 'Caption',    width: '22%' },
  { id: 'func_id',    name: 'Func ID',    width: '70px' },
  { id: 'func_name',  name: 'Func Name',  width: '22%' },
  { id: 'frame_path', name: 'Frame Path', width: '28%' },
];

function _buildVcRows(data) {
  return data.map(w => [
    w.widget_id,
    icon(w.type),
    _badge(w.type),
    w.caption   || '—',
    w.func_id   || '—',
    w.func_name || '—',
    w.frame_path,
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

/** Show a status message as a temporary toast notification. */
function setStatus(msg, level = 'ok') {
  // Try existing status-msg element first (backward compat)
  let el = document.getElementById('status-msg');
  if (!el) {
    // Create a toast element
    el = document.createElement('div');
    el.id = 'status-msg';
    el.style.cssText = 'position:fixed;bottom:16px;right:16px;padding:8px 16px;' +
      'border-radius:var(--radius,6px);font-size:12px;z-index:9999;' +
      'background:var(--surface-2,#232c3f);border:1px solid var(--border,#273043);' +
      'color:var(--text,#e8ecf5);pointer-events:none;opacity:0;transition:opacity .3s;' +
      'max-width:400px;font-family:var(--font);';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.color = level === 'error' ? 'var(--danger, #f38ba8)'
                 : level === 'warn'  ? 'var(--warn, #f9e2af)'
                 : 'var(--ok, #a6e3a1)';
  el.style.opacity = '1';
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.style.opacity = '0'; }, 5000);
}

// =============================================================================
// DRAG-AND-DROP (whole-window — .qxw and .qsk)
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

  const name = f.name.toLowerCase();
  // Handle .qsk session files
  if (name.endsWith('.qsk')) {
    if (typeof sessionLoadDroppedFile === 'function') {
      sessionLoadDroppedFile(f);
    } else {
      // Fallback: read JSON and try to load
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result);
          if (data.workspace) {
            const inp = document.getElementById('path-input');
            if (inp) inp.value = data.workspace;
            _doLoad({
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: data.workspace }),
            });
          }
        } catch (err) { setStatus('Invalid .qsk file', 'error'); }
      };
      reader.readAsText(f);
    }
    return;
  }

  // Default: treat as .qxw
  const form = new FormData();
  form.append('file', f);
  _doLoad({ method: 'POST', body: form });
});

// =============================================================================
// INIT
// =============================================================================

(async function init() {
  // Restore theme
  _restoreTheme();

  // Restore sidebar state
  _restoreSidebar();

  // Init nav tooltips
  _initNavTooltips();

  // Greeting
  _initGreeting();

  // Render recents
  _renderRecents();

  // Restore state if a workspace was already loaded
  const state = await _apiJson('/api/status');
  _updateHeader(state);

  // Initialise session module
  if (typeof initSession === 'function') initSession();
})();
