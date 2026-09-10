/**
 * porter.js — Function Porter tab
 *
 * 5-step wizard:
 *   1. Load source + target QXW
 *   2. Select functions (with dependency closure)
 *   3. Map source fixtures → target fixtures
 *   4. Validate the plan
 *   5. Execute & export
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────

let _pSrcLoaded = false;
let _pTgtLoaded = false;
let _pSrcName   = '';
let _pTgtName   = '';

let _pSrcFunctions = [];
let _pSrcFixtures  = [];
let _pTgtFixtures  = [];

let _pClosure    = null;   // result of /resolve
let _pCandidates = null;   // result of /fixture-candidates
let _pFixMapping = {};     // src_fix_id → [tgt_fix_id, ...]
let _pFanoutMode = 'pattern_repeat';
let _pMirrorFixtures = new Set();
let _pPanChannelMap  = {};  // src_fix_id → {coarse, fine?}
let _pNamePrefix     = '';
let _pImportPath     = '';
let _pValidation     = null;

let _pStep = 1;  // current wizard step (1–5)

// Search/filter
let _pFnSearch = '';
let _pFnTypeFilter = '';

let _pInited = false;

// ── Init ─────────────────────────────────────────────────────────────────────

async function porterInit() {
  if (_pInited) return;
  _pInited = true;
  await _pRefreshState();
}

function _pStatus(msg, type = 'info') {
  const el = document.getElementById('porter-status');
  if (!el) return;
  el.textContent = msg;
  el.className = `status-bar status-${type}`;
}

// ── State refresh ────────────────────────────────────────────────────────────

async function _pRefreshState() {
  try {
    const r = await fetch('/api/porter/state');
    if (!r.ok) return;
    const s = await r.json();
    _pSrcLoaded = s.src_loaded;
    _pTgtLoaded = s.tgt_loaded;
    _pSrcName   = s.src_name || '';
    _pTgtName   = s.tgt_name || '';
    if (_pSrcLoaded) await _pFetchSourceData();
    if (_pTgtLoaded) await _pFetchTargetData();
    _pRenderStep();
  } catch (e) {
    _pStatus('Error refreshing state: ' + e.message, 'error');
  }
}

// ── Load source / target ─────────────────────────────────────────────────────

async function _pLoadSide(side, pathInputId, fileInputId) {
  const endpoint = `/api/porter/${side}/load`;
  const label    = side === 'source' ? 'Source' : 'Target';
  const pathVal  = (document.getElementById(pathInputId)?.value || '').trim();
  const fileEl   = document.getElementById(fileInputId);
  const file     = fileEl?.files?.[0];

  _pStatus(`Loading ${label.toLowerCase()}...`, 'info');
  try {
    let r;
    if (file) {
      const fd = new FormData();
      fd.append('file', file);
      r = await fetch(endpoint, { method: 'POST', body: fd });
    } else if (pathVal) {
      r = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: pathVal }),
      });
    } else {
      _pStatus(`Enter a path or click Browse to pick the ${label.toLowerCase()} .qxw file.`, 'error');
      return;
    }

    const d = await r.json();
    if (!r.ok) { _pStatus(`${label} load error: ${d.error}`, 'error'); return; }

    if (side === 'source') {
      _pSrcLoaded = true; _pSrcName = d.name;
      if (file) document.getElementById(pathInputId).value = file.name;
      await _pFetchSourceData();
    } else {
      _pTgtLoaded = true; _pTgtName = d.name;
      if (file) document.getElementById(pathInputId).value = file.name;
      await _pFetchTargetData();
    }
    const s = d.summary;
    _pStatus(`${label} loaded: ${d.name} (${s.fixtures} fixtures, ${s.functions} functions)`, 'ok');
    _pRenderStep();
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
  }
}

function porterLoadSrc() {
  _pLoadSide('source', 'porter-src-path', 'porter-src-file');
  // Track in session
  const p = document.getElementById('porter-src-path')?.value?.trim();
  if (p && typeof _sess !== 'undefined') _sess.porter_source = p;
}
function porterLoadTgt() { _pLoadSide('target', 'porter-tgt-path', 'porter-tgt-file'); }
function porterBrowseSrc() { document.getElementById('porter-src-file')?.click(); }
function porterBrowseTgt() { document.getElementById('porter-tgt-file')?.click(); }
function porterSetSourcePath(path) {
  const inp = document.getElementById('porter-src-path');
  if (inp && path) { inp.value = path; porterLoadSrc(); }
}
function porterSrcFileChosen() {
  const f = document.getElementById('porter-src-file')?.files?.[0];
  if (f) { document.getElementById('porter-src-path').value = ''; porterLoadSrc(); }
}
function porterTgtFileChosen() {
  const f = document.getElementById('porter-tgt-file')?.files?.[0];
  if (f) { document.getElementById('porter-tgt-path').value = ''; porterLoadTgt(); }
}

async function _pFetchSourceData() {
  const [fnR, fxR] = await Promise.all([
    fetch('/api/porter/source/functions'),
    fetch('/api/porter/source/fixtures'),
  ]);
  _pSrcFunctions = fnR.ok ? await fnR.json() : [];
  _pSrcFixtures  = fxR.ok ? await fxR.json() : [];
}

async function _pFetchTargetData() {
  const r = await fetch('/api/porter/target/fixtures');
  _pTgtFixtures = r.ok ? await r.json() : [];
}

// ── Wizard navigation ────────────────────────────────────────────────────────

function porterGoStep(n) {
  if (n < 1 || n > 5) return;
  // Guard: can't advance past step 1 without both files loaded
  if (n > 1 && (!_pSrcLoaded || !_pTgtLoaded)) {
    _pStatus('Load both source and target QXW files first.', 'error');
    return;
  }
  _pStep = n;
  _pRenderStep();
}

function _pRenderStep() {
  // Update step indicators
  for (let i = 1; i <= 5; i++) {
    const btn = document.getElementById(`porter-step-${i}`);
    if (btn) {
      btn.classList.toggle('active', i === _pStep);
      btn.classList.toggle('done', i < _pStep);
    }
    const panel = document.getElementById(`porter-panel-${i}`);
    if (panel) panel.hidden = (i !== _pStep);
  }
  // Update header info
  const srcH = document.getElementById('porter-src-info');
  const tgtH = document.getElementById('porter-tgt-info');
  if (srcH) srcH.textContent = _pSrcLoaded ? _pSrcName : '— not loaded —';
  if (tgtH) tgtH.textContent = _pTgtLoaded ? _pTgtName : '— not loaded —';

  // Render the active panel
  if (_pStep === 2) _pRenderSelectFunctions();
  if (_pStep === 3) _pRenderMapFixtures();
  if (_pStep === 4) _pRenderValidation();
}

// ═════════════════════════════════════════════════════════════════════════════
// Step 2: Select functions
// ═════════════════════════════════════════════════════════════════════════════

function porterFnSearch(val) { _pFnSearch = (val || '').toLowerCase(); _pRenderSelectFunctions(); }
function porterFnTypeFilter(val) { _pFnTypeFilter = val || ''; _pRenderSelectFunctions(); }
function porterSelectAllFn() {
  document.querySelectorAll('#porter-fn-list .porter-check').forEach(cb => cb.checked = true);
}
function porterSelectNoneFn() {
  document.querySelectorAll('#porter-fn-list .porter-check').forEach(cb => cb.checked = false);
}

function _pRenderSelectFunctions() {
  const container = document.getElementById('porter-fn-list');
  if (!container) return;

  let items = _pSrcFunctions
    .filter(f => {
      if (_pFnSearch && !f.name.toLowerCase().includes(_pFnSearch)) return false;
      if (_pFnTypeFilter && f.type !== _pFnTypeFilter) return false;
      return true;
    });

  if (!items.length) {
    container.innerHTML = '<div class="porter-placeholder">No functions match</div>';
    return;
  }

  container.innerHTML = items.map(f => `
    <label class="porter-row">
      <input type="checkbox" class="porter-check" value="${f.id}" data-name="${_esc(f.name)}">
      <span class="porter-row-label">${_esc(f.name)}</span>
      <span class="porter-row-sub">${_esc(f.type)}${f.path ? ' · ' + _esc(f.path) : ''}</span>
    </label>`).join('');

  // Restore previous selections if closure exists
  if (_pClosure) {
    const seeds = new Set(_pClosure.seed_ids);
    container.querySelectorAll('.porter-check').forEach(cb => {
      if (seeds.has(cb.value)) cb.checked = true;
    });
  }
}

async function porterResolve() {
  const checks = Array.from(document.querySelectorAll('#porter-fn-list .porter-check:checked'));
  if (!checks.length) {
    _pStatus('Select at least one function.', 'error');
    return;
  }
  const seedIds = checks.map(c => c.value);

  _pStatus('Resolving dependencies...', 'info');
  try {
    const r = await fetch('/api/porter/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed_ids: seedIds }),
    });
    const d = await r.json();
    if (!r.ok) { _pStatus('Resolve error: ' + d.error, 'error'); return; }

    _pClosure = d;
    const nSeed = d.seed_ids.length;
    const nDep  = d.function_ids.length - nSeed;
    let msg = `Resolved: ${nSeed} selected + ${nDep} dependencies = ${d.function_ids.length} functions.`;
    if (d.fixture_ids.length) msg += ` ${d.fixture_ids.length} fixtures referenced.`;
    if (d.cycles.length) msg += ` ⚠ ${d.cycles.length} cycle(s) detected.`;
    if (d.unresolved.length) msg += ` ⚠ ${d.unresolved.length} unresolved ref(s).`;
    _pStatus(msg, d.unresolved.length ? 'warn' : 'ok');

    // Show closure summary
    _pRenderClosureSummary();
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
  }
}

function _pRenderClosureSummary() {
  const el = document.getElementById('porter-closure-summary');
  if (!el || !_pClosure) return;

  const c = _pClosure;
  let html = `<div class="porter-summary-box">
    <strong>${c.function_ids.length}</strong> function(s) in closure
    (<strong>${c.seed_ids.length}</strong> selected +
     <strong>${c.function_ids.length - c.seed_ids.length}</strong> dependencies)<br>
    <strong>${c.fixture_ids.length}</strong> source fixture(s) referenced`;

  if (c.cycles.length) {
    html += `<br><span class="porter-warn">⚠ Cycles: ${c.cycles.map(_esc).join('; ')}</span>`;
  }
  if (c.unresolved.length) {
    html += `<br><span class="porter-warn">⚠ Unresolved IDs: ${c.unresolved.join(', ')}</span>`;
  }
  html += `</div>`;
  el.innerHTML = html;
}

// ═════════════════════════════════════════════════════════════════════════════
// Step 3: Map fixtures
// ═════════════════════════════════════════════════════════════════════════════

async function _pRenderMapFixtures() {
  const container = document.getElementById('porter-fixture-map');
  if (!container) return;

  if (!_pClosure || !_pClosure.fixture_ids.length) {
    container.innerHTML = '<div class="porter-placeholder">No fixtures to map (functions have no fixture references)</div>';
    return;
  }

  // Fetch candidates if not already fetched (or closure changed)
  _pStatus('Finding compatible fixtures...', 'info');
  try {
    const r = await fetch('/api/porter/fixture-candidates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixture_ids: _pClosure.fixture_ids }),
    });
    const d = await r.json();
    if (!r.ok) { _pStatus('Error: ' + d.error, 'error'); return; }
    _pCandidates = d;
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
    return;
  }

  // Auto-map if mapping is empty
  if (Object.keys(_pFixMapping).length === 0) {
    try {
      const r = await fetch('/api/porter/auto-map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fixture_ids: _pClosure.fixture_ids }),
      });
      if (r.ok) _pFixMapping = await r.json();
    } catch (e) { /* best-effort */ }
  }

  // Render mapping table
  let html = '<table class="porter-map-table"><thead><tr>'
    + '<th>Source Fixture</th><th>→</th><th>Target Fixture(s)</th><th>Mirror</th>'
    + '</tr></thead><tbody>';

  for (const srcFix of _pCandidates.source_fixtures) {
    const srcId = srcFix.id;
    const cands = _pCandidates.candidates[srcId] || {};
    const mapped = _pFixMapping[srcId] || [];

    // Build target options: tier1 first, then tier2, then tier3
    let options = '';
    const _opt = (list, label) => {
      if (!list.length) return '';
      return `<optgroup label="${label}">` +
        list.map(t => `<option value="${t.id}" ${mapped.includes(t.id) ? 'selected' : ''}>${_esc(t.name)} [${t.id}] (${t.mode})</option>`).join('') +
        '</optgroup>';
    };
    options += _opt(cands.tier1 || [], 'Exact match (model+mode)');
    options += _opt(cands.tier2 || [], 'Same model, different mode');
    options += _opt(cands.tier3 || [], 'Different model');

    const hasTier1 = (cands.tier1 || []).length > 0;

    html += `<tr>
      <td>
        <strong>${_esc(srcFix.name)}</strong> [${srcId}]<br>
        <small>${_esc(srcFix.manufacturer)} ${_esc(srcFix.model)} · ${srcFix.mode} · ${srcFix.channels}ch</small>
      </td>
      <td class="porter-arrow">→</td>
      <td>
        <select multiple class="porter-tgt-select" data-src-id="${srcId}"
                onchange="porterUpdateMapping('${srcId}', this)"
                size="${Math.min(5, (cands.tier1||[]).length + (cands.tier2||[]).length + 2)}">
          ${options || '<option disabled>No target fixtures available</option>'}
        </select>
        ${!hasTier1 ? '<small class="porter-warn">⚠ No exact match in target</small>' : ''}
      </td>
      <td>
        <label><input type="checkbox" class="porter-mirror-cb" data-src-id="${srcId}"
               onchange="porterToggleMirror('${srcId}', this.checked)"
               ${_pMirrorFixtures.has(srcId) ? 'checked' : ''}> Mirror Pan</label>
      </td>
    </tr>`;
  }
  html += '</tbody></table>';

  // Fan-out mode selector
  html += `<div class="porter-fanout-bar">
    <label>Fan-out mode:
      <select id="porter-fanout-mode" onchange="porterSetFanout(this.value)">
        <option value="pattern_repeat" ${_pFanoutMode === 'pattern_repeat' ? 'selected' : ''}>Pattern Repeat (tile)</option>
        <option value="clone" ${_pFanoutMode === 'clone' ? 'selected' : ''}>Clone (each src→its targets)</option>
        <option value="block" ${_pFanoutMode === 'block' ? 'selected' : ''}>Block (contiguous groups)</option>
        <option value="manual" ${_pFanoutMode === 'manual' ? 'selected' : ''}>Manual (1:1)</option>
      </select>
    </label>
    <label style="margin-left:1rem">Name prefix:
      <input type="text" id="porter-name-prefix" class="filter-input" style="width:150px"
             value="${_esc(_pNamePrefix)}" placeholder="e.g. SHOW2 / "
             oninput="_pNamePrefix = this.value">
    </label>
  </div>`;

  container.innerHTML = html;
  _pStatus(`${_pCandidates.source_fixtures.length} source fixture(s) to map.`, 'info');
}

