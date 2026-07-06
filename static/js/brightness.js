/* =============================================================================
   brightness.js — Per-fixture brightness scaling tab
   =============================================================================
   Lets the user scale the Master Dimmer channel of each fixture (or fixture
   group) across every Scene in the loaded workspace, then download a new QXW.
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _brtFixtures   = [];   // [{id,name,manufacturer,model,mode,dimmer_offset,...}]
let _brtLoaded     = false;
let _brtScales     = {};   // fixture_id → scale (0.0–2.0, default 1.0)
let _brtManual     = {};   // fixture_id → dimmer_offset (for QXF-not-found fixtures)
let _brtLinked     = {};   // model_key  → bool (true = sliders move together)
let _brtPreviewTm  = null; // debounce timer for preview
let _brtBaseline   = {};   // fixture_id → {peak, mean, scene_count} (from current scene values)

// ── Public API (called from app.js) ──────────────────────────────────────────

function invalidateBrightness() {
  _brtLoaded   = false;
  _brtFixtures = [];
  _brtScales   = {};
  _brtManual   = {};
  _brtLinked   = {};
  _brtBaseline = {};
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
  const [data, baselineData] = await Promise.all([
    _apiJson('/api/brightness/fixtures'),
    _apiJson('/api/brightness/baseline'),
  ]);
  if (data.error) { setStatus(data.error, 'error'); return; }
  _brtFixtures = Array.isArray(data) ? data : [];

  // Store baseline stats keyed by fixture ID
  _brtBaseline = {};
  if (Array.isArray(baselineData)) {
    for (const b of baselineData) _brtBaseline[b.id] = b;
  }

  // Initialise scales to 1.0 and link state per model group
  const seen = {};
  for (const fx of _brtFixtures) {
    if (_brtScales[fx.id] === undefined) _brtScales[fx.id] = 1.0;
    const mk = _brtModelKey(fx);
    if (!seen[mk]) { seen[mk] = true; if (_brtLinked[mk] === undefined) _brtLinked[mk] = true; }
  }
  _brtRender();
  _brtUpdateFetchBtn();
}

function _brtModelKey(fx) {
  return `${fx.manufacturer}||${fx.model}||${fx.mode}`;
}

function _brtMissingFixtures() {
  return _brtFixtures.filter(fx => !fx.qxf_found).map(fx => ({
    manufacturer: fx.manufacturer,
    model:        fx.model,
    fixture_name: fx.name,
  }));
}

// ── Baseline indicator helpers ────────────────────────────────────────────────

/** Compute peak dimmer % (0-100) for a group, averaged across all its fixtures. */
function _brtGroupPeakPct(fixtures) {
  let sum = 0, n = 0;
  for (const fx of fixtures) {
    const b = _brtBaseline[fx.id];
    if (b && b.scene_count > 0) { sum += b.peak; n++; }
  }
  return n > 0 ? sum / n / 255 * 100 : null;
}

/**
 * Build the baseline indicator HTML for a group header.
 * @param {number|null} pct   - this group's peak %
 * @param {number|null} maxPct - highest peak % across all groups (null = only one group)
 */
