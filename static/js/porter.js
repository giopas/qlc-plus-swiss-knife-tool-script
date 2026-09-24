/**
 * porter.js — Function Porter tab
 *
 * 5-step wizard:
 *   1. Load source + target QXW
 *   2. Select functions (with dependency closure)
 *   3. Map source fixtures → target fixtures
 *   4. Validate the plan
 *   5. Execute & export
 *
 * v1.4: pick functions from the source Virtual Console (their widgets come
 * along), fan-in mapping (many source fixtures → fewer targets), Doctor gate
 * on export and an import report saved next to the new workspace.
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
let _pDropUnmapped   = false;
let _pCompleteCh     = true;
let _pManual         = new Set();   // functions ticked in the function list
let _pExcluded       = new Set();   // functions coming from the VC but unticked by hand
let _pVcTree         = [];          // source VC (from /source/vc)
let _pVcScope        = [];          // widget keys ticked in the VC tree
let _pVcSeeds        = [];          // functions used by those widgets
let _pClosureKey     = '';          // seeds the current closure was built from
let _pResolveTimer   = null;
let _pPlans = { source: null, target: null };   // /api/porter/stage/<side>
let _pVc = { enabled: true, target_page: '', page_caption: '', bindings: 'keep_free' };

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

// Messages go to the app's one status bar (bottom of the window), so an old
// message from another tool never sits next to a Porter one.
function _pStatus(msg, type = 'info') {
  const level = (type === 'error' || type === 'warn') ? type : 'ok';
  if (typeof setStatus === 'function') { setStatus(msg, level); return; }
  const el = document.getElementById('porter-status');
  if (!el) return;
  el.hidden = false;
  el.textContent = msg;
  el.className = `status-bar status-${type}`;
}

const _P_STEP_HINT = {
  1: 'Pick the source show (import from) and the target show (import into).',
  2: 'Tick pages, frames, buttons or functions to port — what they need is added automatically.',
  3: 'Check where each source fixture goes in the target rig.',
  4: 'Check the plan and the Virtual Console options, then export.',
};

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
      setFileChip('porter-src-chip', file ? file.name : document.getElementById(pathInputId).value);
      await _pFetchSourceData();
    } else {
      _pTgtLoaded = true; _pTgtName = d.name;
      if (file) document.getElementById(pathInputId).value = file.name;
      setFileChip('porter-tgt-chip', file ? file.name : document.getElementById(pathInputId).value);
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
function porterBrowseSrc() { pickQxwInto('porter-src-path', 'porter-src-file', porterLoadSrc); }
function porterBrowseTgt() { pickQxwInto('porter-tgt-path', 'porter-tgt-file', porterLoadTgt); }
function porterUseOpenSrc() { useOpenWorkspace('porter-src-path', 'porter-src-file', porterLoadSrc); }
function porterUseOpenTgt() { useOpenWorkspace('porter-tgt-path', 'porter-tgt-file', porterLoadTgt); }
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
  await _pFetchPlan('source');
  _pSrcFunctions = fnR.ok ? await fnR.json() : [];
  _pSrcFixtures  = fxR.ok ? await fxR.json() : [];
  try {
    const r = await fetch('/api/porter/source/vc');
    _pVcTree = r.ok ? await r.json() : [];
  } catch (e) { _pVcTree = []; }
  _pManual = new Set();
  _pExcluded = new Set();
  _pVcScope = [];
  _pVcSeeds = [];
  _pClosure = null;
  _pClosureKey = '';
}

async function _pFetchTargetData() {
  const r = await fetch('/api/porter/target/fixtures');
  _pTgtFixtures = r.ok ? await r.json() : [];
  await _pFetchPlan('target');
}

// ── Wizard navigation ────────────────────────────────────────────────────────

async function porterGoStep(n) {
  if (n < 1 || n > 5) return;
  // Guard: can't advance past step 1 without both files loaded
  if (n > 1 && (!_pSrcLoaded || !_pTgtLoaded)) {
    _pStatus('Load both source and target QXW files first.', 'error');
    return;
  }
  // Steps 3–5 need the selection resolved (done automatically)
  if (n >= 3 && !(await porterResolve(false))) { if (_pStep !== 2) { _pStep = 2; _pRenderStep(); } return; }
  _pStep = n;
  _pRenderStep();
  if (_P_STEP_HINT[n]) _pStatus(_P_STEP_HINT[n], 'info');
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
  if (_pStep === 1 || _pStep === 3) setTimeout(_pDrawPlans, 0);
  if (_pStep === 2) _pRenderSelectFunctions();
  if (_pStep === 3) _pRenderMapFixtures();
  if (_pStep === 4) { _pRenderVcOptions(); _pRenderValidation(); }
}

// ═════════════════════════════════════════════════════════════════════════════
// Step 2: Select functions
// ═════════════════════════════════════════════════════════════════════════════

function porterFnSearch(val) { _pFnSearch = (val || '').toLowerCase(); _pRenderSelectFunctions(); }
function porterFnTypeFilter(val) { _pFnTypeFilter = val || ''; _pRenderSelectFunctions(); }
// ── What is selected ────────────────────────────────────────────────────────

/** Seeds = functions ticked by hand + functions of ticked VC widgets,
 *  minus the ones unticked by hand; in source order (deterministic). */