function porterUpdateMapping(srcId, selectEl) {
  const selected = Array.from(selectEl.selectedOptions).map(o => o.value);
  _pFixMapping[srcId] = selected;
}

function porterToggleMirror(srcId, checked) {
  if (checked) _pMirrorFixtures.add(srcId);
  else _pMirrorFixtures.delete(srcId);
}

function porterSetFanout(mode) { _pFanoutMode = mode; }

function porterAutoMap() {
  _pFixMapping = {};
  _pRenderMapFixtures();
}

// ═════════════════════════════════════════════════════════════════════════════
// Step 4: Validate
// ═════════════════════════════════════════════════════════════════════════════

async function _pRenderValidation() {
  const container = document.getElementById('porter-validation-result');
  if (!container) return;

  if (!_pClosure) {
    container.innerHTML = '<div class="porter-placeholder">Go back and select functions first.</div>';
    return;
  }

  _pStatus('Validating...', 'info');
  const plan = _pBuildPlan();

  try {
    const r = await fetch('/api/porter/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(plan),
    });
    const d = await r.json();
    if (!r.ok) { _pStatus('Validation error: ' + (d.error || 'Unknown'), 'error'); return; }
    _pValidation = d;

    let html = '';
    if (d.errors.length) {
      html += '<div class="porter-val-section porter-val-errors"><h4>Errors (blocking)</h4><ul>';
      d.errors.forEach(e => html += `<li>${_esc(e)}</li>`);
      html += '</ul></div>';
    }
    if (d.warnings.length) {
      html += '<div class="porter-val-section porter-val-warnings"><h4>Warnings</h4><ul>';
      d.warnings.forEach(w => html += `<li>${_esc(w)}</li>`);
      html += '</ul></div>';
    }
    if (d.info.length) {
      html += '<div class="porter-val-section porter-val-info"><h4>Summary</h4><ul>';
      d.info.forEach(i => html += `<li>${_esc(i)}</li>`);
      html += '</ul></div>';
    }

    const exportBtn = document.getElementById('porter-export-btn');
    if (exportBtn) exportBtn.disabled = !d.ok;

    if (d.ok) {
      html += '<div class="porter-val-ok">✓ Plan is valid — ready to export.</div>';
      _pStatus('Validation passed. Ready to export.', 'ok');
    } else {
      _pStatus('Validation failed. Fix errors before exporting.', 'error');
    }

    container.innerHTML = html;
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// Step 5: Execute & Export
// ═════════════════════════════════════════════════════════════════════════════

async function porterExecute() {
  if (!_pValidation?.ok) {
    _pStatus('Validate first (Step 4).', 'error');
    return;
  }

  _pStatus('Executing import...', 'info');
  const plan = _pBuildPlan();

  try {
    const r = await fetch('/api/porter/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(plan),
    });

    if (!r.ok) {
      const d = await r.json();
      _pStatus('Execute error: ' + (d.error || 'Unknown'), 'error');
      return;
    }

    const blob = await r.blob();
    const suggestedName = r.headers.get('X-Suggested-Filename') || 'imported.qxw';

    const savedName = await saveFileWithPicker(
      blob, suggestedName,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
      'Save imported workspace as'
    );
    if (!savedName) return;
    _pStatus(`Saved: ${savedName}`, 'ok');
    porterGoStep(5);
    _pRenderDone(savedName);
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
  }
}

