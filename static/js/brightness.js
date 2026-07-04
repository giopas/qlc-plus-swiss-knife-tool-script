/* =============================================================================
   brightness.js — Per-fixture brightness scaling tab
   =============================================================================
   Lets the user scale the Master Dimmer channel of each fixture (or fixture
   group) across every Scene in the loaded workspace, then download a new QXW.
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _brtFixtures   = [];          // [{id,name,manufacturer,model,mode,dimmer_offset,...}]
let _brtLoaded     = false;
let _brtScales     = {};          // fixture_id → scale (0.0–2.0, default 1.0)
let _brtManual     = {};          // fixture_id → dimmer_offset (for QXF-not-found fixtures)
let _brtLinked     = {};          // model_key  → bool (true = sliders move together)
let _brtPreviewTm  = null;        // debounce timer for preview

// ── Public API (called from app.js) ──────────────────────────────────────────

function invalidateBrightness() {
  _brtLoaded   = false;
  _brtFixtures = [];
  _brtScales   = {};
  _brtManual   = {};
  _brtLinked   = {};
  const wrap = document.getElementById('brt-fixture-wrap');
  if (wrap) wrap.innerHTML = '<div class="brt-placeholder">Load a workspace to adjust brightness.</div>';
  _brtSetPreview(null);
}

async function ensureBrightnessLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_brtLoaded) return;
  _brtLoaded = true;
  await _brtLoadFixtures();
}

// ── Data ─────────────────────────────────────────────────────────────────────

async function _brtLoadFixtures() {
  const data = await _apiJson('/api/brightness/fixtures');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _brtFixtures = Array.isArray(data) ? data : [];

  // Initialise scales to 1.0 and link state per model group
  const seen = {};
  for (const fx of _brtFixtures) {
    if (!(_brtScales[fx.id] !== undefined)) _brtScales[fx.id] = 1.0;
    const mk = _brtModelKey(fx);
    if (!seen[mk]) { seen[mk] = true; _brtLinked[mk] = true; }
  }
  _brtRender();
}

function _brtModelKey(fx) {
  return `${fx.manufacturer}||${fx.model}||${fx.mode}`;
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function _brtRender() {
  const wrap = document.getElementById('brt-fixture-wrap');
  if (!wrap) return;

  if (!_brtFixtures.length) {
    wrap.innerHTML = '<div class="brt-placeholder">No fixtures found in the loaded workspace.</div>';
    return;
  }

  // Group by manufacturer/model/mode
  const groups = {};
  for (const fx of _brtFixtures) {
    const mk = _brtModelKey(fx);
    if (!groups[mk]) groups[mk] = { fixtures: [], mk };
    groups[mk].fixtures.push(fx);
  }

  let html = '';
  for (const mk of Object.keys(groups)) {
    const grp = groups[mk];
    const fx0 = grp.fixtures[0];
    const linked = _brtLinked[mk] !== false;
    const noQxf  = !fx0.qxf_found;

    // Compute group representative scale (average of linked fixtures)
    const grpScale = linked
      ? grp.fixtures.reduce((s, f) => s + (_brtScales[f.id] ?? 1), 0) / grp.fixtures.length
      : (_brtScales[fx0.id] ?? 1);

    const pct  = Math.round(grpScale * 100);
    const mkSafe = _esc(mk);

    html += `
    <div class="brt-group" data-model="${mkSafe}">
      <div class="brt-group-header">
        <span class="brt-group-name">
          <strong>${_esc(fx0.manufacturer)} ${_esc(fx0.model)}</strong>
          <span class="brt-group-mode">${_esc(fx0.mode)}</span>
          ${noQxf ? `<span class="brt-badge brt-badge-warn" title="QXF fixture file not found — set dimmer offset manually">⚠ No QXF</span>` : ''}
        </span>
        <label class="brt-link-label" title="Move all fixtures in this group together">
          <input type="checkbox" class="brt-link-cb"
                 data-model="${mkSafe}"
                 ${linked ? 'checked' : ''}
                 onchange="brtToggleLink(this)">
          Link group
        </label>
        ${linked ? `
        <div class="brt-slider-row brt-group-slider">
          <input type="range"  min="0" max="200" step="1"
                 value="${pct}"
                 class="brt-slider"
                 data-model="${mkSafe}" data-linked="1"
                 oninput="brtGroupSlider(this)">
          <input type="number" min="0" max="200" step="1"
                 value="${pct}"
                 class="brt-num"
                 data-model="${mkSafe}" data-linked="1"
                 oninput="brtGroupNum(this)">
          <span class="brt-pct-label">%</span>
          <button class="btn btn-surface brt-reset-btn"
                  title="Reset group to 100%"
                  onclick="brtResetGroup('${mkSafe}')">↺</button>
        </div>` : ''}
      </div>
      <div class="brt-fixture-list ${linked ? 'brt-list-linked' : ''}">`;

    for (const fx of grp.fixtures) {
      const fPct  = Math.round((_brtScales[fx.id] ?? 1) * 100);
      const doff  = fx.dimmer_offset ?? _brtManual[fx.id] ?? '';
      const chInfo = fx.dimmer_offset !== null && fx.dimmer_offset !== undefined
        ? `ch&nbsp;${fx.dimmer_offset}&nbsp;·&nbsp;${fx.channels}&nbsp;ch&nbsp;mode`
        : `<span class="brt-ch-unknown">dimmer ch unknown</span>`;

      html += `
        <div class="brt-fixture-row" data-id="${_esc(fx.id)}">
          <span class="brt-fx-name">${_esc(fx.name)}</span>
          <span class="brt-fx-info">${chInfo}</span>
          ${noQxf ? `
          <label class="brt-manual-label" title="Enter the 0-indexed DMX channel offset for the Master Dimmer">
            Dimmer ch:
            <input type="number" min="0" max="511" step="1"
                   class="brt-manual-ch"
                   value="${_esc(doff)}"
                   data-id="${_esc(fx.id)}"
                   oninput="brtSetManual(this)">
          </label>` : ''}
          <div class="brt-slider-row" style="${linked ? 'opacity:0.45;pointer-events:none' : ''}">
            <input type="range"  min="0" max="200" step="1"
                   value="${fPct}"
                   class="brt-slider"
                   data-id="${_esc(fx.id)}"
                   oninput="brtFixtureSlider(this)">
            <input type="number" min="0" max="200" step="1"
                   value="${fPct}"
                   class="brt-num"
                   data-id="${_esc(fx.id)}"
                   oninput="brtFixtureNum(this)">
            <span class="brt-pct-label">%</span>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  wrap.innerHTML = html;
  _brtSchedulePreview();
}

// ── Slider / input handlers ───────────────────────────────────────────────────

function brtGroupSlider(el) {
  const mk  = el.dataset.model;
  const pct = parseInt(el.value, 10);
  _brtSyncGroup(mk, pct);
}

function brtGroupNum(el) {
  const mk  = el.dataset.model;
  const pct = Math.max(0, Math.min(200, parseInt(el.value, 10) || 0));
  _brtSyncGroup(mk, pct);
}

function brtFixtureSlider(el) {
  const id  = el.dataset.id;
  const pct = parseInt(el.value, 10);
  _brtSyncFixture(id, pct);
}

function brtFixtureNum(el) {
  const id  = el.dataset.id;
  const pct = Math.max(0, Math.min(200, parseInt(el.value, 10) || 0));
  _brtSyncFixture(id, pct);
}

function brtToggleLink(cb) {
  const mk = cb.dataset.model;
  _brtLinked[mk] = cb.checked;
  _brtRender();
}

function brtResetGroup(mk) {
  _brtSyncGroup(decodeURIComponent(mk), 100);
}

function brtResetAll() {
  for (const fx of _brtFixtures) _brtScales[fx.id] = 1.0;
  _brtRender();
}

function brtSetManual(el) {
  const id  = el.dataset.id;
  const val = parseInt(el.value, 10);
  if (!isNaN(val) && val >= 0) {
    _brtManual[id] = val;
    _brtSchedulePreview();
  }
}

// ── Internal sync helpers ─────────────────────────────────────────────────────

function _brtSyncGroup(mk, pct) {
  const scale = pct / 100;
  for (const fx of _brtFixtures) {
    if (_brtModelKey(fx) === mk) _brtScales[fx.id] = scale;
  }
  // Update DOM: group slider + number
  for (const el of document.querySelectorAll(`[data-model="${CSS.escape(mk)}"][data-linked="1"]`)) {
    el.value = pct;
  }
  // Dim individual rows
  for (const row of document.querySelectorAll('.brt-fixture-row')) {
    const id = row.dataset.id;
    const fx = _brtFixtures.find(f => f.id === id);
    if (!fx || _brtModelKey(fx) !== mk) continue;
    for (const inp of row.querySelectorAll('.brt-slider,.brt-num')) inp.value = pct;
  }
  _brtSchedulePreview();
}

function _brtSyncFixture(id, pct) {
  _brtScales[id] = pct / 100;
  // Update DOM: both range and number inputs for this fixture
  for (const el of document.querySelectorAll(`[data-id="${CSS.escape(id)}"]`)) {
    if (el.type === 'range' || el.type === 'number') el.value = pct;
  }
  _brtSchedulePreview();
}

// ── Preview (debounced) ───────────────────────────────────────────────────────

function _brtSchedulePreview() {
  clearTimeout(_brtPreviewTm);
  _brtPreviewTm = setTimeout(_brtFetchPreview, 350);
}

async function _brtFetchPreview() {
  if (!_brtFixtures.length) return;
  const scales = _brtBuildScales();
  const res = await _apiJson('/api/brightness/preview', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ scales }),
  });
  if (!res.error) _brtSetPreview(res);
}

function _brtSetPreview(stats) {
  const el = document.getElementById('brt-preview');
  if (!el) return;
  if (!stats) {
    el.textContent = '—';
    el.className   = 'brt-preview-count';
    return;
  }
  const s = stats.scenes;
  const v = stats.values;
  const f = stats.fixtures_active;
  el.textContent = `${f} fixture${f !== 1 ? 's' : ''}, ${s} scene${s !== 1 ? 's' : ''}, ${v} value${v !== 1 ? 's' : ''} will change`;
  el.className   = `brt-preview-count ${v > 0 ? 'brt-preview-active' : ''}`;
}

// ── Generate QXW ─────────────────────────────────────────────────────────────

async function brtGenerateQxw() {
  if (!_brtFixtures.length) {
    setStatus('Load a workspace first.', 'warn'); return;
  }
  const scales = _brtBuildScales();
  const nonTrivial = Object.values(scales).some(v => Math.abs(v - 1.0) > 0.001);
  if (!nonTrivial) {
    setStatus('All fixtures are at 100% — nothing to change.', 'warn'); return;
  }

  setStatus('Generating…');
  let resp;
  try {
    resp = await fetch('/api/brightness/apply', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ scales, manual_dimmer_offsets: _brtManual }),
    });
  } catch (e) {
    setStatus('Network error: ' + e.message, 'error'); return;
  }

  if (!resp.ok) {
    try { const err = await resp.json(); setStatus(err.error || 'Failed.', 'error'); }
    catch { setStatus('Generate failed.', 'error'); }
    return;
  }

  const blob          = await resp.blob();
  const suggestedName = resp.headers.get('X-Suggested-Filename') || 'workspace_BRIGHTNESS.qxw';
  const scenes        = resp.headers.get('X-Scenes-Modified') || '?';
  const values        = resp.headers.get('X-Values-Changed')  || '?';

  if (typeof window.showSaveFilePicker === 'function') {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        startIn: 'documents',
        types: [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
      });
      const w = await handle.createWritable();
      await w.write(blob); await w.close();
      setStatus(`✓ Saved ${handle.name} — ${scenes} scenes, ${values} channel values adjusted`, 'ok');
      return;
    } catch (e) {
      if (e.name === 'AbortError') return;
    }
  }
  // Fallback download
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href = url; a.download = suggestedName;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 3000);
  setStatus(`✓ Downloaded ${suggestedName} — ${scenes} scenes, ${values} channel values adjusted`, 'ok');
}

// ── QXF upload ────────────────────────────────────────────────────────────────

async function brtUploadQxf() {
  const inp = document.getElementById('brt-qxf-input');
  if (!inp?.files?.length) { setStatus('Choose a .qxf file first.', 'warn'); return; }
  const fd = new FormData();
  fd.append('file', inp.files[0]);
  let resp;
  try {
    resp = await fetch('/api/brightness/upload-qxf', { method: 'POST', body: fd });
  } catch (e) {
    setStatus('Upload error: ' + e.message, 'error'); return;
  }
  const res = await resp.json();
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(res.message || 'QXF uploaded.', 'ok');
  // Reload fixture info with new QXF
  _brtLoaded = false;
  await _brtLoadFixtures();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _brtBuildScales() {
  const out = {};
  for (const fx of _brtFixtures) {
    out[fx.id] = _brtScales[fx.id] ?? 1.0;
  }
  return out;
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
