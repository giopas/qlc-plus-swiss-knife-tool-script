/* =========================================================================
   static/js/quickstart.js — Quick Start QXW Wizard
   =========================================================================
   5-step wizard: Fixtures → Placement → Analysis → VC Preview → Export
   Calls /api/quickstart/* endpoints (quick_start_routes.py)
   ========================================================================= */

let _qsLoaded = false;
function ensureQuickStartLoaded() {
  if (_qsLoaded) return;
  _qsLoaded = true;
  qsRefreshStatus();
}

/* ── state ─────────────────────────────────────────────────────────────── */
let _qsStep = 1;
const _qsTotalSteps = 5;
let _qsLoadedDefs = [];  // array of {key, manufacturer, model, type, channels, modes}

/* ── Canvas stage state ────────────────────────────────────────────────── */
let _qsStage = { w_mm: 8000, d_mm: 6000, h_mm: 4000, cols: 8, rows: 6 };
let _qsViewMode = 'top';
let _qsSelectedIdxs = new Set();   // multi-select: set of selected indices
let _qsRigData = [];          // local copy of rig for canvas rendering
let _qsCanvas = null;
let _qsCtx = null;
let _qsDragIdx = -1;
let _qsDragOffX = 0;
let _qsDragOffZ = 0;
let _qsDragStartPositions = {};  // {idx: {x, z}} for group drag
let _qsDragAnchorStart = null;   // anchor fixture start pos

const _QS_PALETTE = [
  '#00e5ff','#ff007f','#39ff14','#ffff00',
  '#ff8c00','#b026ff','#ff3333','#00ff99',
  '#ff66cc','#33ccff',
];
let _qsModelColorMap = {};

const _QS_TITLE_H = 28, _QS_MARGIN_L = 48, _QS_MARGIN_R = 16,
      _QS_MARGIN_T = 16, _QS_MARGIN_B = 40;

const _QS_HEIGHT_TIERS = [
  { label: 'Floor',    min: 0,    max: 500  },
  { label: 'Low-Mid',  min: 500,  max: 1500 },
  { label: 'Mid',      min: 1500, max: 2500 },
  { label: 'Top-Mid',  min: 2500, max: 3500 },
  { label: 'Top',      min: 3500, max: Infinity },
];

/* Position presets (fraction of stage dimension) */
const _QS_POS_H = { 'Left': 0.2, 'Center': 0.5, 'Right': 0.8 };
const _QS_POS_D = { 'Back': 0.2, 'Mid': 0.5, 'Front': 0.8 };
const _QS_POS_Y = { 'Floor': 0, 'Low-Mid': 1000, 'Mid': 2000, 'Top-Mid': 3000, 'Top': 3500 };

/* ── helpers ────────────────────────────────────────────────────────────── */
function _qsApi(method, path, body) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  return fetch('/api/quickstart' + path, opts).then(r => r.json());
}

function _qsShow(id) {
  document.querySelectorAll('.qs-step').forEach(el => el.style.display = 'none');
  const el = document.getElementById(id);
  if (el) el.style.display = '';
}

function _qsUpdateNav() {
  const back = document.getElementById('qs-btn-back');
  const next = document.getElementById('qs-btn-next');
  const exp  = document.getElementById('qs-btn-export');

  if (back) back.style.display = _qsStep > 1 ? '' : 'none';
  if (next) next.style.display = _qsStep < _qsTotalSteps ? '' : 'none';
  if (exp)  exp.style.display  = _qsStep === _qsTotalSteps ? '' : 'none';

  const ind = document.getElementById('qs-step-indicator');
  if (ind) ind.textContent = `Step ${_qsStep} of ${_qsTotalSteps}`;

  for (let i = 1; i <= _qsTotalSteps; i++) {
    const dot = document.getElementById('qs-dot-' + i);
    if (!dot) continue;
    dot.classList.toggle('qs-dot-active', i === _qsStep);
    dot.classList.toggle('qs-dot-done', i < _qsStep);
  }
}

/* ── navigation ─────────────────────────────────────────────────────────── */
function qsGoStep(n) {
  _qsStep = Math.max(1, Math.min(_qsTotalSteps, n));
  _qsShow('qs-step-' + _qsStep);
  _qsUpdateNav();

  if (_qsStep === 2) qsInitStage();
  if (_qsStep === 3) qsRunAnalysis();
  if (_qsStep === 4) qsLoadPreview();
  if (_qsStep === 5) qsLoadSummary();
}

function qsNext() { qsGoStep(_qsStep + 1); }
function qsBack() { qsGoStep(_qsStep - 1); }

/* ── Loaded definitions management ─────────────────────────────────────── */
function _qsAddLoadedDef(defn) {
  if (_qsLoadedDefs.find(d => d.key === defn.key)) return;
  _qsLoadedDefs.push(defn);
  _qsRenderLoadedDefs();
  _qsRenderFixtureSelect();
}

function _qsRenderLoadedDefs() {
  const wrap = document.getElementById('qs-loaded-defs');
  if (!wrap) return;
  if (_qsLoadedDefs.length === 0) {
    wrap.innerHTML = '<div class="qs-empty">No fixture definitions loaded yet.</div>';
    return;
  }
  const thSt = 'text-align:left;padding:6px 8px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)';
  const tdSt = 'padding:5px 8px;border-bottom:1px solid var(--surface1)';
  let html = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">
    <thead><tr>
      <th style="${thSt}">Manufacturer</th><th style="${thSt}">Model</th>
      <th style="${thSt}">Type</th><th style="${thSt};text-align:center">Channels</th><th style="padding:6px 4px;border-bottom:1px solid var(--overlay0)"></th>
    </tr></thead><tbody>`;
  _qsLoadedDefs.forEach((d, i) => {
    html += `<tr>
      <td style="${tdSt}">${_esc(d.manufacturer)}</td>
      <td style="${tdSt}">${_esc(d.model)}</td>
      <td style="${tdSt}">${_esc(d.type)}</td>
      <td style="${tdSt};text-align:center">${d.channels}</td>
      <td style="${tdSt};text-align:center"><button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:10px" onclick="qsRemoveLoadedDef('${_esc(d.key.replace(/'/g, "\\'"))}')">Remove</button></td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  wrap.innerHTML = html;
}