function _pSeedIds() {
  const vc = new Set(_pVcSeeds.map(String));
  return _pSrcFunctions.map(f => String(f.id))
    .filter(id => _pManual.has(id) || (vc.has(id) && !_pExcluded.has(id)));
}
function _pIsSelected(id) {
  id = String(id);
  return _pManual.has(id) || (_pVcSeeds.map(String).includes(id) && !_pExcluded.has(id));
}
function _pSetFn(id, on) {
  id = String(id);
  if (on) { _pManual.add(id); _pExcluded.delete(id); }
  else { _pManual.delete(id); if (_pVcSeeds.map(String).includes(id)) _pExcluded.add(id); }
}

function porterSelectAllFn() {
  document.querySelectorAll('#porter-fn-list .porter-check').forEach(cb => { cb.checked = true; _pSetFn(cb.value, true); });
  _pScheduleResolve();
}
function porterSelectNoneFn() {
  document.querySelectorAll('#porter-fn-list .porter-check').forEach(cb => { cb.checked = false; _pSetFn(cb.value, false); });
  _pScheduleResolve();
}
function porterToggleFn(cb) {
  _pSetFn(cb.value, cb.checked);
  _pScheduleResolve();
}

// ── Source VC tree (ticking a frame ticks everything inside) ────────────────

function _pRenderVcTree() {
  const el = document.getElementById('porter-vc-tree');
  if (!el) return;
  if (!_pVcTree.length) {
    el.innerHTML = '<div class="porter-placeholder">The source has no Virtual Console.</div>';
    return;
  }
  const scope = new Set(_pVcScope);
  el.innerHTML = _pVcTree.map((w, i) => {
    const icon = w.depth === 0 ? '📄 ' : (w.tag === 'Frame' || w.tag === 'SoloFrame' ? '▣ ' : '');
    return `<label class="porter-row${w.depth === 0 ? ' porter-vc-page' : ''}" style="padding-left:${0.5 + w.depth * 1.2}rem">
      <input type="checkbox" class="porter-vc-check" data-idx="${i}" value="${w.key}"
             ${scope.has(w.key) ? 'checked' : ''} onchange="porterVcToggle(${i}, this.checked)">
      <span class="porter-row-label">${icon}${_esc(w.caption || '(no caption)')}</span>
      <span class="porter-row-sub">${_esc(w.tag)} · ${w.functions} function(s)</span>
    </label>`;
  }).join('');
  _pVcSyncParents();
}

function _pVcBoxes() {
  return Array.from(document.querySelectorAll('#porter-vc-tree .porter-vc-check'));
}

/** Indexes of the rows inside row *i* (the tree is in document order). */
function _pVcChildren(i) {
  const out = [];
  const d = _pVcTree[i].depth;
  for (let j = i + 1; j < _pVcTree.length && _pVcTree[j].depth > d; j++) out.push(j);
  return out;
}

/** A frame shows ticked when everything inside is ticked, dashed when partly. */
function _pVcSyncParents() {
  const boxes = _pVcBoxes();
  for (let i = _pVcTree.length - 1; i >= 0; i--) {
    const kids = _pVcChildren(i);
    if (!kids.length) { boxes[i].indeterminate = false; continue; }
    const on = kids.filter(j => boxes[j].checked).length;
    boxes[i].checked = on === kids.length;
    boxes[i].indeterminate = on > 0 && on < kids.length;
  }
}

function porterVcToggle(i, checked) {
  const boxes = _pVcBoxes();
  for (const j of _pVcChildren(i)) { boxes[j].checked = checked; boxes[j].indeterminate = false; }
  _pVcSyncParents();
  _pVcScopeChanged();
}