function _brtBaselineBadge(pct, maxPct) {
  if (pct === null) return ''; // no scene data
  const rounded = Math.round(pct);
  // Relative diff vs the brightest group (skip if this IS the brightest)
  let diffHtml = '';
  if (maxPct !== null && maxPct > 0 && Math.round(pct) < Math.round(maxPct)) {
    const diff = Math.round(pct - maxPct);
    diffHtml = `<span class="brt-baseline-diff" title="vs brightest group">${diff}%</span>`;
  }
  // Colour: green ≥ 95%, yellow 70-94%, orange 40-69%, red < 40%
  const cls = rounded >= 95 ? 'brt-bl-full'
            : rounded >= 70 ? 'brt-bl-ok'
            : rounded >= 40 ? 'brt-bl-low'
            :                  'brt-bl-dim';
  return `<span class="brt-baseline ${cls}" title="Peak dimmer value in scenes: ${rounded}% of full (${Math.round(pct/100*255)}/255). Reflects the actual current scene values — a value below 100% means this group was already scaled down in the loaded file.">` +
         `⟂ ${rounded}%${diffHtml}</span>`;
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
  const groupOrder = [];
  for (const fx of _brtFixtures) {
    const mk = _brtModelKey(fx);
    if (!groups[mk]) { groups[mk] = { fixtures: [], mk }; groupOrder.push(mk); }
    groups[mk].fixtures.push(fx);
  }

  // Pre-compute baseline peaks per group to find the global max
  const groupPeaks = {};
  let globalMaxPct = null;
  for (const mk of groupOrder) {
    const p = _brtGroupPeakPct(groups[mk].fixtures);
    groupPeaks[mk] = p;
    if (p !== null && (globalMaxPct === null || p > globalMaxPct)) globalMaxPct = p;
  }
  // Only show relative diff if there are at least 2 groups with scene data
  const validGroups = groupOrder.filter(mk => groupPeaks[mk] !== null);
  const showRelative = validGroups.length >= 2;

  let html = '';
  for (const mk of groupOrder) {
    const grp    = groups[mk];
    const fx0    = grp.fixtures[0];
    const linked = _brtLinked[mk] !== false;
    const noQxf  = !fx0.qxf_found;

    const grpScale = linked
      ? grp.fixtures.reduce((s, f) => s + (_brtScales[f.id] ?? 1), 0) / grp.fixtures.length
      : (_brtScales[fx0.id] ?? 1);
    const pct    = Math.round(grpScale * 100);
    const mkSafe = _esc(mk);

    const qxfBadge = noQxf
      ? `<span class="brt-badge brt-badge-warn" title="QXF not found — enter dimmer channel manually, upload/fetch the QXF, or assign one below">⚠ No QXF</span>`
      : `<span class="brt-badge brt-badge-ok"   title="QXF loaded from: ${_esc(fx0.qxf_path || 'local filesystem')}">✓ QXF</span>`;

    // Baseline indicator badge
    const blPct    = groupPeaks[mk];
    const blMaxPct = showRelative ? globalMaxPct : null;
    const blBadge  = _brtBaselineBadge(blPct, blMaxPct);

    // Per-group QXF assign button — always visible, lets user force any .qxf to this group
    const mfrSafe   = _esc(fx0.manufacturer);
    const modelSafe = _esc(fx0.model);
    const assignId  = `brt-assign-${mkSafe.replace(/[^a-z0-9]/gi,'_')}`;

    html += `
    <div class="brt-group" data-model="${mkSafe}">
      <div class="brt-group-header">
        <span class="brt-group-name">
          <strong>${mfrSafe} ${modelSafe}</strong>
          <span class="brt-group-mode">${_esc(fx0.mode)}</span>
          ${qxfBadge}
          ${blBadge}
        </span>
        <label class="brt-link-label" title="Move all fixtures in this group together">
          <input type="checkbox" class="brt-link-cb"
                 data-model="${mkSafe}" ${linked ? 'checked' : ''}
                 onchange="brtToggleLink(this)">
          Link group
        </label>
        <!-- Per-group QXF override picker -->
        <label class="btn btn-surface brt-assign-qxf-btn"
               title="Manually assign a QXF file to this fixture group, bypassing automatic name matching">
          📂 Assign QXF
          <input type="file" accept=".qxf" style="display:none" id="${assignId}"
                 onchange="brtAssignQxf(this,'${mfrSafe}','${modelSafe}')">
        </label>
        ${linked ? `
        <div class="brt-slider-row brt-group-slider">
          <input type="range"  min="0" max="200" step="1" value="${pct}" class="brt-slider"
                 data-model="${mkSafe}" data-linked="1" oninput="brtGroupSlider(this)">
          <input type="number" min="0" max="200" step="1" value="${pct}" class="brt-num"
                 data-model="${mkSafe}" data-linked="1" oninput="brtGroupNum(this)">
          <span class="brt-pct-label">%</span>
          <button class="btn btn-surface brt-reset-btn" title="Reset group to 100%"
                  onclick="brtResetGroup('${mkSafe}')">↺</button>
        </div>` : ''}
      </div>
      <div class="brt-fixture-list ${linked ? 'brt-list-linked' : ''}">`;

    for (const fx of grp.fixtures) {
      const fPct    = Math.round((_brtScales[fx.id] ?? 1) * 100);
      // Dimmer channel: manual override wins, then auto-detected, then empty
      const manualVal = _brtManual[fx.id];
      const autoOff   = fx.dimmer_offset;
      const doff      = manualVal !== undefined ? manualVal : (autoOff ?? '');
      const hasAuto   = autoOff !== null && autoOff !== undefined;
      // Channel info label (left of input)
      const chLabel   = hasAuto && manualVal === undefined
        ? `${fx.channels}&nbsp;ch&nbsp;·` : '';
      // Style: yellow/highlighted when no QXF or manual override active; muted otherwise
      const chClass   = (!hasAuto || manualVal !== undefined) ? 'brt-manual-ch' : 'brt-manual-ch brt-ch-override';
      const chTitle   = hasAuto
        ? (manualVal !== undefined
            ? `Manual override active (auto-detected: ch ${autoOff}). Clear to revert.`
            : `Auto-detected from QXF. Edit to override.`)
        : '0-indexed DMX channel offset for Master Dimmer (required — QXF not found)';

      html += `
        <div class="brt-fixture-row" data-id="${_esc(fx.id)}">
          <span class="brt-fx-name">${_esc(fx.name)}</span>
          <label class="brt-manual-label" title="${_esc(chTitle)}">
            ${chLabel} Dimmer&nbsp;ch:
            <input type="number" min="0" max="511" step="1"
                   class="${chClass}" value="${_esc(String(doff))}"
                   placeholder="${hasAuto ? autoOff : '?'}"
                   data-id="${_esc(fx.id)}" data-auto="${hasAuto ? autoOff : ''}"
                   oninput="brtSetManual(this)">
          </label>
          <div class="brt-slider-row" style="${linked ? 'opacity:0.45;pointer-events:none' : ''}">
            <input type="range"  min="0" max="200" step="1" value="${fPct}" class="brt-slider"
                   data-id="${_esc(fx.id)}" oninput="brtFixtureSlider(this)">
            <input type="number" min="0" max="200" step="1" value="${fPct}" class="brt-num"
                   data-id="${_esc(fx.id)}" oninput="brtFixtureNum(this)">
            <span class="brt-pct-label">%</span>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  wrap.innerHTML = html;
  _brtSchedulePreview();
}

// ── GitHub fetch button state ─────────────────────────────────────────────────

function _brtUpdateFetchBtn() {
  const btn = document.getElementById('brt-fetch-gh-btn');
  if (!btn) return;
  const n = _brtMissingFixtures().length;
  btn.disabled = n === 0;
  btn.title = n
    ? `Fetch QXF definitions for ${n} unrecognised fixture type(s) from GitHub (internet)`
    : 'All fixtures already matched locally';
}

// ── Slider / input handlers ───────────────────────────────────────────────────

function brtGroupSlider(el) { _brtSyncGroup(el.dataset.model, parseInt(el.value, 10)); }
function brtGroupNum(el)    { _brtSyncGroup(el.dataset.model, Math.max(0, Math.min(200, parseInt(el.value, 10) || 0))); }
function brtFixtureSlider(el) { _brtSyncFixture(el.dataset.id, parseInt(el.value, 10)); }
function brtFixtureNum(el)    { _brtSyncFixture(el.dataset.id, Math.max(0, Math.min(200, parseInt(el.value, 10) || 0))); }
function brtToggleLink(cb)  { _brtLinked[cb.dataset.model] = cb.checked; _brtRender(); }
function brtResetGroup(mk)  { _brtSyncGroup(decodeURIComponent(mk), 100); }
function brtResetAll()      { for (const fx of _brtFixtures) _brtScales[fx.id] = 1.0; _brtRender(); }
function brtSetManual(el) {
  const raw = el.value.trim();
  const val = parseInt(raw, 10);
  if (raw === '' || isNaN(val)) {
    // Clear: revert to auto-detected value (stored in data-auto)
    delete _brtManual[el.dataset.id];
    el.classList.add('brt-ch-override');
    el.classList.remove('brt-ch-override'); // triggers re-style on next render
  } else if (val >= 0) {
    _brtManual[el.dataset.id] = val;
    el.classList.add('brt-ch-override');
  }
  _brtSchedulePreview();
}

// ── Assign QXF to a specific fixture group ────────────────────────────────────

async function brtAssignQxf(input, manufacturer, model) {
  if (!input.files?.length) return;
  const file = input.files[0];
  const fd   = new FormData();
  fd.append('file',         file);
  fd.append('manufacturer', manufacturer);
  fd.append('model',        model);
  setStatus(`Assigning ${file.name} to ${manufacturer} ${model}…`);
  let resp;
  try {
    resp = await fetch('/api/brightness/assign-qxf', { method: 'POST', body: fd });
  } catch (e) { setStatus('Upload error: ' + e.message, 'error'); return; }
  const res = await resp.json();
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(res.message || 'QXF assigned.', 'ok');
  input.value = '';
  _brtLoaded  = false;
  await _brtLoadFixtures();
}

// ── Internal sync helpers ─────────────────────────────────────────────────────

function _brtSyncGroup(mk, pct) {
  const scale = pct / 100;
  for (const fx of _brtFixtures) if (_brtModelKey(fx) === mk) _brtScales[fx.id] = scale;
  for (const el of document.querySelectorAll(`[data-model="${CSS.escape(mk)}"][data-linked="1"]`)) el.value = pct;
  for (const row of document.querySelectorAll('.brt-fixture-row')) {
    const fx = _brtFixtures.find(f => f.id === row.dataset.id);
    if (!fx || _brtModelKey(fx) !== mk) continue;
    for (const inp of row.querySelectorAll('.brt-slider,.brt-num')) inp.value = pct;
  }
  _brtSchedulePreview();
}

function _brtSyncFixture(id, pct) {
  _brtScales[id] = pct / 100;
  for (const el of document.querySelectorAll(`[data-id="${CSS.escape(id)}"]`))
    if (el.type === 'range' || el.type === 'number') el.value = pct;
  _brtSchedulePreview();
}

// ── Preview (debounced) ───────────────────────────────────────────────────────

function _brtSchedulePreview() {
  clearTimeout(_brtPreviewTm);
  _brtPreviewTm = setTimeout(_brtFetchPreview, 350);
}

async function _brtFetchPreview() {
  if (!_brtFixtures.length) return;
  const res = await _apiJson('/api/brightness/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scales: _brtBuildScales() }),
  });
  if (!res.error) _brtSetPreview(res);
}

function _brtSetPreview(stats) {
  const el = document.getElementById('brt-preview');
  if (!el) return;
  if (!stats) { el.textContent = '—'; el.className = 'brt-preview-count'; return; }
  const { fixtures_active: f, scenes: s, values: v } = stats;
  el.textContent = `${f} fixture${f!==1?'s':''}, ${s} scene${s!==1?'s':''}, ${v} value${v!==1?'s':''} will change`;
  el.className   = `brt-preview-count ${v > 0 ? 'brt-preview-active' : ''}`;
}

// ── Generate QXW ──────────────────────────────────────────────────────────────

async function brtGenerateQxw() {
  if (!_brtFixtures.length) { setStatus('Load a workspace first.', 'warn'); return; }
  const scales = _brtBuildScales();
  if (!Object.values(scales).some(v => Math.abs(v - 1.0) > 0.001)) {
    setStatus('All fixtures are at 100% — nothing to change.', 'warn'); return;
  }
  setStatus('Generating…');
  let resp;
  try {
    resp = await fetch('/api/brightness/apply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scales, manual_dimmer_offsets: _brtManual }),
    });
  } catch (e) { setStatus('Network error: ' + e.message, 'error'); return; }
  if (!resp.ok) {
    try { const err = await resp.json(); setStatus(err.error || 'Failed.', 'error'); }
    catch { setStatus('Generate failed.', 'error'); }
    return;
  }
  const blob  = await resp.blob();
  const fname = resp.headers.get('X-Suggested-Filename') || 'workspace_BRIGHTNESS.qxw';
  const scenes = resp.headers.get('X-Scenes-Modified') || '?';
  const vals   = resp.headers.get('X-Values-Changed')  || '?';
  const savedName = await saveFileWithPicker(
    blob, fname,
    [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
    'Save brightness-adjusted workspace as'
  );
  if (!savedName) return;  // user cancelled
  setStatus(`✓ Saved ${savedName} — ${scenes} scenes, ${vals} channel values adjusted`, 'ok');
}

// ── Upload QXF (one or many) ──────────────────────────────────────────────────

async function brtUploadQxf() {
  const inp = document.getElementById('brt-qxf-input');
  if (!inp?.files?.length) { setStatus('Choose one or more .qxf files.', 'warn'); return; }
  const fd = new FormData();
  for (const f of inp.files) fd.append('file', f);
  setStatus(`Uploading ${inp.files.length} QXF file(s)…`);
  let resp;
  try {
    resp = await fetch('/api/brightness/upload-qxf', { method: 'POST', body: fd });
  } catch (e) { setStatus('Upload error: ' + e.message, 'error'); return; }
  const res = await resp.json();
  const errNote = res.errors?.length ? ' (' + res.errors.join('; ') + ')' : '';
  setStatus((res.message || 'Done.') + errNote, res.saved?.length ? 'ok' : 'warn');
  inp.value = '';
  _brtLoaded = false;
  await _brtLoadFixtures();
}

// ── Scan local fixture directories ────────────────────────────────────────────

async function brtScanLocal() {
  setStatus('📁 Scanning local QLC+ fixture directories…');
  let res;
  try { res = await _apiJson('/api/brightness/scan-local'); }
  catch (e) { setStatus('Scan error: ' + e.message, 'error'); return; }
  if (res.error) { setStatus(res.error, 'error'); return; }

  const total   = res.total_qxf_files ?? 0;
  const matched = res.fixtures_matched?.length ?? 0;
  const missing = res.fixtures_missing?.length ?? 0;
  const ndirs   = res.dirs?.length ?? 0;
  let msg = `📁 Local: ${total} QXF file(s) in ${ndirs} director${ndirs!==1?'ies':'y'}. `;
  msg += matched ? `✓ ${matched} fixture type(s) matched. ` : '';
  msg += missing ? `⚠ ${missing} still unmatched.` : (matched ? 'All fixtures matched!' : '');
  setStatus(msg, (matched > 0 || total > 0) ? 'ok' : 'warn');

  _brtLoaded = false;
  await _brtLoadFixtures();
}

// ── Fetch from GitHub (internet) ──────────────────────────────────────────────

async function brtFetchGithub() {
  const missing = _brtMissingFixtures();
  if (!missing.length) { setStatus('All fixtures already matched — nothing to fetch.', 'warn'); return; }

  // Always show explicit internet-connection warning
  const nameList = missing.map(f => `  • ${f.manufacturer} ${f.model}`).join('\n');
  const ok = confirm(
    `⚠ INTERNET CONNECTION REQUIRED\n\n` +
    `This will make outbound HTTP requests to:\n` +
    `  • api.github.com\n` +
    `  • raw.githubusercontent.com\n\n` +
    `Fixtures to look up (${missing.length}):\n${nameList}\n\n` +
    `Downloaded QXF files will be saved next to your workspace.\n\n` +
    `Continue?`
  );
  if (!ok) return;

  setStatus(`🌐 Connecting to GitHub — looking up ${missing.length} fixture type(s)…`);
  let res;
  try {
    res = await _apiJson('/api/brightness/fetch-github', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixtures: missing }),
    });
  } catch (e) { setStatus('Network error: ' + e.message, 'error'); return; }
  if (res.error) { setStatus('🌐 ' + res.error, 'error'); return; }

  const dl  = res.downloaded?.length ?? 0;
  const nf  = res.not_found?.length  ?? 0;
  const err = res.errors?.length     ?? 0;
  let msg = `🌐 GitHub: `;
  if (dl)  msg += `✓ ${dl} QXF file(s) downloaded. `;
  if (nf)  msg += `⚠ ${nf} fixture(s) not found on GitHub. `;
  if (err) msg += `✗ ${err} error(s). `;
  if (!dl && !nf && !err) msg += 'No results.';
  setStatus(msg, dl ? 'ok' : 'warn');

  if (dl) { _brtLoaded = false; await _brtLoadFixtures(); }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _brtBuildScales() {
  const out = {};
  for (const fx of _brtFixtures) out[fx.id] = _brtScales[fx.id] ?? 1.0;
  return out;
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