function _pRenderDone(filename) {
  const el = document.getElementById('porter-panel-5');
  if (!el) return;
  el.innerHTML = `
    <div class="porter-done">
      <h3>Import complete</h3>
      <p>Saved as: <strong>${_esc(filename)}</strong></p>
      <p>${_pClosure.function_ids.length} function(s) imported with
         ${_pClosure.fixture_ids.length} fixture mapping(s).</p>
      <button class="btn btn-accent" onclick="porterReset()">Start new import</button>
    </div>`;
}

async function porterReport() {
  const plan = _pBuildPlan();
  try {
    const r = await fetch('/api/porter/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan, validation: _pValidation }),
    });
    const d = await r.json();
    if (!r.ok) { _pStatus('Report error: ' + d.error, 'error'); return; }
    // Copy to clipboard
    await navigator.clipboard.writeText(d.report);
    _pStatus('Report copied to clipboard.', 'ok');
  } catch (e) {
    _pStatus('Could not copy report: ' + e.message, 'error');
  }
}

function porterReset() {
  _pClosure = null;
  _pCandidates = null;
  _pFixMapping = {};
  _pMirrorFixtures.clear();
  _pPanChannelMap = {};
  _pValidation = null;
  _pNamePrefix = '';
  _pStep = 1;
  _pStatus('Ready for a new import.', 'info');
  _pRenderStep();
}

// ── Plan builder ─────────────────────────────────────────────────────────────

function _pBuildPlan() {
  return {
    closure:         _pClosure,
    fixture_mapping: _pFixMapping,
    fanout_mode:     _pFanoutMode,
    mirror_fixtures: Array.from(_pMirrorFixtures),
    pan_channel_map: _pPanChannelMap,
    name_prefix:     _pNamePrefix,
    import_path:     _pImportPath,
  };
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