function porterVcAll(on) {
  _pVcBoxes().forEach(b => { b.checked = on; b.indeterminate = false; });
  _pVcScopeChanged();
}

async function _pVcScopeChanged() {
  _pVcScope = _pVcBoxes().filter(b => b.checked).map(b => b.value);
  if (!_pVcScope.length) {
    _pVcSeeds = [];
  } else {
    try {
      const r = await fetch('/api/porter/vc/seeds', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: _pVcScope }),
      });
      const d = await r.json();
      if (!r.ok) { _pStatus('Error: ' + d.error, 'error'); return; }
      _pVcSeeds = d.seed_ids.map(String);
    } catch (e) { _pStatus('Network error: ' + e.message, 'error'); return; }
  }
  const info = document.getElementById('porter-vc-pick-info');
  const nW = _pVcScope.length;
  if (info) info.textContent = nW ? `${nW} widget(s) ticked → ${_pVcSeeds.length} function(s); the widgets come along.` : '';
  _pRenderFnList();
  _pScheduleResolve();
}

// ── Dependencies: resolved automatically ────────────────────────────────────

function _pScheduleResolve() {
  clearTimeout(_pResolveTimer);
  _pResolveTimer = setTimeout(() => porterResolve(true), 250);
}

async function porterNextFromSelect() {
  clearTimeout(_pResolveTimer);
  const ok = await porterResolve(false);
  if (ok) porterGoStep(3);
}

function _pRenderSelectFunctions() {
  _pRenderVcTree();
  _pRenderFnList();
  _pRenderClosureSummary();
}

function _pRenderFnList() {
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
      <input type="checkbox" class="porter-check" value="${f.id}" data-name="${_esc(f.name)}"
             ${_pIsSelected(f.id) ? 'checked' : ''} onchange="porterToggleFn(this)">
      <span class="porter-row-label">${_esc(f.name)}</span>
      <span class="porter-row-sub">${_esc(f.type)}${f.path ? ' · ' + _esc(f.path) : ''}</span>
    </label>`).join('');

}

/** Build the closure for the current selection.  *quiet*: while ticking
 *  (no status noise).  Returns true when there is something to port. */
async function porterResolve(quiet = false) {
  const seedIds = _pSeedIds();
  const key = seedIds.join(',');
  if (!seedIds.length) {
    _pClosure = null;
    _pClosureKey = '';
    _pRenderClosureSummary();
    if (!quiet) _pStatus('Tick at least one page, frame, button or function.', 'error');
    return false;
  }
  if (_pClosure && key === _pClosureKey) return true;
  try {
    const r = await fetch('/api/porter/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed_ids: seedIds }),
    });
    const d = await r.json();
    if (!r.ok) { _pStatus('Error: ' + d.error, 'error'); return false; }
    _pClosure = d;
    _pClosureKey = key;
    _pFixMapping = {};          // selection changed: map again
    _pRenderClosureSummary();
    if (d.unresolved.length) {
      _pStatus(`⚠ ${d.unresolved.length} referenced function(s) missing in the source: ${d.unresolved.join(', ')}`, 'warn');
    } else if (!quiet) {
      _pStatus(`${d.function_ids.length} function(s) to port.`, 'ok');
    }
    return true;
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
    return false;
  }
}

function _pRenderClosureSummary() {
  const el = document.getElementById('porter-closure-summary');
  if (!el) return;
  if (!_pClosure) {
    el.innerHTML = '<div class="porter-summary-box">Nothing ticked yet.</div>';
    return;
  }

  const c = _pClosure;
  const nDep = c.function_ids.length - c.seed_ids.length;
  let html = `<div class="porter-summary-box">
    To port: <strong>${c.function_ids.length}</strong> function(s) —
    <strong>${c.seed_ids.length}</strong> ticked
    ${nDep ? `+ <strong>${nDep}</strong> they need (chaser steps, collection members…)` : ''}
    · using <strong>${c.fixture_ids.length}</strong> source fixture(s)
    ${_pVcScope.length ? ` · <strong>${_pVcScope.length}</strong> VC widget(s) come along` : ''}`;

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
        body: JSON.stringify({ fixture_ids: _pClosure.fixture_ids, strategy: _pStrategy() }),
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
        <option value="fan_in" ${_pFanoutMode === 'fan_in' ? 'selected' : ''}>Fan-in (several sources → one target)</option>
      </select>
    </label>
    <label style="margin-left:1rem" data-tooltip="E.g. the ceiling spots when porting into a floor-only rig">
      <input type="checkbox" ${_pDropUnmapped ? 'checked' : ''} onchange="_pDropUnmapped = this.checked">
      Leave out source fixtures with no target</label>
    <label style="margin-left:1rem" data-tooltip="Missing channels get their neutral value (no LTP bleed)">
      <input type="checkbox" ${_pCompleteCh ? 'checked' : ''} onchange="_pCompleteCh = this.checked">
      Declare every channel</label>
    <label style="margin-left:1rem">Name prefix:
      <input type="text" id="porter-name-prefix" class="filter-input" style="width:150px"
             value="${_esc(_pNamePrefix)}" placeholder="e.g. SHOW2 / "
             oninput="_pNamePrefix = this.value">
    </label>
  </div>`;

  container.innerHTML = html;
  _pDrawPlans();
  _pStatus(`${_pCandidates.source_fixtures.length} source fixture(s) to map.`, 'info');
}