function qsRemoveLoadedDef(key) {
  _qsApi('POST', '/remove-def', { key, remove_fixtures: false })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsLoadedDefs = _qsLoadedDefs.filter(x => x.key !== key);
      _qsRenderLoadedDefs();
      _qsRenderFixtureSelect();
    })
    .catch(e => alert('Remove failed: ' + e));
}

function _qsRenderFixtureSelect() {
  const sel = document.getElementById('qs-fix-type');
  if (!sel) return;
  sel.innerHTML = '';
  if (_qsLoadedDefs.length === 0) {
    sel.innerHTML = '<option value="">— load a fixture first —</option>';
    return;
  }
  _qsLoadedDefs.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d.key;
    opt.textContent = `${d.manufacturer} — ${d.model} (${d.channels} ch)`;
    sel.appendChild(opt);
  });
}

function _esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

/* ── Step 1: Fixture Selection ─────────────────────────────────────────── */
function qsRefreshStatus() {
  _qsApi('GET', '/status').then(d => {
    if (d.loaded_defs && d.loaded_defs.length) {
      _qsLoadedDefs = d.loaded_defs;
      _qsRenderLoadedDefs();
      _qsRenderFixtureSelect();
    }
    if (d.rig && d.rig.length > 0) _qsRenderRigTable(d.rig);
  }).catch(() => {});
}

/* ── Load from file path ───────────────────────────────────────────────── */
function qsLoadQxf() {
  const path = document.getElementById('qs-qxf-path').value.trim();
  if (!path) return;
  _qsApi('POST', '/load-qxf', { path })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      const def = d.definition;
      _qsAddLoadedDef(def);
      const info = document.getElementById('qs-qxf-info');
      if (info) {
        info.textContent = `Loaded: ${def.manufacturer} ${def.model} — ${def.channels} ch`;
        info.style.color = 'var(--green)';
      }
    })
    .catch(e => alert('Failed to load QXF: ' + e));
}

/* ── Upload from file input ────────────────────────────────────────────── */
function qsUploadQxf() {
  const inp = document.getElementById('qs-qxf-upload');
  if (!inp || !inp.files.length) return;

  const fd = new FormData();
  fd.append('file', inp.files[0]);

  fetch('/api/quickstart/upload-qxf', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(d => {
      if (d.error) { alert(d.error); return; }
      const def = d.definition;
      _qsAddLoadedDef(def);
      const info = document.getElementById('qs-qxf-info');
      if (info) {
        info.textContent = `Uploaded: ${def.manufacturer} ${def.model} — ${def.channels} ch`;
        info.style.color = 'var(--green)';
      }
      inp.value = '';
    })
    .catch(e => alert('Upload failed: ' + e));
}

/* ── Add fixture to rig ────────────────────────────────────────────────── */
function qsAddFixture() {
  const sel = document.getElementById('qs-fix-type');
  const key = sel ? sel.value : '';
  if (!key) { alert('Select a fixture type first. Load a QXF definition above.'); return; }
  const qty  = parseInt(document.getElementById('qs-fix-qty').value) || 1;
  const name = document.getElementById('qs-fix-name').value.trim() || '';

  _qsApi('POST', '/add-fixture', { key, quantity: qty, name: name || undefined })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsRenderRigTable(d.rig);
    })
    .catch(e => alert('Add failed: ' + e));
}

function qsRemoveFixture(idx) {
  _qsApi('POST', '/remove-fixture', { idx })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsRenderRigTable(d.rig);
    })
    .catch(e => alert('Remove failed: ' + e));
}

function qsClearRig() {
  _qsApi('POST', '/clear')
    .then(d => _qsRenderRigTable(d.rig || []))
    .catch(e => alert('Clear failed: ' + e));
}

function _qsRenderRigTable(rig) {
  const wrap = document.getElementById('qs-rig-table');
  if (!wrap) return;
  if (!rig || rig.length === 0) {
    wrap.innerHTML = '<div class="qs-empty">No fixtures added yet. Load a fixture definition and add it above.</div>';
    return;
  }
  let html = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed">
    <colgroup><col style="width:32px"><col><col><col style="width:36px"><col style="width:40px"><col style="width:44px"><col style="width:38px"></colgroup>
    <thead><tr>
      <th style="text-align:left;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">#</th>
      <th style="text-align:left;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">Name</th>
      <th style="text-align:left;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">Model</th>
      <th style="text-align:center;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">Ch</th>
      <th style="text-align:center;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">Univ</th>
      <th style="text-align:center;padding:6px 4px;border-bottom:1px solid var(--overlay0);font-size:11px;color:var(--overlay0)">Addr</th>
      <th style="padding:6px 4px;border-bottom:1px solid var(--overlay0)"></th>
    </tr></thead><tbody>`;
  rig.forEach((f, i) => {
    html += `<tr>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1)">${i + 1}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(f.name || '—')}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);font-size:11px;color:var(--overlay0);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(f.model || '')}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);text-align:center">${f.channels || '—'}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);text-align:center">${f.universe != null ? f.universe + 1 : '—'}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);text-align:center">${f.address != null ? f.address + 1 : '—'}</td>
      <td style="padding:5px 4px;border-bottom:1px solid var(--surface1);text-align:center"><button class="btn btn-danger btn-sm" style="padding:2px 6px;font-size:10px" onclick="qsRemoveFixture(${i})">✕</button></td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  wrap.innerHTML = html;
}

/* ── GitHub Fixture Browser ───────────────────────────────────────────── */
let _qsGhMfgs = [];
let _qsGhFixtures = [];

function qsOpenGitHub() {
  const modal = document.getElementById('qs-gh-modal');
  if (modal) modal.style.display = '';
  qsGhLoadManufacturers();
}

function qsCloseGitHub() {
  const modal = document.getElementById('qs-gh-modal');
  if (modal) modal.style.display = 'none';
}

