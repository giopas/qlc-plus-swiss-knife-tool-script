/* =============================================================================
   fixture.js — Fixture Configurator tab (full canvas configurator)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _rig         = [];          // [{idx, name, manufacturer, model, mode, ch_count, role,
                                //   universe, address, x_mm, z_mm, y_mm, color, grid, h_role}]
let _qxfDefs     = [];          // [{key, manufacturer, model, type, modes:[{name,channels}]}]
let _stage       = { w_mm: 8000, d_mm: 6000, h_mm: 4000, cols: 8, rows: 6 };
let _viewMode    = 'top';       // 'top' | 'front' | 'side'
let _snapEnabled = true;
let _selectedIdx = -1;          // index into _rig[]
let _fixLoaded   = false;

// Canvas drag state
let _dragIdx     = -1;
let _dragOffX    = 0;
let _dragOffZ    = 0;
let _canvas      = null;
let _ctx         = null;

// Color palette (one per unique model)
const _PALETTE = [
  '#00e5ff','#ff007f','#39ff14','#ffff00',
  '#ff8c00','#b026ff','#ff3333','#00ff99',
  '#ff66cc','#33ccff',
];
let _modelColorMap = {};

// Height tiers for elevation views
const _HEIGHT_TIERS = [
  { label: 'Floor',    min: 0,    max: 500  },
  { label: 'Low-Mid',  min: 500,  max: 1500 },
  { label: 'Mid',      min: 1500, max: 2500 },
  { label: 'Top-Mid',  min: 2500, max: 3500 },
  { label: 'Top',      min: 3500, max: Infinity },
];


// ── Public API ────────────────────────────────────────────────────────────────

function invalidateFixtures() {
  _fixLoaded   = false;
  _rig         = [];
  _selectedIdx = -1;
  // Clear the server-side configurator rig so next visit re-imports from new workspace
  fetch('/api/fixture/configurator/clear', { method: 'POST' }).catch(() => {});
  _renderRigTable();
  if (_canvas) _drawCanvas();
}

async function ensureFixturesLoaded() {
  if (_fixLoaded) return;
  _fixLoaded = true;
  await _initConfigurator();
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function _initConfigurator() {
  _canvas = document.getElementById('fix-canvas');
  if (!_canvas) return;
  _ctx = _canvas.getContext('2d');
  _resizeCanvas();
  if (!_canvas._roAttached) {
    const ro = new ResizeObserver(() => { _resizeCanvas(); _drawCanvas(); });
    ro.observe(_canvas.parentElement);
    _canvas._roAttached = true;
  }
  _canvas.addEventListener('mousedown',  _onCanvasMouseDown);
  _canvas.addEventListener('mousemove',  _onCanvasMouseMove);
  _canvas.addEventListener('mouseup',    _onCanvasMouseUp);
  _canvas.addEventListener('mouseleave', _onCanvasMouseUp);

  await Promise.all([_fetchQxfDefs(), _fetchStage()]);
  await _fetchRig();          // fetch rig after stage so dims are ready

  // Auto-populate from workspace if configurator rig is still empty
  if (_rig.length === 0) {
    const status = await _apiJson('/api/status');
    if (status.loaded) {
      const res = await _apiPost('/api/fixture/configurator/import-from-workspace', {});
      if (res.rig && res.rig.length) {
        _rig   = res.rig;
        _stage = { ..._stage, ...(res.stage || {}) };
        _assignColors();
        _syncStageFields();
        setStatus(`Auto-imported ${_rig.length} fixture(s) from workspace.`, 'ok');
      }
    }
  }

  _syncStageFields();
  _renderRigTable();
  _drawCanvas();
}

// ── Data fetching ─────────────────────────────────────────────────────────────

async function _fetchRig() {
  const data = await _apiJson('/api/fixture/configurator/rig');
  if (Array.isArray(data)) {
    _rig = data;
    _assignColors();
  }
}

async function _fetchQxfDefs() {
  const data = await _apiJson('/api/fixture/configurator/qxf-defs');
  if (Array.isArray(data)) _qxfDefs = data;
  _populateTypeDropdown();
}

async function _fetchStage() {
  const data = await _apiJson('/api/fixture/configurator/stage');
  if (data && !data.error) {
    _stage = { w_mm: data.w_mm, d_mm: data.d_mm, h_mm: data.h_mm,
               cols: data.cols, rows: data.rows };
  }
}

function _assignColors() {
  let colorIdx = 0;
  for (const f of _rig) {
    const key = f.model || f.manufacturer || 'Unknown';
    if (!_modelColorMap[key]) {
      _modelColorMap[key] = _PALETTE[colorIdx % _PALETTE.length];
      colorIdx++;
    }
    f.color = f.color || _modelColorMap[key];
  }
}

// ── Stage fields sync ─────────────────────────────────────────────────────────

function _syncStageFields() {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  set('fix-stage-w', _stage.w_mm);
  set('fix-stage-d', _stage.d_mm);
  set('fix-stage-h', _stage.h_mm);
  set('fix-grid-cols', _stage.cols);
  set('fix-grid-rows', _stage.rows);
}

async function _applyStageFields() {
  const get = id => parseInt(document.getElementById(id)?.value || 0);
  const body = { w_mm: get('fix-stage-w'), d_mm: get('fix-stage-d'),
                 h_mm: get('fix-stage-h'), cols: get('fix-grid-cols'),
                 rows: get('fix-grid-rows') };
  const res = await _apiPost('/api/fixture/configurator/stage', body);
  if (res.ok) {
    _stage = { w_mm: res.w_mm, d_mm: res.d_mm, h_mm: res.h_mm,
               cols: res.cols, rows: res.rows };
    _drawCanvas();
  }
}

function _bindStageFields() {
  ['fix-stage-w','fix-stage-d','fix-stage-h','fix-grid-cols','fix-grid-rows'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', _applyStageFields);
  });
}

// ── QXF / Import ──────────────────────────────────────────────────────────────

async function fixLoadQxf() {
  const inp = document.getElementById('fix-qxf-path');
  const path = (inp?.value || '').trim();
  if (!path) { setStatus('Enter a QXF file path.', 'error'); return; }
  const res = await _apiPost('/api/fixture/configurator/load-qxf', { path });
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(`Loaded: ${res.definition.manufacturer} ${res.definition.model}`, 'ok');
  await _fetchQxfDefs();
  _drawCanvas();
}

async function fixImportWorkspace() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('Load a workspace first.', 'error'); return; }
  const res = await _apiPost('/api/fixture/configurator/import-from-workspace', {});
  if (res.error) { setStatus(res.error, 'error'); return; }
  _rig = res.rig || [];
  _stage = res.stage || _stage;
  _assignColors();
  _syncStageFields();
  _renderRigTable();
  _drawCanvas();
  setStatus(`Imported ${_rig.length} fixture(s) from workspace.`, 'ok');
}

// ── View selector ─────────────────────────────────────────────────────────────

function fixSetView(mode) {
  _viewMode = mode;
  ['top','front','side'].forEach(m => {
    const btn = document.getElementById(`fix-btn-view-${m}`);
    if (btn) btn.classList.toggle('btn-view-active', m === mode);
  });
  _drawCanvas();
}

// ── Rig table ─────────────────────────────────────────────────────────────────

function _renderRigTable() {
  const wrap = document.getElementById('fix-rig-table-wrap');
  if (!wrap) return;
  if (!_rig.length) {
    wrap.innerHTML = '<p class="empty-msg">No fixtures. Add one or import from workspace.</p>';
    return;
  }
  const rows = _rig.map((f, i) => {
    const sel  = i === _selectedIdx ? ' row-active' : '';
    const dot  = `<span class="fix-color-dot" style="background:${_te(f.color||'#888')}"></span>`;
    const univ = f.universe != null ? f.universe : '—';
    const addr = f.address  != null ? f.address  : '—';
    const grid = f.grid || '—';
    return `<tr class="fix-rig-row${sel}" data-idx="${i}" onclick="fixSelectRow(${i})">
      <td>${dot}</td>
      <td>${_te(f.name||'')}</td>
      <td>${_te(f.model||'')}</td>
      <td>${_te(f.mode||'')}</td>
      <td>${f.ch_count||''}</td>
      <td>U${univ}.${String(addr).padStart(3,'0')}</td>
      <td>${_te(grid)}</td>
      <td>${_te(f.role||'')}</td>
    </tr>`;
  }).join('');
  wrap.innerHTML = `
    <table class="fix-rig-table">
      <thead><tr>
        <th></th><th>Name</th><th>Model</th><th>Mode</th>
        <th>Ch</th><th>Patch</th><th>Grid</th><th>Role</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function fixSelectRow(idx) {
  _selectedIdx = idx;
  _renderRigTable();
  _drawCanvas();
}

// ── Add / Remove / Move / AutoDMX ─────────────────────────────────────────────

async function fixRemoveSelected() {
  if (_selectedIdx < 0 || _selectedIdx >= _rig.length) return;
  const res = await _apiDelete(`/api/fixture/configurator/${_selectedIdx}`);
  if (res.error) { setStatus(res.error, 'error'); return; }
  _rig = res.rig || [];
  _assignColors();
  _selectedIdx = Math.min(_selectedIdx, _rig.length - 1);
  _renderRigTable();
  _drawCanvas();
}

async function fixMoveRow(dir) {
  if (_selectedIdx < 0) return;
  const res = await _apiPost('/api/fixture/configurator/move', { idx: _selectedIdx, direction: dir });
  if (res.error) { setStatus(res.error, 'error'); return; }
  _rig = res.rig || [];
  _assignColors();
  _selectedIdx = Math.max(0, Math.min(_selectedIdx + dir, _rig.length - 1));
  _renderRigTable();
  _drawCanvas();
}

async function fixAutoDmx() {
  const res = await _apiPost('/api/fixture/configurator/auto-dmx', {});
  if (res.error) { setStatus(res.error, 'error'); return; }
  _rig = res.rig || [];
  _assignColors();
  _renderRigTable();
  _drawCanvas();
  setStatus('DMX addresses auto-assigned.', 'ok');
}

// ── Add fixture dialog ────────────────────────────────────────────────────────

function _populateTypeDropdown() {
  const sel = document.getElementById('fix-add-type');
  if (!sel) return;
  const cur = sel.value;
  // Group by manufacturer
  const byMfg = {};
  for (const d of _qxfDefs) {
    const g = d.manufacturer || 'Unknown';
    if (!byMfg[g]) byMfg[g] = [];
    byMfg[g].push(d);
  }
  let html = '<option value="">— Select type —</option>';
  for (const [mfg, defs] of Object.entries(byMfg).sort()) {
    html += `<optgroup label="${_te(mfg)}">`;
    for (const d of defs)
      html += `<option value="${_te(d.key)}">${_te(d.model)}</option>`;
    html += '</optgroup>';
  }
  sel.innerHTML = html;
  if (cur) sel.value = cur;
}

function fixAddDialog() {
  const modal = document.getElementById('fix-add-modal');
  if (!modal) return;
  // Reset fields
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  set('fix-add-type', '');
  set('fix-add-mode', '');
  set('fix-add-name', '');
  set('fix-add-mfg',  '');
  set('fix-add-model','');
  set('fix-add-universe', 1);
  set('fix-add-address',  1);
  set('fix-add-channels', 1);
  set('fix-add-count',    1);
  set('fix-add-role',    'Custom');
  const modeWrap = document.getElementById('fix-add-mode-wrap');
  if (modeWrap) modeWrap.innerHTML = '<select id="fix-add-mode" class="input-sm"><option value="">— Select mode —</option></select>';
  modal.style.display = 'flex';
}

function fixAddModalClose() {
  const modal = document.getElementById('fix-add-modal');
  if (modal) modal.style.display = 'none';
}

function fixAddTypeChanged() {
  const sel  = document.getElementById('fix-add-type');
  const key  = sel?.value || '';
  const def  = _qxfDefs.find(d => d.key === key);
  const modeWrap = document.getElementById('fix-add-mode-wrap');

  if (!def) {
    if (modeWrap) modeWrap.innerHTML = '<select id="fix-add-mode" class="input-sm"><option value="">— Select mode —</option></select>';
    return;
  }
  // Fill mfg / model name
  const setv = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setv('fix-add-mfg',   def.manufacturer || '');
  setv('fix-add-model', def.model || '');
  if (!document.getElementById('fix-add-name')?.value)
    setv('fix-add-name', def.model || '');

  // Mode dropdown
  const modes = def.modes || [];
  let opts = '<option value="">— Select mode —</option>';
  for (const m of modes) opts += `<option value="${_te(m.name)}" data-ch="${m.channels}">${_te(m.name)} (${m.channels} ch)</option>`;
  if (modeWrap) modeWrap.innerHTML = `<select id="fix-add-mode" class="input-sm" onchange="fixAddModeChanged()">${opts}</select>`;
  if (modes.length === 1) {
    document.getElementById('fix-add-mode').value = modes[0].name;
    fixAddModeChanged();
  }
}

function fixAddModeChanged() {
  const sel = document.getElementById('fix-add-mode');
  if (!sel) return;
  const opt = sel.options[sel.selectedIndex];
  const ch  = opt?.dataset?.ch;
  if (ch) { const el = document.getElementById('fix-add-channels'); if (el) el.value = ch; }
}

async function fixAddConfirm() {
  const get  = id => (document.getElementById(id)?.value || '').trim();
  const geti = id => parseInt(document.getElementById(id)?.value || 0);

  const type  = get('fix-add-type');
  const mode  = get('fix-add-mode');
  const name  = get('fix-add-name');
  const mfg   = get('fix-add-mfg')   || (type ? (_qxfDefs.find(d=>d.key===type)?.manufacturer||'') : 'Generic');
  const model = get('fix-add-model') || name;
  const count = Math.max(1, geti('fix-add-count'));

  if (!name)  { setStatus('Name is required.', 'error'); return; }

  const universe = geti('fix-add-universe');
  const address  = geti('fix-add-address');

  for (let i = 0; i < count; i++) {
    const body = {
      manufacturer: mfg,
      model:        model,
      mode:         mode || 'Default',
      ch_count:     geti('fix-add-channels'),
      name:         count > 1 ? `${name} ${i+1}` : name,
      role:         get('fix-add-role') || 'Custom',
      universe,
      address: address + i * geti('fix-add-channels'),
      x_mm: 0, z_mm: 0, y_mm: 0,
    };
    const res = await _apiPost('/api/fixture/configurator/add', body);
    if (res.error) { setStatus(res.error, 'error'); return; }
    _rig = res.rig || _rig;
  }
  _assignColors();
  fixAddModalClose();
  _renderRigTable();
  _drawCanvas();
  setStatus(`Added ${count} fixture(s).`, 'ok');
}

// ── Generate QXW ──────────────────────────────────────────────────────────────

async function fixGenerateQxw() {
  if (!_rig.length) { setStatus('Rig is empty.', 'error'); return; }
  try {
    const resp = await fetch('/api/fixture/configurator/generate-qxw', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    if (!resp.ok) { const e = await resp.json(); setStatus(e.error || 'Error', 'error'); return; }
    const blob = await resp.blob();
    const cd   = resp.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename=([^\s;]+)/);
    const name = m ? m[1] : 'rig.qxw';
    _downloadBlob(blob, name);
    setStatus('QXW downloaded.', 'ok');
  } catch (err) { setStatus(String(err), 'error'); }
}

// ── Export Blueprint PDF ──────────────────────────────────────────────────────

async function fixExportPdf() {
  const showName = prompt('Show name for PDF:', 'My Show') || 'Untitled';
  const paperSel = document.getElementById('fix-pdf-paper');
  const paper    = paperSel?.value || 'A3 Landscape';
  try {
    const resp = await fetch('/api/fixture/configurator/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_name: showName, paper }),
    });
    if (!resp.ok) { const e = await resp.json(); setStatus(e.error || 'Error', 'error'); return; }
    const blob = await resp.blob();
    _downloadBlob(blob, 'blueprint.pdf');
    setStatus(`Blueprint PDF (${paper}) downloaded.`, 'ok');
  } catch (err) { setStatus(String(err), 'error'); }
}

function _downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ── Canvas resize ─────────────────────────────────────────────────────────────

function _resizeCanvas() {
  if (!_canvas) return;
  const pane = _canvas.parentElement;
  _canvas.width  = pane.clientWidth  || 600;
  _canvas.height = pane.clientHeight || 400;
}

// ── CSS variable reader (theme-aware canvas colors) ───────────────────────────

function _cv(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || '#888';
}

// ── Canvas draw dispatcher ────────────────────────────────────────────────────

function _drawCanvas() {
  if (!_ctx || !_canvas) return;
  const W = _canvas.width, H = _canvas.height;
  _ctx.clearRect(0, 0, W, H);

  if (_viewMode === 'top')   _drawTopView(W, H);
  else                       _drawElevationView(_viewMode, W, H);
}

// ── Top view (X vs Z, looking down) ──────────────────────────────────────────

const _TITLE_H  = 28;
const _MARGIN_L = 48;
const _MARGIN_R = 16;
const _MARGIN_T = 16;
const _MARGIN_B = 40;

function _drawTopView(W, H) {
  const ctx   = _ctx;
  const drawW = W - _MARGIN_L - _MARGIN_R;
  const drawH = H - _TITLE_H - _MARGIN_T - _MARGIN_B;
  const ox = _MARGIN_L, oy = _TITLE_H + _MARGIN_T;

  // Resolve theme colors at draw time
  const cBase    = _cv('--base');
  const cMantle  = _cv('--mantle');
  const cSurface0= _cv('--surface0');
  const cSurface1= _cv('--surface1');
  const cSurface2= _cv('--surface2');
  const cOverlay0= _cv('--overlay0');
  const cSubtext0= _cv('--subtext0');
  const cText    = _cv('--text');
  const cBlue    = _cv('--blue');

  // Background
  ctx.fillStyle = cBase;
  ctx.fillRect(0, 0, W, H);

  // Title
  ctx.fillStyle = cText;
  ctx.font = 'bold 13px monospace';
  ctx.fillText('Top View  (X → / Z ↓)', 8, 18);

  // Stage area (checkerboard cells)
  const cellW = drawW / _stage.cols;
  const cellH = drawH / _stage.rows;
  for (let r = 0; r < _stage.rows; r++) {
    for (let c = 0; c < _stage.cols; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? cMantle : cBase;
      ctx.fillRect(ox + c * cellW, oy + r * cellH, cellW, cellH);
    }
  }

  // Audience band at bottom
  ctx.fillStyle = `${cBlue}22`;
  ctx.fillRect(ox, oy + drawH, drawW, 24);
  ctx.fillStyle = cBlue;
  ctx.font = '11px monospace';
  ctx.fillText('AUDIENCE', ox + drawW / 2 - 32, oy + drawH + 16);

  // SL / SR labels
  ctx.fillStyle = cOverlay0;
  ctx.font = '11px monospace';
  ctx.fillText('SR', ox + 4, oy + drawH / 2);
  ctx.fillText('SL', ox + drawW - 18, oy + drawH / 2);

  // Grid lines + column labels (A–Z)
  const colLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  ctx.strokeStyle = cSurface1;
  ctx.lineWidth = 0.8;
  for (let c = 0; c <= _stage.cols; c++) {
    const x = ox + c * cellW;
    ctx.beginPath(); ctx.moveTo(x, oy); ctx.lineTo(x, oy + drawH); ctx.stroke();
    if (c < _stage.cols) {
      ctx.fillStyle = cOverlay0;
      ctx.font = '9px monospace';
      ctx.fillText(colLabels[c] || String(c+1), x + cellW/2 - 4, oy - 4);
    }
  }
  for (let r = 0; r <= _stage.rows; r++) {
    const y = oy + r * cellH;
    ctx.beginPath(); ctx.moveTo(ox, y); ctx.lineTo(ox + drawW, y); ctx.stroke();
    if (r < _stage.rows) {
      ctx.fillStyle = cOverlay0;
      ctx.font = '9px monospace';
      ctx.fillText(String(r + 1), ox - 18, y + cellH/2 + 4);
    }
  }

  // Stage border
  ctx.strokeStyle = cSurface2;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(ox, oy, drawW, drawH);

  // Dimension labels
  ctx.fillStyle = cSubtext0;
  ctx.font = '10px monospace';
  ctx.fillText(`${(_stage.w_mm/1000).toFixed(1)} m`, ox + drawW / 2 - 18, oy + drawH + 36);
  ctx.save();
  ctx.translate(ox - 36, oy + drawH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(`${(_stage.d_mm/1000).toFixed(1)} m`, -18, 0);
  ctx.restore();

  // Fixtures
  for (let i = 0; i < _rig.length; i++) {
    const f   = _rig[i];
    const [px, py] = _topViewPx(f.x_mm || 0, f.z_mm || 0, ox, oy, drawW, drawH);
    const clr = f.color || '#888';
    const fg  = _contrastColor(clr);
    _drawFixtureDot(ctx, px, py, clr, fg, i === _selectedIdx);
    ctx.fillStyle = fg;
    ctx.font = '9px monospace';
    const lbl = (f.name || '').substring(0, 10);
    ctx.fillText(lbl, px - lbl.length * 2.8, py + 14);
    if (f.grid) {
      ctx.fillStyle = cSubtext0;
      ctx.font = '8px monospace';
      ctx.fillText(f.grid, px - 6, py - 12);
    }
  }
}

function _topViewPx(x_mm, z_mm, ox, oy, drawW, drawH) {
  const px = ox + (x_mm / _stage.w_mm) * drawW;
  const py = oy + (z_mm / _stage.d_mm) * drawH;
  return [px, py];
}

// ── Elevation views (front = X vs Y, side = Z vs Y) ──────────────────────────

function _drawElevationView(axis, W, H) {
  const ctx = _ctx;
  const isfront = axis === 'front';
  const drawW = W - _MARGIN_L - _MARGIN_R;
  const drawH = H - _TITLE_H - _MARGIN_T - _MARGIN_B;
  const ox = _MARGIN_L, oy = _TITLE_H + _MARGIN_T;
  const spanMm = isfront ? _stage.w_mm : _stage.d_mm;

  const cBase    = _cv('--base');
  const cSurface0= _cv('--surface0');
  const cSurface1= _cv('--surface1');
  const cSurface2= _cv('--surface2');
  const cOverlay0= _cv('--overlay0');
  const cSubtext0= _cv('--subtext0');
  const cText    = _cv('--text');

  ctx.fillStyle = cBase;
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = cText;
  ctx.font = 'bold 13px monospace';
  ctx.fillText(isfront ? 'Front View  (X → / Y ↑)' : 'Side View  (Z → / Y ↑)', 8, 18);

  // Height tier bands
  for (const tier of _HEIGHT_TIERS) {
    const yBot = oy + drawH - (Math.min(tier.min, _stage.h_mm) / _stage.h_mm) * drawH;
    const yTop = oy + drawH - (Math.min(tier.max, _stage.h_mm) / _stage.h_mm) * drawH;
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
  ctx.fillText(`${(_stage.h_mm/1000).toFixed(1)} m`, -18, 0);
  ctx.restore();

  // Fixtures
  for (let i = 0; i < _rig.length; i++) {
    const f   = _rig[i];
    const hPos = isfront ? (f.x_mm || 0) : (f.z_mm || 0);
    const px   = ox + (hPos / spanMm)       * drawW;
    const py   = oy + drawH - ((f.y_mm || 0) / _stage.h_mm) * drawH;
    const clr  = f.color || '#888';
    const fg   = _contrastColor(clr);
    _drawFixtureDot(ctx, px, py, clr, fg, i === _selectedIdx);
    ctx.fillStyle = fg;
    ctx.font = '9px monospace';
    const lbl = (f.name || '').substring(0, 10);
    ctx.fillText(lbl, px - lbl.length * 2.8, py + 14);
  }
}

// ── Fixture dot (bezier circle) ───────────────────────────────────────────────

function _drawFixtureDot(ctx, px, py, color, fg, selected) {
  const r   = selected ? 10 : 8;
  const k   = 0.5523;
  ctx.beginPath();
  ctx.moveTo(px, py - r);
  ctx.bezierCurveTo(px + r*k, py - r,  px + r, py - r*k,  px + r, py);
  ctx.bezierCurveTo(px + r,   py + r*k, px + r*k, py + r,  px,     py + r);
  ctx.bezierCurveTo(px - r*k, py + r,  px - r, py + r*k,  px - r, py);
  ctx.bezierCurveTo(px - r,   py - r*k, px - r*k, py - r,  px,     py - r);
  ctx.closePath();
  ctx.fillStyle   = color;
  ctx.fill();
  if (selected) {
    ctx.strokeStyle = _cv('--pink');
    ctx.lineWidth   = 2.5;
    ctx.stroke();
  }
}

// ── Canvas drag ───────────────────────────────────────────────────────────────

function _onCanvasMouseDown(e) {
  if (_viewMode !== 'top') return;
  const [mx, my] = _canvasXY(e);
  const hit = _hitTest(mx, my);
  if (hit >= 0) {
    _dragIdx     = hit;
    _selectedIdx = hit;
    const f     = _rig[hit];
    const W = _canvas.width, H = _canvas.height;
    const drawW = W - _MARGIN_L - _MARGIN_R;
    const drawH = H - _TITLE_H - _MARGIN_T - _MARGIN_B;
    const [px, py] = _topViewPx(f.x_mm || 0, f.z_mm || 0, _MARGIN_L, _TITLE_H + _MARGIN_T, drawW, drawH);
    _dragOffX = mx - px;
    _dragOffZ = my - py;
    _renderRigTable();
    _drawCanvas();
  }
}

function _onCanvasMouseMove(e) {
  if (_dragIdx < 0) return;
  const [mx, my] = _canvasXY(e);
  const [x_mm, z_mm] = _pixelToMm(mx - _dragOffX, my - _dragOffZ);
  const f = _rig[_dragIdx];
  f.x_mm = Math.max(0, Math.min(_stage.w_mm, x_mm));
  f.z_mm = Math.max(0, Math.min(_stage.d_mm, z_mm));
  _drawCanvas();
}

async function _onCanvasMouseUp(e) {
  if (_dragIdx < 0) return;
  const idx = _dragIdx;
  _dragIdx = -1;
  const f = _rig[idx];

  // Always PATCH the dragged position to the server first so snap and
  // grid-cell computation use the new coordinates, not the original ones.
  const patchRes = await _apiPatch(`/api/fixture/configurator/${idx}`,
    { x_mm: Math.round(f.x_mm), z_mm: Math.round(f.z_mm) });

  if (_snapEnabled) {
    // Snap to nearest grid intersection (server re-reads the patched pos)
    const res = await _apiPost(`/api/fixture/configurator/snap`, { idx });
    if (res.rig) { _rig = res.rig; _assignColors(); }
    else if (res.ok) { f.x_mm = res.x_mm; f.z_mm = res.z_mm; }
  } else {
    // Re-fetch full rig so grid column gets recomputed from new position
    const updRes = await _apiJson('/api/fixture/configurator/rig');
    if (Array.isArray(updRes)) { _rig = updRes; _assignColors(); }
  }
  _renderRigTable();
  _drawCanvas();
}

function _canvasXY(e) {
  const rect = _canvas.getBoundingClientRect();
  return [e.clientX - rect.left, e.clientY - rect.top];
}

function _pixelToMm(px, py) {
  const W = _canvas.width, H = _canvas.height;
  const drawW = W - _MARGIN_L - _MARGIN_R;
  const drawH = H - _TITLE_H - _MARGIN_T - _MARGIN_B;
  const ox = _MARGIN_L, oy = _TITLE_H + _MARGIN_T;
  return [
    ((px - ox) / drawW) * _stage.w_mm,
    ((py - oy) / drawH) * _stage.d_mm,
  ];
}

function _hitTest(mx, my) {
  if (_viewMode !== 'top') return -1;
  const W = _canvas.width, H = _canvas.height;
  const drawW = W - _MARGIN_L - _MARGIN_R;
  const drawH = H - _TITLE_H - _MARGIN_T - _MARGIN_B;
  for (let i = _rig.length - 1; i >= 0; i--) {
    const f = _rig[i];
    const [px, py] = _topViewPx(f.x_mm || 0, f.z_mm || 0, _MARGIN_L, _TITLE_H + _MARGIN_T, drawW, drawH);
    if (Math.hypot(mx - px, my - py) <= 12) return i;
  }
  return -1;
}

// ── Snap toggle ───────────────────────────────────────────────────────────────

function fixToggleSnap() {
  _snapEnabled = !_snapEnabled;
  const btn = document.getElementById('fix-btn-snap');
  if (btn) btn.classList.toggle('btn-view-active', _snapEnabled);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _contrastColor(hex) {
  const r = parseInt(hex.slice(1,3),16)||0;
  const g = parseInt(hex.slice(3,5),16)||0;
  const b = parseInt(hex.slice(5,7),16)||0;
  return (r*299 + g*587 + b*114) / 1000 > 128 ? '#11111b' : '#cdd6f4';
}

function _te(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function _apiPost(url, body) {
  try {
    const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    return await r.json();
  } catch(e) { return {error: String(e)}; }
}

async function _apiPatch(url, body) {
  try {
    const r = await fetch(url, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    return await r.json();
  } catch(e) { return {error: String(e)}; }
}

async function _apiDelete(url) {
  try {
    const r = await fetch(url, { method:'DELETE' });
    return await r.json();
  } catch(e) { return {error: String(e)}; }
}

// ── Rig-pane drag-resize ──────────────────────────────────────────────────────
// The handle sits between .fix-rig-pane (fixed width, left) and
// .fix-canvas-pane (flex:1, right).  We resize the RIG pane; the canvas pane
// automatically fills the remaining space via flex:1, and its ResizeObserver
// fires _resizeCanvas() + _drawCanvas() so the stage always fills the canvas.

function _initCanvasResize() {
  const handle  = document.getElementById('fix-canvas-resize-handle');
  const rigPane = document.querySelector('.fix-rig-pane');
  if (!handle || !rigPane) return;

  let startX = 0, startW = 0;
  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startX = e.clientX;
    startW = rigPane.getBoundingClientRect().width;

    const onMove = ev => {
      // drag right → wider rig pane (canvas shrinks)
      // drag left  → narrower rig pane (canvas grows)
      const delta = ev.clientX - startX;
      const newW  = Math.max(180, Math.min(700, startW + delta));
      rigPane.style.flex  = `0 0 ${newW}px`;
      rigPane.style.width = `${newW}px`;
      // ResizeObserver on canvas parent fires automatically, but call
      // explicitly too for snappy feedback before the observer fires.
      _resizeCanvas();
      _drawCanvas();
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  _bindStageFields();
  _initCanvasResize();
  // Init snap button state
  const btn = document.getElementById('fix-btn-snap');
  if (btn) btn.classList.toggle('btn-view-active', _snapEnabled);
  // Default view button
  const defBtn = document.getElementById('fix-btn-view-top');
  if (defBtn) defBtn.classList.add('btn-view-active');
});