function porterUpdateMapping(srcId, selectEl) {
  const selected = Array.from(selectEl.selectedOptions).map(o => o.value);
  _pFixMapping[srcId] = selected;
  _pDrawPlans();
}

// ── Stage plans (top view, drawn with the Fixtures tab's drawStageTopView) ──

async function _pFetchPlan(side) {
  try {
    const r = await fetch('/api/porter/stage/' + side);
    _pPlans[side] = r.ok ? await r.json() : null;
  } catch (e) { _pPlans[side] = null; }
}

const _P_MAP_COLORS = ['#f38ba8', '#89b4fa', '#a6e3a1', '#f9e2af', '#cba6f7', '#fab387',
                       '#94e2d5', '#eba0ac', '#74c7ec', '#b4befe', '#f5c2e7', '#89dceb'];

/** Step 3 colours: one per target fixture; its sources get the same colour. */
function _pMappingColors() {
  const tgtIds = (_pTgtFixtures || []).map(f => String(f.id))
    .filter(id => Object.values(_pFixMapping).some(ts => ts.map(String).includes(id)));
  const tgt = {};
  tgtIds.forEach((id, i) => { tgt[id] = _P_MAP_COLORS[i % _P_MAP_COLORS.length]; });
  const src = {};
  for (const [s, ts] of Object.entries(_pFixMapping)) {
    const t = (ts || []).map(String).find(id => tgt[id]);
    if (t) src[String(s)] = tgt[t];
  }
  return { src, tgt };
}

function _pDrawPlans() {
  if (typeof drawStageTopView !== 'function') return;
  const step = _pStep === 3 ? 3 : 1;
  const colors = step === 3 ? _pMappingColors() : null;
  for (const side of ['source', 'target']) {
    const cv = document.getElementById(`porter-plan-${side}-${step}`);
    if (!cv || !cv.parentElement || cv.parentElement.offsetParent === null) continue;
    cv.width = cv.parentElement.clientWidth || 500;
    cv.height = cv.parentElement.clientHeight || 300;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, cv.width, cv.height);
    const plan = _pPlans[side];
    const name = side === 'source' ? _pSrcName : _pTgtName;
    const title = `${side === 'source' ? 'Source' : 'Target'}${name ? ': ' + name : ''}`;
    if (!plan || !plan.has_positions) {
      ctx.fillStyle = _cv('--overlay0');
      ctx.font = '12px monospace';
      ctx.fillText(plan ? `${title} — no 3D positions saved in this file` : `${title} — not loaded`, 12, 22);
      continue;
    }
    let rig = plan.fixtures;
    if (colors) {
      const map = side === 'source' ? colors.src : colors.tgt;
      rig = rig.map(f => Object.assign({}, f, { color: map[String(f.id)] || '#585b70' }));
    }
    drawStageTopView(ctx, cv.width, cv.height, plan.stage, rig, {
      title: title + '  (top view)',
      label: f => `[${f.id}] ${(f.name || '').substring(0, 12)}`,
    });
  }
}

window.addEventListener('resize', () => { if (_pStep === 1 || _pStep === 3) _pDrawPlans(); });

function porterToggleMirror(srcId, checked) {
  if (checked) _pMirrorFixtures.add(srcId);
  else _pMirrorFixtures.delete(srcId);
}

function porterSetFanout(mode) { _pFanoutMode = mode; }

function _pStrategy() {
  const el = document.getElementById('porter-automap-strategy');
  return el ? el.value : 'all';
}