function qsGhLoadManufacturers() {
  const list = document.getElementById('qs-gh-mfg-list');
  const info = document.getElementById('qs-gh-status');
  if (list) list.innerHTML = '<div class="qs-loading">Loading manufacturers from QLC+ GitHub...</div>';
  if (info) info.textContent = '';

  _qsApi('GET', '/gh/manufacturers')
    .then(d => {
      if (d.error) { if (list) list.innerHTML = `<div class="qs-error">${_esc(d.error)}</div>`; return; }
      _qsGhMfgs = d.manufacturers || [];
      _qsGhFilterManufacturers();
      if (info) info.textContent = `${_qsGhMfgs.length} manufacturers available`;
    })
    .catch(e => { if (list) list.innerHTML = `<div class="qs-error">Failed: ${_esc(String(e))}</div>`; });
}

function _qsGhFilterManufacturers() {
  const q = (document.getElementById('qs-gh-search').value || '').toLowerCase();
  const list = document.getElementById('qs-gh-mfg-list');
  if (!list) return;

  const filtered = q ? _qsGhMfgs.filter(m => m.toLowerCase().includes(q)) : _qsGhMfgs;
  if (filtered.length === 0) {
    list.innerHTML = '<div class="qs-empty">No manufacturers match your search.</div>';
    return;
  }
  let html = '<div class="qs-gh-grid">';
  filtered.forEach(m => {
    html += `<button class="btn btn-surface qs-gh-mfg-btn" onclick="qsGhSelectMfg('${_esc(m.replace(/'/g, "\\'"))}')">${_esc(m)}</button>`;
  });
  html += '</div>';
  list.innerHTML = html;
}

function qsGhSelectMfg(mfg) {
  const fixList = document.getElementById('qs-gh-fixture-list');
  if (fixList) fixList.innerHTML = '<div class="qs-loading">Loading fixtures...</div>';

  document.querySelectorAll('.qs-gh-mfg-btn').forEach(b => b.classList.remove('btn-primary'));
  document.querySelectorAll('.qs-gh-mfg-btn').forEach(b => {
    if (b.textContent === mfg) b.classList.add('btn-primary');
  });

  _qsApi('GET', '/gh/fixtures?manufacturer=' + encodeURIComponent(mfg))
    .then(d => {
      if (d.error) { if (fixList) fixList.innerHTML = `<div class="qs-error">${_esc(d.error)}</div>`; return; }
      _qsGhFixtures = (d.fixtures || []).map(f => ({ ...f, manufacturer: mfg }));
      _qsGhRenderFixtures();
    })
    .catch(e => { if (fixList) fixList.innerHTML = `<div class="qs-error">Failed: ${_esc(String(e))}</div>`; });
}