function porterAutoMap() {
  const st = _pStrategy();
  if (st === 'fan_in') { _pFanoutMode = 'fan_in'; _pDropUnmapped = true; }
  else if (st === 'same_id') { _pFanoutMode = 'manual'; _pDropUnmapped = true; }
  else if (_pFanoutMode === 'fan_in' || _pFanoutMode === 'manual') _pFanoutMode = 'pattern_repeat';
  _pFixMapping = {};
  _pRenderMapFixtures();
}

// ── VC options (step 4) ─────────────────────────────────────────────────────

async function _pRenderVcOptions() {
  const sel = document.getElementById('porter-vc-page');
  if (!sel) return;
  let pages = [];
  try {
    const r = await fetch('/api/porter/target/pages');
    pages = r.ok ? await r.json() : [];
  } catch (e) { pages = []; }
  sel.innerHTML = '<option value="">➕ A new page</option>' +
    pages.map(p => `<option value="${_esc(p.id)}" ${String(_pVc.target_page) === String(p.id) ? 'selected' : ''}>${_esc(p.caption || '(page ' + p.id + ')')}</option>`).join('');
  document.getElementById('porter-vc-enabled').checked = _pVc.enabled;
  document.getElementById('porter-vc-caption').value = _pVc.page_caption;
  document.getElementById('porter-vc-caption').placeholder = 'Ported from ' + (_pSrcName || 'source');
  document.getElementById('porter-vc-bindings').value = _pVc.bindings;
}

function porterVcOpt() {
  _pVc = {
    enabled:      document.getElementById('porter-vc-enabled').checked,
    target_page:  document.getElementById('porter-vc-page').value,
    page_caption: document.getElementById('porter-vc-caption').value,
    bindings:     document.getElementById('porter-vc-bindings').value,
  };
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
      if (r.status === 422 && d.findings) {
        const box = document.getElementById('porter-validation-result');
        if (box) box.innerHTML = '<div class="porter-val-section porter-val-errors"><h4>Doctor: new errors — not exported</h4><ul>'
          + d.findings.map(f => `<li>${_esc(f)}</li>`).join('') + '</ul></div>';
      }
      _pStatus('Export blocked: ' + (d.error || 'Unknown'), 'error');
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
    let reportName = '';
    const fullPath = saveFileWithPicker.lastPath;
    if (fullPath) {
      try {
        const rr = await fetch('/api/porter/save-report', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ qxw_path: fullPath }),
        });
        const dd = await rr.json();
        if (rr.ok) reportName = dd.name;
      } catch (e) { /* non-fatal */ }
    }
    let summary = {};
    try { const rs = await fetch('/api/porter/last-result'); summary = rs.ok ? await rs.json() : {}; } catch (e) { /* ignore */ }
    _pStatus(`Saved: ${savedName}` + (reportName ? ` (+ ${reportName})` : ' — use 📋 Copy Report for the import report'), 'ok');
    porterGoStep(5);
    _pRenderDone(savedName, summary, reportName);
  } catch (e) {
    _pStatus('Network error: ' + e.message, 'error');
  }
}

function _pRenderDone(filename, summary, reportName) {
  const el = document.getElementById('porter-panel-5');
  if (!el) return;
  summary = summary || {};
  const doc = summary.doctor || {};
  const li = (arr) => (arr || []).map(x => `<li>${_esc(x)}</li>`).join('');
  el.innerHTML = `
    <div class="porter-done">
      <h3>Import complete</h3>
      <p>Saved as: <strong>${_esc(filename)}</strong>${reportName ? ` · report: <strong>${_esc(reportName)}</strong>` : ''}</p>
      <p>${summary.functions ?? _pClosure.function_ids.length} function(s) ported
         ${summary.pruned && summary.pruned.length ? `(${summary.pruned.length} left out: none of their fixtures is in the target)` : ''}.</p>
      ${summary.vc ? `<ul>${li(summary.vc.summary)}</ul>` : ''}
      ${summary.panic && summary.panic.length ? `<ul>${li(summary.panic.map(p => 'PANIC RESET: ' + p))}</ul>` : ''}
      <p>Doctor: ${(doc.errors || []).length} new error(s), ${(doc.warnings || []).length} new warning(s)
         (file: ${doc.total_errors ?? '?'} error(s), ${doc.total_warnings ?? '?'} warning(s)).</p>
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
  _pManual = new Set();
  _pExcluded = new Set();
  _pVcScope = [];
  _pVcSeeds = [];
  _pClosureKey = '';
  _pDropUnmapped = false;
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
    drop_unmapped:   _pDropUnmapped,
    complete_channels: _pCompleteCh,
    vc: Object.assign({}, _pVc, { scope: _pVcScope }),
  };
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