function _qsGhRenderFixtures() {
  const fixList = document.getElementById('qs-gh-fixture-list');
  if (!fixList) return;
  if (_qsGhFixtures.length === 0) {
    fixList.innerHTML = '<div class="qs-empty">No fixtures found.</div>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Fixture</th><th></th></tr></thead><tbody>';
  _qsGhFixtures.forEach(f => {
    html += `<tr>
      <td>${_esc(f.display)}</td>
      <td><button class="btn btn-success btn-sm" onclick="qsGhLoadFixture('${_esc(f.manufacturer.replace(/'/g, "\\'"))}','${_esc(f.name.replace(/'/g, "\\'"))}',this)">Load</button></td>
    </tr>`;
  });
  html += '</tbody></table>';
  fixList.innerHTML = html;
}

function qsGhLoadFixture(mfg, filename, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  _qsApi('POST', '/gh/load', { manufacturer: mfg, filename })
    .then(d => {
      if (d.error) { alert(d.error); if (btn) { btn.disabled = false; btn.textContent = 'Load'; } return; }
      const def = d.definition;
      _qsAddLoadedDef(def);
      if (btn) { btn.textContent = 'Loaded'; btn.classList.remove('btn-success'); btn.classList.add('btn-surface'); }
      const info = document.getElementById('qs-gh-status');
      if (info) info.textContent = `Loaded: ${def.manufacturer} ${def.model}`;
    })
    .catch(e => {
      alert('Load failed: ' + e);
      if (btn) { btn.disabled = false; btn.textContent = 'Load'; }
    });
}


/* ═══════════════════════════════════════════════════════════════════════════
   Step 2: Stage Placement — Canvas-based 2D stage view
   ═══════════════════════════════════════════════════════════════════════════ */

function _qsCv(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || '#888';
}

function _qsContrastColor(hex) {
  const r = parseInt(hex.slice(1,3),16)||0;
  const g = parseInt(hex.slice(3,5),16)||0;
  const b = parseInt(hex.slice(5,7),16)||0;
  return (r*299 + g*587 + b*114) / 1000 > 128 ? '#11111b' : '#cdd6f4';
}

function _qsAssignColors() {
  let ci = 0;
  for (const f of _qsRigData) {
    const key = f.model || f.manufacturer || 'Unknown';
    if (!_qsModelColorMap[key]) {
      _qsModelColorMap[key] = _QS_PALETTE[ci % _QS_PALETTE.length];
      ci++;
    }
    f._color = _qsModelColorMap[key];
  }
}

/* ── Init the stage canvas (called when entering Step 2) ─────────────── */
function qsInitStage() {
  _qsApi('GET', '/status').then(d => {
    _qsRigData = (d.rig || []).map(f => ({
      ...f,
      x_mm: f.x || 0,
      z_mm: f.z || 0,
      y_mm: f.y || 0,
    }));
    _qsAssignColors();
    _qsRenderStageFixtureList();
    _qsSetupCanvas();
    _qsDrawCanvas();
    _qsSyncStageFields();
  });
}

function _qsSetupCanvas() {
  _qsCanvas = document.getElementById('qs-stage-canvas');
  if (!_qsCanvas) return;
  _qsCtx = _qsCanvas.getContext('2d');
  _qsResizeCanvas();

  if (!_qsCanvas._qsAttached) {
    _qsCanvas._qsAttached = true;
    const ro = new ResizeObserver(() => { _qsResizeCanvas(); _qsDrawCanvas(); });
    ro.observe(_qsCanvas.parentElement);
    _qsCanvas.addEventListener('mousedown', _qsOnMouseDown);
    _qsCanvas.addEventListener('mousemove', _qsOnMouseMove);
    _qsCanvas.addEventListener('mouseup',   _qsOnMouseUp);
    _qsCanvas.addEventListener('mouseleave', _qsOnMouseUp);
  }
}

function _qsResizeCanvas() {
  if (!_qsCanvas) return;
  const pane = _qsCanvas.parentElement;
  _qsCanvas.width  = pane.clientWidth  || 600;
  _qsCanvas.height = pane.clientHeight || 400;
}

function _qsSyncStageFields() {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  set('qs-stage-w', _qsStage.w_mm);
  set('qs-stage-d', _qsStage.d_mm);
  set('qs-stage-h', _qsStage.h_mm);
}

function qsApplyStageFields() {
  const g = id => parseInt(document.getElementById(id)?.value || 0);
  _qsStage.w_mm = Math.max(1000, g('qs-stage-w'));
  _qsStage.d_mm = Math.max(1000, g('qs-stage-d'));
  _qsStage.h_mm = Math.max(1000, g('qs-stage-h'));
  _qsDrawCanvas();
}

/* ── View mode ────────────────────────────────────────────────────────── */
function qsSetView(mode) {
  _qsViewMode = mode;
  ['top','front','side'].forEach(m => {
    const btn = document.getElementById('qs-btn-view-' + m);
    if (btn) btn.classList.toggle('btn-view-active', m === mode);
  });
  _qsDrawCanvas();
}

/* ── Fixture list for Step 2 (sidebar) ────────────────────────────────── */
function _qsRenderStageFixtureList() {
  const wrap = document.getElementById('qs-stage-fixture-list');
  if (!wrap) return;
  if (!_qsRigData.length) {
    wrap.innerHTML = '<div class="qs-empty">No fixtures. Go back to Step 1.</div>';
    return;
  }
  let html = '';
  _qsRigData.forEach((f, i) => {
    const sel = _qsSelectedIdxs.has(i) ? ' qs-fix-row-sel' : '';
    const dot = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${f._color||'#888'};margin-right:6px"></span>`;
    html += `<div class="qs-fix-row${sel}" data-idx="${i}" onclick="qsSelectFixture(${i}, event)">
      ${dot}<span class="qs-fix-row-name">${_esc(f.name||'—')}</span>
      <span class="qs-fix-row-pos">${Math.round(f.x_mm)}, ${Math.round(f.z_mm)}, ${Math.round(f.y_mm)}</span>
    </div>`;
  });
  wrap.innerHTML = html;
  _qsUpdateAlignBtns();
}

function qsSelectFixture(idx, evt) {
  if (evt && (evt.shiftKey || evt.ctrlKey || evt.metaKey)) {
    // Toggle this index in the selection set
    if (_qsSelectedIdxs.has(idx)) _qsSelectedIdxs.delete(idx);
    else _qsSelectedIdxs.add(idx);
  } else {
    // Single-click: toggle or replace
    if (_qsSelectedIdxs.size === 1 && _qsSelectedIdxs.has(idx)) {
      _qsSelectedIdxs.clear();
    } else {
      _qsSelectedIdxs.clear();
      _qsSelectedIdxs.add(idx);
    }
  }
  _qsRenderStageFixtureList();
  _qsDrawCanvas();
}

function qsSelectAll() {
  _qsRigData.forEach((_, i) => _qsSelectedIdxs.add(i));
  _qsRenderStageFixtureList();
  _qsDrawCanvas();
}

function qsSelectNone() {
  _qsSelectedIdxs.clear();
  _qsRenderStageFixtureList();
  _qsDrawCanvas();
}

function _qsUpdateAlignBtns() {
  const wrap = document.getElementById('qs-align-btns');
  if (!wrap) return;
  const n = _qsSelectedIdxs.size;
  // Edge-align (Left/Right/Back/Front) needs 1+; Avg needs 2+; Dist needs 3+
  wrap.querySelectorAll('button').forEach(b => {
    const fn = b.getAttribute('onclick') || '';
    if (fn.includes('Distribute')) b.disabled = n < 3;
    else if (fn.includes('AlignX') || fn.includes('AlignZ') || fn.includes('AlignY')) b.disabled = n < 2;
    else b.disabled = n < 1;  // Left/Right/Top/Bottom: 1+ selected
  });
  const info = document.getElementById('qs-sel-info');
  if (info) info.textContent = n === 0 ? 'None selected' : `${n} selected`;
}

/* ── Alignment functions ─────────────────────────────────────────────── */
function _qsGetSelected() {
  return [..._qsSelectedIdxs].filter(i => i >= 0 && i < _qsRigData.length);
}

function qsAlignX() {
  // Align horizontally: all selected get the average X
  const sel = _qsGetSelected(); if (sel.length < 2) return;
  const avg = sel.reduce((s, i) => s + _qsRigData[i].x_mm, 0) / sel.length;
  const x = Math.round(avg);
  const promises = sel.map(i => {
    _qsRigData[i].x_mm = x;
    return _qsApi('POST', '/update-placement', { idx: i, x });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignZ() {
  // Align vertically (depth): all selected get the average Z
  const sel = _qsGetSelected(); if (sel.length < 2) return;
  const avg = sel.reduce((s, i) => s + _qsRigData[i].z_mm, 0) / sel.length;
  const z = Math.round(avg);
  const promises = sel.map(i => {
    _qsRigData[i].z_mm = z;
    return _qsApi('POST', '/update-placement', { idx: i, z });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignY() {
  // Align height: all selected get the average Y
  const sel = _qsGetSelected(); if (sel.length < 2) return;
  const avg = sel.reduce((s, i) => s + _qsRigData[i].y_mm, 0) / sel.length;
  const y = Math.round(avg);
  const promises = sel.map(i => {
    _qsRigData[i].y_mm = y;
    return _qsApi('POST', '/update-placement', { idx: i, y });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignLeft() {
  const sel = _qsGetSelected(); if (sel.length < 1) return;
  const x = 0;  // stage left edge
  const promises = sel.map(i => {
    _qsRigData[i].x_mm = x;
    return _qsApi('POST', '/update-placement', { idx: i, x });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignRight() {
  const sel = _qsGetSelected(); if (sel.length < 1) return;
  const x = _qsStage.w_mm;  // stage right edge
  const promises = sel.map(i => {
    _qsRigData[i].x_mm = x;
    return _qsApi('POST', '/update-placement', { idx: i, x });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignTop() {
  // Back of stage (z=0)
  const sel = _qsGetSelected(); if (sel.length < 1) return;
  const z = 0;  // stage back edge
  const promises = sel.map(i => {
    _qsRigData[i].z_mm = z;
    return _qsApi('POST', '/update-placement', { idx: i, z });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsAlignBottom() {
  // Front of stage (z=d_mm)
  const sel = _qsGetSelected(); if (sel.length < 1) return;
  const z = _qsStage.d_mm;  // stage front edge
  const promises = sel.map(i => {
    _qsRigData[i].z_mm = z;
    return _qsApi('POST', '/update-placement', { idx: i, z });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsDistributeX() {
  // Spread selected evenly along X axis
  const sel = _qsGetSelected(); if (sel.length < 3) return;
  sel.sort((a, b) => _qsRigData[a].x_mm - _qsRigData[b].x_mm);
  const minX = _qsRigData[sel[0]].x_mm;
  const maxX = _qsRigData[sel[sel.length - 1]].x_mm;
  const step = (maxX - minX) / (sel.length - 1);
  const promises = sel.map((idx, j) => {
    const x = Math.round(minX + j * step);
    _qsRigData[idx].x_mm = x;
    return _qsApi('POST', '/update-placement', { idx, x });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

function qsDistributeZ() {
  // Spread selected evenly along Z axis
  const sel = _qsGetSelected(); if (sel.length < 3) return;
  sel.sort((a, b) => _qsRigData[a].z_mm - _qsRigData[b].z_mm);
  const minZ = _qsRigData[sel[0]].z_mm;
  const maxZ = _qsRigData[sel[sel.length - 1]].z_mm;
  const step = (maxZ - minZ) / (sel.length - 1);
  const promises = sel.map((idx, j) => {
    const z = Math.round(minZ + j * step);
    _qsRigData[idx].z_mm = z;
    return _qsApi('POST', '/update-placement', { idx, z });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); _qsDrawCanvas(); });
}

/* ── Position presets ─────────────────────────────────────────────────── */
function qsPresetPos(hKey, dKey) {
  // Apply horizontal (X) and depth (Z) preset to selected fixtures or all
  const targets = _qsSelectedIdxs.size > 0 ? [..._qsSelectedIdxs] : _qsRigData.map((_, i) => i);
  const x_mm = Math.round(_qsStage.w_mm * _QS_POS_H[hKey]);
  const z_mm = Math.round(_qsStage.d_mm * _QS_POS_D[dKey]);

  const promises = targets.map(idx => {
    _qsRigData[idx].x_mm = x_mm;
    _qsRigData[idx].z_mm = z_mm;
    return _qsApi('POST', '/update-placement', { idx, x: x_mm, z: z_mm });
  });
  Promise.all(promises).then(() => {
    _qsRenderStageFixtureList();
    _qsDrawCanvas();
  });
}

function qsPresetHeight(hKey) {
  const targets = _qsSelectedIdxs.size > 0 ? [..._qsSelectedIdxs] : _qsRigData.map((_, i) => i);
  const y_mm = _QS_POS_Y[hKey];

  const promises = targets.map(idx => {
    _qsRigData[idx].y_mm = y_mm;
    return _qsApi('POST', '/update-placement', { idx, y: y_mm });
  });
  Promise.all(promises).then(() => {
    _qsRenderStageFixtureList();
    _qsDrawCanvas();
  });
}

/* ── Auto DMX ─────────────────────────────────────────────────────────── */
function qsAutoDmx() {
  _qsApi('POST', '/auto-dmx')
    .then(d => {
      if (d.error) { alert(d.error); return; }
      // Refresh rig data
      _qsRigData = (d.rig || []).map(f => ({
        ...f,
        x_mm: f.x || 0, z_mm: f.z || 0, y_mm: f.y || 0,
      }));
      _qsAssignColors();
      _qsRenderStageFixtureList();
      _qsDrawCanvas();
      const info = document.getElementById('qs-dmx-info');
      if (info) {
        info.textContent = `Auto-assigned ${d.rig.length} fixtures across ${d.universes || 1} universe(s)`;
        info.style.color = 'var(--green)';
      }
    })
    .catch(e => alert('Auto-DMX failed: ' + e));
}

/* ── Canvas drawing ───────────────────────────────────────────────────── */
function _qsDrawCanvas() {
  if (!_qsCtx || !_qsCanvas) return;
  const W = _qsCanvas.width, H = _qsCanvas.height;
  _qsCtx.clearRect(0, 0, W, H);
  if (_qsViewMode === 'top') _qsDrawTopView(W, H);
  else _qsDrawElevationView(_qsViewMode, W, H);
}

function _qsDrawTopView(W, H) {
  const ctx = _qsCtx;
  const drawW = W - _QS_MARGIN_L - _QS_MARGIN_R;
  const drawH = H - _QS_TITLE_H - _QS_MARGIN_T - _QS_MARGIN_B;
  const ox = _QS_MARGIN_L, oy = _QS_TITLE_H + _QS_MARGIN_T;

  const cBase     = _qsCv('--base');
  const cMantle   = _qsCv('--mantle');
  const cSurface1 = _qsCv('--surface1');
  const cSurface2 = _qsCv('--surface2');
  const cOverlay0 = _qsCv('--overlay0');
  const cSubtext0 = _qsCv('--subtext0');
  const cText     = _qsCv('--text');
  const cBlue     = _qsCv('--blue');

  // Background
  ctx.fillStyle = cBase;
  ctx.fillRect(0, 0, W, H);

  // Title
  ctx.fillStyle = cText;
  ctx.font = 'bold 13px monospace';
  ctx.fillText('Top View  (X → / Z ↓)', 8, 18);

  // Stage checkerboard
  const cellW = drawW / _qsStage.cols;
  const cellH = drawH / _qsStage.rows;
  for (let r = 0; r < _qsStage.rows; r++) {
    for (let c = 0; c < _qsStage.cols; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? cMantle : cBase;
      ctx.fillRect(ox + c * cellW, oy + r * cellH, cellW, cellH);
    }
  }

  // Audience band
  ctx.fillStyle = `${cBlue}22`;
  ctx.fillRect(ox, oy + drawH, drawW, 24);
  ctx.fillStyle = cBlue;
  ctx.font = '11px monospace';
  ctx.fillText('AUDIENCE', ox + drawW / 2 - 32, oy + drawH + 16);

  // SL / SR
  ctx.fillStyle = cOverlay0;
  ctx.font = '11px monospace';
  ctx.fillText('SR', ox + 4, oy + drawH / 2);
  ctx.fillText('SL', ox + drawW - 18, oy + drawH / 2);

  // Grid
  const colLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  ctx.strokeStyle = cSurface1;
  ctx.lineWidth = 0.8;
  for (let c = 0; c <= _qsStage.cols; c++) {
    const x = ox + c * cellW;
    ctx.beginPath(); ctx.moveTo(x, oy); ctx.lineTo(x, oy + drawH); ctx.stroke();
    if (c < _qsStage.cols) {
      ctx.fillStyle = cOverlay0;
      ctx.font = '9px monospace';
      ctx.fillText(colLabels[c] || String(c+1), x + cellW/2 - 4, oy - 4);
    }
  }
  for (let r = 0; r <= _qsStage.rows; r++) {
    const y = oy + r * cellH;
    ctx.beginPath(); ctx.moveTo(ox, y); ctx.lineTo(ox + drawW, y); ctx.stroke();
    if (r < _qsStage.rows) {
      ctx.fillStyle = cOverlay0;
      ctx.font = '9px monospace';
      ctx.fillText(String(r + 1), ox - 18, y + cellH/2 + 4);
    }
  }

  // Border
  ctx.strokeStyle = cSurface2;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(ox, oy, drawW, drawH);

  // Dimension labels
  ctx.fillStyle = cSubtext0;
  ctx.font = '10px monospace';
  ctx.fillText(`${(_qsStage.w_mm/1000).toFixed(1)} m`, ox + drawW / 2 - 18, oy + drawH + 36);
  ctx.save();
  ctx.translate(ox - 36, oy + drawH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(`${(_qsStage.d_mm/1000).toFixed(1)} m`, -18, 0);
  ctx.restore();

  // Fixtures
  for (let i = 0; i < _qsRigData.length; i++) {
    const f = _qsRigData[i];
    const [px, py] = _qsTopPx(f.x_mm, f.z_mm, ox, oy, drawW, drawH);
    const clr = f._color || '#888';
    const fg = _qsContrastColor(clr);
    _qsDrawDot(ctx, px, py, clr, fg, _qsSelectedIdxs.has(i));
    ctx.fillStyle = fg;
    ctx.font = '9px monospace';
    const lbl = (f.name || '').substring(0, 10);
    ctx.fillText(lbl, px - lbl.length * 2.8, py + 14);
  }
}

function _qsTopPx(x_mm, z_mm, ox, oy, drawW, drawH) {
  return [
    ox + (x_mm / _qsStage.w_mm) * drawW,
    oy + (z_mm / _qsStage.d_mm) * drawH,
  ];
}

function _qsDrawElevationView(axis, W, H) {
  const ctx = _qsCtx;
  const isfront = axis === 'front';
  const drawW = W - _QS_MARGIN_L - _QS_MARGIN_R;
  const drawH = H - _QS_TITLE_H - _QS_MARGIN_T - _QS_MARGIN_B;
  const ox = _QS_MARGIN_L, oy = _QS_TITLE_H + _QS_MARGIN_T;
  const spanMm = isfront ? _qsStage.w_mm : _qsStage.d_mm;

  const cBase     = _qsCv('--base');
  const cSurface0 = _qsCv('--surface0');
  const cSurface1 = _qsCv('--surface1');
  const cSurface2 = _qsCv('--surface2');
  const cOverlay0 = _qsCv('--overlay0');
  const cSubtext0 = _qsCv('--subtext0');
  const cText     = _qsCv('--text');

  ctx.fillStyle = cBase;
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = cText;
  ctx.font = 'bold 13px monospace';
  ctx.fillText(isfront ? 'Front View  (X → / Y ↑)' : 'Side View  (Z → / Y ↑)', 8, 18);

  // Height tier bands
  for (const tier of _QS_HEIGHT_TIERS) {
    const yBot = oy + drawH - (Math.min(tier.min, _qsStage.h_mm) / _qsStage.h_mm) * drawH;
    const yTop = oy + drawH - (Math.min(tier.max, _qsStage.h_mm) / _qsStage.h_mm) * drawH;
    ctx.fillStyle = `${cSurface0}66`;
    ctx.fillRect(ox, yTop, drawW, yBot - yTop);
    ctx.fillStyle = cOverlay0;
    ctx.font = '9px monospace';
    ctx.fillText(tier.label, ox + 4, yTop + 11);
    ctx.strokeStyle = cSurface1;
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(ox, yTop); ctx.lineTo(ox + drawW, yTop); ctx.stroke();
  }

  // Border
  ctx.strokeStyle = cSurface2;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(ox, oy, drawW, drawH);

  // Dimension labels
  ctx.fillStyle = cSubtext0;
  ctx.font = '10px monospace';
  ctx.fillText(`${(spanMm/1000).toFixed(1)} m`, ox + drawW/2 - 18, oy + drawH + 16);
  ctx.save();
  ctx.translate(ox - 36, oy + drawH/2);
  ctx.rotate(-Math.PI/2);
  ctx.fillText(`${(_qsStage.h_mm/1000).toFixed(1)} m`, -18, 0);
  ctx.restore();

  // Fixtures
  for (let i = 0; i < _qsRigData.length; i++) {
    const f = _qsRigData[i];
    const hPos = isfront ? (f.x_mm || 0) : (f.z_mm || 0);
    const px = ox + (hPos / spanMm) * drawW;
    const py = oy + drawH - ((f.y_mm || 0) / _qsStage.h_mm) * drawH;
    const clr = f._color || '#888';
    const fg = _qsContrastColor(clr);
    _qsDrawDot(ctx, px, py, clr, fg, _qsSelectedIdxs.has(i));
    ctx.fillStyle = fg;
    ctx.font = '9px monospace';
    const lbl = (f.name || '').substring(0, 10);
    ctx.fillText(lbl, px - lbl.length * 2.8, py + 14);
  }
}

function _qsDrawDot(ctx, px, py, color, fg, selected) {
  const r = selected ? 10 : 8;
  const k = 0.5523;
  ctx.beginPath();
  ctx.moveTo(px, py - r);
  ctx.bezierCurveTo(px + r*k, py - r,  px + r, py - r*k,  px + r, py);
  ctx.bezierCurveTo(px + r,   py + r*k, px + r*k, py + r,  px,     py + r);
  ctx.bezierCurveTo(px - r*k, py + r,  px - r, py + r*k,  px - r, py);
  ctx.bezierCurveTo(px - r,   py - r*k, px - r*k, py - r,  px,     py - r);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  if (selected) {
    ctx.strokeStyle = _qsCv('--pink');
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }
}

/* ── Canvas mouse interaction (drag in top view) ─────────────────────── */
function _qsCanvasXY(e) {
  const rect = _qsCanvas.getBoundingClientRect();
  return [e.clientX - rect.left, e.clientY - rect.top];
}

function _qsPixelToMm(px, py) {
  const W = _qsCanvas.width, H = _qsCanvas.height;
  const drawW = W - _QS_MARGIN_L - _QS_MARGIN_R;
  const drawH = H - _QS_TITLE_H - _QS_MARGIN_T - _QS_MARGIN_B;
  return [
    ((px - _QS_MARGIN_L) / drawW) * _qsStage.w_mm,
    ((py - (_QS_TITLE_H + _QS_MARGIN_T)) / drawH) * _qsStage.d_mm,
  ];
}

function _qsHitTest(mx, my) {
  if (_qsViewMode !== 'top') return -1;
  const W = _qsCanvas.width, H = _qsCanvas.height;
  const drawW = W - _QS_MARGIN_L - _QS_MARGIN_R;
  const drawH = H - _QS_TITLE_H - _QS_MARGIN_T - _QS_MARGIN_B;
  const ox = _QS_MARGIN_L, oy = _QS_TITLE_H + _QS_MARGIN_T;
  for (let i = _qsRigData.length - 1; i >= 0; i--) {
    const f = _qsRigData[i];
    const [px, py] = _qsTopPx(f.x_mm || 0, f.z_mm || 0, ox, oy, drawW, drawH);
    if (Math.hypot(mx - px, my - py) <= 12) return i;
  }
  return -1;
}

function _qsOnMouseDown(e) {
  if (_qsViewMode !== 'top') return;
  const [mx, my] = _qsCanvasXY(e);
  const hit = _qsHitTest(mx, my);
  if (hit >= 0) {
    // Multi-select with Shift/Ctrl/Cmd
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      if (_qsSelectedIdxs.has(hit)) _qsSelectedIdxs.delete(hit);
      else _qsSelectedIdxs.add(hit);
    } else {
      if (!_qsSelectedIdxs.has(hit)) {
        _qsSelectedIdxs.clear();
        _qsSelectedIdxs.add(hit);
      }
    }
    _qsDragIdx = hit;
    const f = _qsRigData[hit];
    const W = _qsCanvas.width, H = _qsCanvas.height;
    const drawW = W - _QS_MARGIN_L - _QS_MARGIN_R;
    const drawH = H - _QS_TITLE_H - _QS_MARGIN_T - _QS_MARGIN_B;
    const [px, py] = _qsTopPx(f.x_mm||0, f.z_mm||0, _QS_MARGIN_L, _QS_TITLE_H+_QS_MARGIN_T, drawW, drawH);
    _qsDragOffX = mx - px;
    _qsDragOffZ = my - py;
    // Store initial positions for group drag
    _qsDragStartPositions = {};
    for (const idx of _qsSelectedIdxs) {
      _qsDragStartPositions[idx] = { x: _qsRigData[idx].x_mm, z: _qsRigData[idx].z_mm };
    }
    _qsDragAnchorStart = { x: f.x_mm, z: f.z_mm };
    _qsRenderStageFixtureList();
    _qsDrawCanvas();
  } else {
    _qsSelectedIdxs.clear();
    _qsRenderStageFixtureList();
    _qsDrawCanvas();
  }
}

function _qsOnMouseMove(e) {
  if (_qsDragIdx < 0) return;
  const [mx, my] = _qsCanvasXY(e);
  const [x_mm, z_mm] = _qsPixelToMm(mx - _qsDragOffX, my - _qsDragOffZ);
  // Compute delta from anchor fixture's start position
  const newX = Math.max(0, Math.min(_qsStage.w_mm, x_mm));
  const newZ = Math.max(0, Math.min(_qsStage.d_mm, z_mm));
  if (_qsDragAnchorStart && _qsSelectedIdxs.size > 1) {
    const dx = newX - _qsDragAnchorStart.x;
    const dz = newZ - _qsDragAnchorStart.z;
    for (const idx of _qsSelectedIdxs) {
      const start = _qsDragStartPositions[idx];
      if (!start) continue;
      _qsRigData[idx].x_mm = Math.max(0, Math.min(_qsStage.w_mm, start.x + dx));
      _qsRigData[idx].z_mm = Math.max(0, Math.min(_qsStage.d_mm, start.z + dz));
    }
  } else {
    _qsRigData[_qsDragIdx].x_mm = newX;
    _qsRigData[_qsDragIdx].z_mm = newZ;
  }
  _qsDrawCanvas();
}

function _qsOnMouseUp(e) {
  if (_qsDragIdx < 0) return;
  _qsDragIdx = -1;
  _qsDragAnchorStart = null;
  // Persist all selected fixtures to server
  const toSave = _qsSelectedIdxs.size > 0 ? [..._qsSelectedIdxs] : [];
  if (toSave.length === 0) return;
  const promises = toSave.map(idx => {
    const f = _qsRigData[idx];
    return _qsApi('POST', '/update-placement', {
      idx, x: Math.round(f.x_mm), z: Math.round(f.z_mm)
    });
  });
  Promise.all(promises).then(() => { _qsRenderStageFixtureList(); });
  _qsDrawCanvas();
}


/* ── Step 3: Capability Analysis ───────────────────────────────────────── */
function qsRunAnalysis() {
  const wrap = document.getElementById('qs-analysis-result');
  if (wrap) wrap.innerHTML = '<div class="qs-loading">Analyzing fixture capabilities...</div>';
  _qsApi('GET', '/analyse')
    .then(d => {
      if (d.error) { if (wrap) wrap.innerHTML = `<div class="qs-error">${_esc(d.error)}</div>`; return; }
      let html = '<div class="qs-analysis">';
      html += '<h4>Fixture Groups</h4>';
      const groups = d.groups || {};
      for (const [key, count] of Object.entries(groups)) {
        const label = { moving_heads: 'Moving Heads', color_fixtures: 'Color Fixtures', dimmers_only: 'Dimmers', other: 'Other' }[key] || key;
        html += `<div class="qs-group-row"><span class="qs-group-label">${_esc(label)}</span> <span class="qs-group-count">${count} fixture(s)</span></div>`;
      }
      html += '<h4>Capabilities Detected</h4><ul>';
      const s = d.summary || d;
      if (s.has_any_rgb) html += '<li>RGB colour mixing</li>';
      if (s.has_any_strobe) html += '<li>Strobe / flash</li>';
      if (s.has_any_dimmer) html += '<li>Dimmer / intensity</li>';
      if (s.has_any_pan_tilt) html += '<li>Pan / tilt (moving heads)</li>';
      html += '</ul></div>';
      if (wrap) wrap.innerHTML = html;
    })
    .catch(e => { if (wrap) wrap.innerHTML = `<div class="qs-error">Analysis failed: ${_esc(String(e))}</div>`; });
}

/* ── Step 4: VC Preview ────────────────────────────────────────────────── */
function qsLoadPreview() {
  const wrap = document.getElementById('qs-vc-preview');
  if (wrap) wrap.innerHTML = '<div class="qs-loading">Generating VC layout preview...</div>';
  _qsApi('GET', '/preview')
    .then(d => {
      if (d.error) { if (wrap) wrap.innerHTML = `<div class="qs-error">${_esc(d.error)}</div>`; return; }
      let html = '<div class="qs-preview">';
      html += _qsRenderVcTree(d.vc_layout || d.vc_tree || d);
      html += '</div>';
      if (wrap) wrap.innerHTML = html;
    })
    .catch(e => { if (wrap) wrap.innerHTML = `<div class="qs-error">Preview failed: ${_esc(String(e))}</div>`; });
}

function _qsRenderVcTree(node) {
  if (!node) return '';
  let html = '';
  if (node.type === 'Frame' || node.type === 'frame') {
    html += `<div class="qs-vc-frame"><div class="qs-vc-frame-title">${_esc(node.caption || node.name || 'Frame')}</div>`;
    if (node.children) node.children.forEach(c => html += _qsRenderVcTree(c));
    html += '</div>';
  } else if (node.type === 'Button' || node.type === 'button') {
    const cls = (node.function_type === 'Chaser') ? 'qs-vc-btn-chaser' : 'qs-vc-btn-scene';
    html += `<div class="qs-vc-btn ${cls}">${_esc(node.caption || node.name || 'Button')}</div>`;
  } else if (Array.isArray(node)) {
    node.forEach(c => html += _qsRenderVcTree(c));
  } else if (node.frames) {
    node.frames.forEach(c => html += _qsRenderVcTree(c));
  } else if (node.children) {
    node.children.forEach(c => html += _qsRenderVcTree(c));
  }
  return html;
}

/* ── Step 5: Summary & Export ──────────────────────────────────────────── */
function qsLoadSummary() {
  _qsApi('GET', '/status').then(d => {
    const wrap = document.getElementById('qs-summary');
    if (!wrap) return;
    const rig = d.rig || [];
    const total_ch = rig.reduce((s, f) => s + (f.channels || 0), 0);
    const univs = d.universes || [];
    let html = '<div class="qs-summary-box">';
    html += '<h4>Ready to Export</h4>';
    html += `<p><b>Fixtures:</b> ${rig.length} total (${total_ch} DMX channels across ${univs.length || 1} universe(s))</p>`;
    if (_qsLoadedDefs.length > 0) {
      html += '<p><b>Fixture types:</b> ' + _qsLoadedDefs.map(d => `${_esc(d.manufacturer)} ${_esc(d.model)}`).join(', ') + '</p>';
    }
    html += '</div>';
    wrap.innerHTML = html;
  });
  // Hook up filename preview
  _qsUpdateFilenamePreview();
  const nameInput = document.getElementById('qs-project-name');
  if (nameInput) nameInput.addEventListener('input', _qsUpdateFilenamePreview);
}

function _qsGenerateFilename() {
  const name = (document.getElementById('qs-project-name')?.value || '').trim();
  const now = new Date();
  const ts = now.getFullYear().toString()
    + String(now.getMonth() + 1).padStart(2, '0')
    + String(now.getDate()).padStart(2, '0')
    + '_' + String(now.getHours()).padStart(2, '0')
    + String(now.getMinutes()).padStart(2, '0');
  const slug = name ? name.replace(/[^a-zA-Z0-9_\- ]/g, '').replace(/\s+/g, '_') : 'quick_start';
  return slug + '_' + ts + '.qxw';
}

function _qsUpdateFilenamePreview() {
  const el = document.getElementById('qs-filename-preview');
  if (el) el.textContent = _qsGenerateFilename();
}

async function qsExport() {
  const btn = document.getElementById('qs-btn-export');
  if (btn) { btn.disabled = true; btn.textContent = 'Generating...'; }

  const projectName = (document.getElementById('qs-project-name')?.value || '').trim();
  const suggestedName = _qsGenerateFilename();

  const params = new URLSearchParams({
    project_name: projectName,
    stage_w: _qsStage.w_mm,
    stage_d: _qsStage.d_mm,
    stage_h: _qsStage.h_mm,
  });
  const url = '/api/quickstart/generate?' + params.toString();

  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(errText || 'Server error ' + resp.status);
    }
    const blob = await resp.blob();

    const saved = await saveFileWithPicker(
      blob,
      suggestedName,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
      'Save QLC+ Workspace'
    );

    if (saved) {
      const fullPath = saveFileWithPicker.lastPath;
      const msg = fullPath
        ? 'Workspace saved to: ' + fullPath
        : 'Workspace saved as ' + saved;
      setStatus(msg, 'ok');
    }
    // saved === null means user cancelled — no message needed
  } catch (err) {
    console.error('Quick Start export failed:', err);
    setStatus('Export failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Export .qxw'; }
  }
}
