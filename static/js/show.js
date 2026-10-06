// =============================================================================
// The show in progress (WORKPLAN Phase 2.6)
// Every tool changes one working copy of the open show; each change is a step
// in its History (undo any step); 💾 Save as new file… writes it all at once,
// with one report.  The header shows it; sidebar tools that changed the show
// get an orange dot until it is saved.
// =============================================================================

let _show = { active: false, unsaved: 0, version: -1, changed_tools: {} };
let _showTimer = null;

const _SHOW_INVALIDATE = {
  idbrowser: '_invalidateIdBrowser', setlist: 'invalidateSetlist', dictionary: 'invalidateDictionary',
  checklist: 'invalidateChecklist', techrider: 'invalidateTechRider', triggers: 'invalidateTriggers',
  fixtures: 'invalidateFixtures', brightness: 'invalidateBrightness', showbook: 'invalidateShowbook',
  doctor: 'invalidateDoctor', reducer: 'invalidateReducer', looks: 'invalidateLooks',
  stage: 'invalidateStage', vceditor: 'invalidateVcEditor', porter: 'invalidatePorter',
  compare: 'invalidateCompare', inputs: 'invalidateInputs',
};

function _activeScreen() {
  const s = document.querySelector('.screen.active');
  return s ? s.id.replace('scr-', '') : '';
}

/** The show changed in the tool on screen: the other tools start again from it
 *  next time they are opened; the header counts follow. */
async function _showChangedElsewhere() {
  const here = _activeScreen();
  Object.entries(_SHOW_INVALIDATE).forEach(([scr, fn]) => {
    if (scr !== here && typeof window[fn] === 'function') window[fn]();
  });
  try { _updateHeader(await _apiJson('/api/status')); } catch { /* header only */ }
}

function showRefreshSoon(delay = 250) {
  clearTimeout(_showTimer);
  _showTimer = setTimeout(showRefresh, delay);
}

async function showRefresh() {
  let st;
  try {
    const r = await _origFetch('/api/show/status');
    st = await r.json();
  } catch { return; }
  const changed = st.active && _show.active && st.version !== _show.version;
  _show = st;
  _renderShowBar();
  _renderSideChanges();
  if (typeof routeSync === 'function') routeSync(st.changed_tools);
  if (changed) _showChangedElsewhere();
  if (document.getElementById('show-history')?.classList.contains('open')) showHistoryRender();
}

function _renderShowBar() {
  const bar = document.getElementById('show-bar');
  if (!bar) return;
  bar.hidden = !_show.active;
  const n = _show.unsaved || 0;
  const ch = document.getElementById('sb-changes');
  if (ch) {
    ch.innerHTML = n ? `<b>${n}</b><small>unsaved change${n > 1 ? 's' : ''}</small>`
      : (_show.saved_name ? `<b>✓</b><small title="${_esc(_show.saved_name)}">saved</small>` : '<b>0</b><small>changes</small>');
    ch.className = 'sb-pill sb-card' + (n ? ' sb-unsaved' : '');
    ch.title = n ? 'Open the History to see every change' : '';
  }
  const d = _show.doctor, dr = document.getElementById('sb-doctor');
  if (dr) {
    if (d) {
      const e = d.error || 0, w = d.warning || 0;
      dr.innerHTML = `<b>${e} · ${w}</b><small>Doctor err · warn</small>`;
      dr.title = `Workspace Doctor on the show as it is now: ${e} error${e === 1 ? '' : 's'}, ${w} warning${w === 1 ? '' : 's'} — click to open it`;
      dr.className = 'sb-pill sb-card sb-doctor ' + (e ? 'sb-bad' : w ? 'sb-warn' : 'sb-good');
      dr.hidden = false;
    } else dr.hidden = true;
  }
  const u = document.getElementById('sb-undo');
  if (u) u.disabled = !(_show.steps > 0);
  const s = document.getElementById('sb-save');
  if (s) s.title = `Save the show as a new file (${_show.suggested_name || ''}) with a report of every change — the file you opened is never touched`;
  // orange dots: tools that changed the show since it was opened / saved
  document.querySelectorAll('.sn-item[id^="sn-"]').forEach(btn => {
    const tool = btn.id.slice(3);
    const k = (_show.changed_tools || {})[tool] || 0;
    let dot = btn.querySelector('.sn-dot');
    if (k && !dot) { dot = document.createElement('i'); dot.className = 'sn-dot'; btn.appendChild(dot); }
    if (dot) {
      dot.hidden = !k;
      dot.title = k ? `${k} change${k > 1 ? 's' : ''} in the show, not saved yet` : '';
    }
  });
  window._showUnsaved = n;
}

// Every change a tool makes goes through a POST/PATCH to /api/…: refresh the
// bar shortly after (tools don't need to know about the show bar).
const _origFetch = window.fetch.bind(window);
window.fetch = function (input, init) {
  const url = typeof input === 'string' ? input : (input && input.url) || '';
  const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
  const p = _origFetch(input, init);
  if (method !== 'GET' && url.startsWith('/api/') && !url.startsWith('/api/show/status')) {
    p.then(() => showRefreshSoon()).catch(() => {});
  }
  return p;
};

// ── Edits a tool still holds in the page (VC Editor drags) ─────────────────

function showPendingEdits() {
  return typeof _vceChanges !== 'undefined' && _vceChanges && Object.keys(_vceChanges).length > 0;
}

async function showFlushPending() {
  if (showPendingEdits() && typeof _vceFlush === 'function') await _vceFlush();
}

// ── Undo / History ───────────────────────────────────────────────────────────

async function showUndo(n) {
  await showFlushPending();
  const r = await _origFetch('/api/show/undo', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(n ? { n } : {}),
  });
  const d = await r.json();
  if (!r.ok || d.error) { setStatus(d.error || 'Undo failed.', 'error'); return; }
  const k = (d.show && d.show.redo) || 0;
  setStatus((n ? `Back to how the show was before step ${n}.` : 'Last change undone.') +
    (k ? ` ↷ Redo brings ${k === 1 ? 'it' : 'them'} back.` : ''));
  _show.version = -2;                  // everything (this screen too) starts again
  await _refreshAfterLoad();
  await showRefresh();
}

async function showRedo() {
  const r = await _origFetch('/api/show/redo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const d = await r.json();
  if (!r.ok || d.error) { setStatus(d.error || 'Nothing to redo.', 'error'); return; }
  setStatus('Redone — the undone steps are back.');
  _show.version = -2;
  await _refreshAfterLoad();
  await showRefresh();
}

/** Undo from the side list: more than the last step asks first. */
function showUndoFromSide(n) {
  const last = _show.steps || 0;
  if (n < last && !confirm(`Undo steps ${n}–${last}? (↷ Redo brings them back until you change the show again.)`)) return;
  showUndo(n);
}

// ── The changes list on the left (under the menu) ────────────────────────────

let _sideVersion = null;
async function _renderSideChanges() {
  const box = document.getElementById('side-changes');
  if (!box) return;
  box.hidden = !_show.active;
  if (!_show.active) return;
  const rb = document.getElementById('sc-redo');
  if (rb) { rb.hidden = !_show.redo; rb.title = `Redo ${_show.redo} undone step(s)`; }
  if (_sideVersion === _show.version) return;
  _sideVersion = _show.version;
  let steps = [];
  try { steps = (await (await _origFetch('/api/show/history')).json()).steps || []; } catch { return; }
  const list = document.getElementById('sc-list');
  const cnt = document.getElementById('sc-count');
  if (cnt) cnt.textContent = steps.length ? `· ${steps.length}` : '';
  if (!steps.length) {
    list.innerHTML = '<li class="sc-empty">No changes yet — each tool you apply adds a step here.</li>';
    return;
  }
  const SHOW = 5;
  const more = steps.length - SHOW;
  list.innerHTML = (more > 0 ? `<li class="sc-more" onclick="showHistoryToggle(true)">+ ${more} earlier…</li>` : '') +
    steps.slice(-SHOW).map(s => `<li class="sc-row${s.saved ? ' sc-saved' : ''}" title="${_esc(s.tool_title + ' — ' + s.title + (s.detail ? '\n' + s.detail : ''))}">
      <span class="sc-n" title="step ${s.n}">${s.saved ? '✓' : s.n}</span>
      <span class="sc-t" onclick="go('${s.tool}')"><b>${_esc(s.tool_title)}</b> ${_esc(s.title)}</span>
      ${s.undoable ? `<button class="sc-undo" title="Undo this step${s.n < steps.length ? ' and the ones after it' : ''}" onclick="showUndoFromSide(${s.n})">↶</button>` : ''}
    </li>`).join('');
}

async function showHistoryToggle(open) {
  await showFlushPending();
  const p = document.getElementById('show-history');
  if (!p) return;
  const on = open === undefined ? !p.classList.contains('open') : open;
  p.classList.toggle('open', on);
  if (on) showHistoryRender();
}

async function showHistoryRender() {
  const list = document.getElementById('sh-list');
  if (!list) return;
  const d = await (await _origFetch('/api/show/history')).json();
  const st = d.show || {};
  document.getElementById('sh-source').textContent = st.source_name || '';
  const fn = document.getElementById('sh-filename');
  if (fn && !fn.dataset.touched) fn.value = st.suggested_name || '';
  const steps = d.steps || [];
  const rd = document.getElementById('sh-redo');
  if (rd) rd.hidden = !st.redo;
  const time = t => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  let html = `<li class="sh-step sh-start"><span class="sh-n">0</span><div class="sh-body">
      <div class="sh-title">Opened ${_esc(st.source_name || '')}</div>
      <div class="sh-sub">the file itself is never changed</div></div></li>`;
  html += steps.map(s => {
    const doc = s.doctor ? `Doctor after: ${s.doctor.error || 0} errors · ${s.doctor.warning || 0} warnings` : '';
    const sub = [s.detail, s.edits > 1 ? `${s.edits} edits` : '', doc, time(s.time)].filter(Boolean).join(' · ');
    return `<li class="sh-step${s.saved ? ' sh-saved' : ''}">
      <span class="sh-n">${s.n}</span>
      <div class="sh-body">
        <div class="sh-title"><b>${_esc(s.tool_title)}</b> — ${_esc(s.title)}${s.saved ? ' <span class="sh-tag">saved</span>' : ''}</div>
        <div class="sh-sub">${_esc(sub)}</div>
      </div>
      <div class="sh-acts">
        ${document.getElementById('sn-' + s.tool) ? `<button class="btn btn-surface btn-sm" onclick="showHistoryToggle(false);go('${s.tool}')">Open tool</button>` : ''}
        ${s.undoable ? `<button class="btn btn-surface btn-sm" title="Go back to how the show was before this step (this step and the ones after it are undone)" onclick="showUndo(${s.n})">↶ Undo from here</button>` : ''}
      </div></li>`;
  }).join('');
  if (!steps.length) html += '<li class="sh-empty">No changes yet. Every tool you apply adds a step here.</li>';
  list.innerHTML = html;
}

// ── Do it again: the recipe and Show Profiles (WORKPLAN 3.1) ─────────────────

async function showSaveRecipe() {
  if (!_show.active) { setStatus('Open a show first.', 'error'); return; }
  await showFlushPending();
  const r = await _origFetch('/api/profile/recipe');
  if (!r.ok) { setStatus('Could not prepare the recipe.', 'error'); return; }
  const n = r.headers.get('X-Calls') || '0';
  const saved = await saveFileWithPicker(await r.blob(), r.headers.get('X-Suggested-Filename') || 'show.recipe.json',
    [{ description: 'Swiss Knife recipe', accept: { 'application/json': ['.json'] } }], 'Save the recipe');
  if (saved) setStatus(`Recipe saved: ${saved} — ${n} change(s). Replay it: python -m core.recipe replay ${saved}` +
    ' (add --onto <other show>.qxw to do it on another show).', 'ok');
}

let _shProfiles = [];
async function showProfilesLoad() {
  const d = await (await _origFetch('/api/profile/list')).json();
  _shProfiles = d.profiles || [];
  const sel = document.getElementById('sh-prof-list');
  if (sel) sel.innerHTML = _shProfiles.length
    ? _shProfiles.map(p => `<option value="${_esc(p.name)}" title="${_esc(p.description || '')}">${_esc(p.name)} — ${p.rig ? p.fixtures + ' fixtures · ' : ''}${p.steps} step${p.steps === 1 ? '' : 's'}${p.params.length ? ' · needs ' + _esc(p.params.join(', ')) : ''}</option>`).join('')
    : '<option value="">no profiles yet — save one above</option>';
  showProfSelected();
  try {
    const f = await (await _origFetch('/api/profile/folder')).json();
    const w = document.getElementById('sh-prof-where');
    if (w) w.textContent = 'Profiles are kept in ' + f.path;
  } catch { /* optional */ }
  // the rig of Quick Start can go into the profile
  try {
    const q = await (await _origFetch('/api/quickstart/status')).json();
    const row = document.getElementById('sh-prof-rig-row');
    if (row) { row.hidden = !q.fixture_count; document.getElementById('sh-prof-rig-n').textContent = q.fixture_count || 0; }
  } catch { /* optional */ }
}

/** "▶ Start a show" is offered for a profile that keeps its own rig. */
function showProfSelected() {
  const sel = document.getElementById('sh-prof-list');
  const p = _shProfiles.find(x => x.name === (sel && sel.value));
  const b = document.getElementById('sh-prof-start');
  if (b) b.hidden = !(p && p.rig);
  const e = document.getElementById('sh-prof-edit');
  if (e) { e.hidden = true; e.innerHTML = ''; }
}

async function showSaveProfile() {
  const name = document.getElementById('sh-prof-name').value.trim();
  if (!name) { setStatus('Give the profile a name.', 'warn'); return; }
  await showFlushPending();
  const rig = !!(document.getElementById('sh-prof-rig') || {}).checked;
  const r = await _origFetch('/api/profile/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: document.getElementById('sh-prof-desc').value, include_rig: rig,
                           stage: typeof _qsStage !== 'undefined' ? _qsStage : undefined }) });
  const d = await r.json();
  if (!r.ok) { setStatus('✗ ' + d.error, 'error'); return; }
  document.getElementById('sh-prof-new').hidden = true;
  setStatus(`★ Profile '${d.name}' saved — ${d.steps} step(s)` + (d.rig ? ' and the rig' : '') + (d.params.length ? `, needs ${d.params.join(', ')}` : '') +
    (d.rig ? '. It can start a show from nothing: ▶ Start a show here, or python -m core.profile build "' + d.name + '" --out <new>.qxw'
           : '. Apply it to another show from here, or: python -m core.profile build "' + d.name + '" --show <show>.qxw'), 'ok');
  await showProfilesLoad();
  const sel = document.getElementById('sh-prof-list');
  if (sel) { sel.value = d.name; showProfSelected(); }
}

async function showApplyProfileFile() {
  const path = await nativePick('Profile or recipe', [{ label: 'Profile / recipe', exts: ['.json'] }]);
  if (path) showApplyProfile(path);
  else if (nativePick.unavailable) setStatus('Copy the file into the profiles folder, then pick it in the list.', 'warn');
}

async function showApplyProfile(path) {
  if (!_show.active) { setStatus('Open a show first.', 'error'); return; }
  const name = path ? '' : document.getElementById('sh-prof-list').value;
  if (!name && !path) { setStatus('Save a profile first, or pick one from a file.', 'warn'); return; }
  const params = {};
  document.querySelectorAll('#sh-prof-params input[data-param]').forEach(i => { params[i.dataset.param] = i.value.trim(); });
  await showFlushPending();
  const box = document.getElementById('sh-prof-result');
  box.textContent = 'Applying…';
  const r = await _origFetch('/api/profile/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path: path || '', params }) });
  const d = await r.json();
  if (!r.ok) {
    box.textContent = '';
    if (d.params && d.params.length) _showParamInputs(d.params, path);
    setStatus('✗ ' + d.error, 'error');
    return;
  }
  document.getElementById('sh-prof-params').innerHTML = '';
  _showProfResult(d, box);
  await showRefresh();
  showHistoryRender();
}

function _showProfResult(d, box) {
  const bad = d.steps.filter(s => s.status !== 'applied');
  const notes = d.steps.filter(s => s.status === 'applied' && s.note);
  box.innerHTML = (d.started ? `Started from the rig: <b>${d.started.fixtures}</b> fixture(s). ` : '') +
    `<b>${_esc(d.name)}</b>: ${d.applied} applied` +
    (d.skipped ? `, <span class="skip">${d.skipped} left out</span>` : '') + (d.failed ? `, <span class="fail">${d.failed} failed</span>` : '') +
    (bad.length || notes.length ? '<ul>' + bad.map(s => `<li class="${s.status === 'failed' ? 'fail' : 'skip'}">${s.n}. ${_esc(s.title)} — ${_esc(s.why || '')}</li>`).join('') +
      notes.map(s => `<li>${s.n}. ${_esc(s.title)} — ${_esc(s.note)}</li>`).join('') + '</ul>' : '');
  setStatus(`▶ Profile '${d.name}': ${d.applied} step(s) applied` + (d.skipped + d.failed ? `, ${d.skipped + d.failed} not — see the History` : '') +
    '. Each one is a step of the History (↶ undo works).', d.skipped + d.failed ? 'warn' : 'ok');
}

/** A profile with its own rig builds a show from nothing (the show open now is replaced). */
async function showStartProfile(path) {
  const name = path ? '' : document.getElementById('sh-prof-list').value;
  if (!name && !path) { setStatus('Save a profile first, or pick one from a file.', 'warn'); return; }
  if (_show.active && !showConfirmDiscard('Starting a new show from the profile')) return;
  const params = {};
  document.querySelectorAll('#sh-prof-params input[data-param]').forEach(i => { params[i.dataset.param] = i.value.trim(); });
  const box = document.getElementById('sh-prof-result');
  box.textContent = 'Building the show…';
  const r = await _origFetch('/api/profile/start', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path: path || '', params }) });
  const d = await r.json();
  if (!r.ok) {
    box.textContent = '';
    if (d.params && d.params.length) _showParamInputs(d.params, path);
    setStatus('✗ ' + d.error, 'error');
    return;
  }
  document.getElementById('sh-prof-params').innerHTML = '';
  if (typeof _refreshAfterLoad === 'function') await _refreshAfterLoad();
  _showProfResult(d, box);
  await showRefresh();
  showHistoryRender();
}

// ── The step editor: drop, reorder, rename ───────────────────────────────────
let _speSteps = [];       // [{n, title, drop}] in the current order
let _speName = '';

async function showEditProfile() {
  const sel = document.getElementById('sh-prof-list');
  const name = sel && sel.value;
  if (!name) { setStatus('Pick a profile to edit.', 'warn'); return; }
  const r = await _origFetch('/api/profile/steps?name=' + encodeURIComponent(name));
  const d = await r.json();
  if (!r.ok) { setStatus('✗ ' + d.error, 'error'); return; }
  _speName = d.name;
  _speSteps = d.steps.map(s => ({ n: s.n, title: s.title, orig: s.title, drop: false }));
  _speRender();
}

function _speRender() {
  const box = document.getElementById('sh-prof-edit');
  if (!box) return;
  box.hidden = false;
  box.innerHTML = `<div class="sh-note">Steps of <b>${_esc(_speName)}</b> — ↑ ↓ to reorder, ✕ to drop, edit a title to rename. (Order matters: a step may use what an earlier one made.)</div>` +
    _speSteps.map((s, i) => `<div class="spe-row${s.drop ? ' dropped' : ''}">
      <span class="spe-n">${i + 1}</span>
      <input class="filter-input" value="${_esc(s.title)}" oninput="_speSteps[${i}].title = this.value" aria-label="Step ${i + 1} title">
      <button class="btn btn-surface btn-sm" onclick="_speMove(${i}, -1)" ${i === 0 ? 'disabled' : ''} title="Earlier">↑</button>
      <button class="btn btn-surface btn-sm" onclick="_speMove(${i}, 1)" ${i === _speSteps.length - 1 ? 'disabled' : ''} title="Later">↓</button>
      <button class="btn btn-surface btn-sm" onclick="_speSteps[${i}].drop = !_speSteps[${i}].drop; _speRender()" title="${s.drop ? 'Keep this step' : 'Drop this step'}">${s.drop ? '↺' : '✕'}</button>
    </div>`).join('') +
    `<div class="sh-row"><button class="btn btn-accent btn-sm" onclick="showSaveProfileEdit()">✓ Save the changes</button>
      <button class="btn btn-surface btn-sm" onclick="showProfSelected()">Cancel</button></div>`;
}

function _speMove(i, d) {
  const j = i + d;
  if (j < 0 || j >= _speSteps.length) return;
  [_speSteps[i], _speSteps[j]] = [_speSteps[j], _speSteps[i]];
  _speRender();
}

async function showSaveProfileEdit() {
  const kept = _speSteps.filter(s => !s.drop);
  const titles = {};
  kept.forEach(s => { if (s.title.trim() && s.title !== s.orig) titles[s.n] = s.title.trim(); });
  const r = await _origFetch('/api/profile/edit', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: _speName, order: kept.map(s => s.n), titles }) });
  const d = await r.json();
  if (!r.ok) { setStatus('✗ ' + d.error, 'error'); return; }
  setStatus(`✎ Profile '${d.name}': ${d.steps} step(s) kept.`, 'ok');
  await showProfilesLoad();
  const sel = document.getElementById('sh-prof-list');
  if (sel) sel.value = d.name;
  showProfSelected();
}

function _showParamInputs(names, path) {
  const el = document.getElementById('sh-prof-params');
  el.innerHTML = '<div class="sh-note">This profile uses files — give them here (or put them next to the profile):</div>' +
    names.map(n => `<div class="sh-param"><span>${_esc(n)}</span><input class="filter-input" data-param="${_esc(n)}" placeholder="/path/to/${_esc(n)}">
      <button class="btn btn-surface btn-sm" onclick="(async b => { const p = await nativePick('${_esc(n)}'); if (p) b.previousElementSibling.value = p; })(this)">…</button></div>`).join('') +
    `<button class="btn btn-accent btn-sm" onclick="showApplyProfile(${path ? `'${_esc(path).replace(/'/g, "\\'")}'` : ''})">▶ Apply with these files</button>`;
}

// ── Save ─────────────────────────────────────────────────────────────────────

async function showSave() {
  if (!_show.active) { setStatus('Open a show first.', 'error'); return; }
  const fnEl = document.getElementById('sh-filename');
  await showFlushPending();
  const name = (fnEl && fnEl.value.trim()) || _show.suggested_name || 'show.qxw';
  setStatus('Preparing the show…');
  const r = await _origFetch('/api/show/file');
  if (!r.ok) { setStatus('Could not prepare the show.', 'error'); return; }
  const blob = await r.blob();
  const saved = await saveFileWithPicker(blob, name.endsWith('.qxw') ? name : name + '.qxw',
    [{ description: 'QLC+ workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save the show as a new file');
  if (!saved) { setStatus('Save cancelled.'); return; }
  const m = await (await _origFetch('/api/show/saved', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ qxw_path: saveFileWithPicker.lastPath || '', name: saved }),
  })).json();
  if (fnEl) delete fnEl.dataset.touched;
  setStatus(`Saved ${saved}` + (m.report_name ? ` + ${m.report_name}` : '') +
    (m.recipe_name ? ` + ${m.recipe_name}` : '') +
    ' — the file you opened is unchanged. You can keep working.');
  await showRefresh();
}

/** Ask before dropping unsaved changes (open another file, reload, quit). */
function showConfirmDiscard(what) {
  const n = window._showUnsaved || 0;
  if (!n) return true;
  return confirm(`The show in progress has ${n} unsaved change${n > 1 ? 's' : ''}.\n\n` +
    `${what} discards them. Continue?\n\n(Cancel, then 💾 Save as new file… to keep them.)`);
}

document.addEventListener('DOMContentLoaded', () => showRefreshSoon(50));

// ── Apply to the show (tools) ────────────────────────────────────────────────

/** POST a tool's plan to its /apply route: the result becomes the show in
 *  progress (a step in the History).  Returns the JSON, or null on error. */
async function showApply(url, body, busy = 'Applying…') {
  setStatus(busy, 'info');
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}) });
    const d = await r.json();
    if (!r.ok || d.error) {
      setStatus((d.error || 'Failed.') + (d.findings ? ' ' + d.findings.slice(0, 3).join(' | ') : ''), 'error');
      return null;
    }
    const s = d.step || {};
    const doc = d.show && d.show.doctor ? ` Doctor: ${d.show.doctor.error || 0} errors, ${d.show.doctor.warning || 0} warnings.` : '';
    setStatus(`✓ Applied to the show — step ${s.n}: ${s.title}.${doc} 💾 Save as new file… (top right) when you're ready.`, 'ok');
    await showRefresh();
    return d;
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
    return null;
  }
}

async function doctorApply() {
  if (typeof _docSel === 'undefined' || !_docSel.size) return;
  const d = await showApply('/api/doctor/apply', { keys: [..._docSel], options: _docOptions() }, 'Fixing the show…');
  if (d) doctorCheck();
}

async function reducerApply() {
  const d = await showApply('/api/reducer/apply', _rrPlan(), 'Reducing the show…');
  if (d) { invalidateReducer(); }
}

async function looksApply() {
  const d = await showApply('/api/looks/apply', _lbPlan(), 'Adding the looks to the show…');
  if (d) { invalidateLooks(); }
}

async function brtApply() {
  if (!_brtFixtures.length) { setStatus('Load a workspace first.', 'warn'); return; }
  const scales = _brtBuildScales();
  if (!Object.values(scales).some(v => Math.abs(v - 1.0) > 0.001)) {
    setStatus('All fixtures are at 100% — nothing to change.', 'warn'); return;
  }
  const d = await showApply('/api/brightness/apply-show', { scales, manual_dimmer_offsets: _brtManual },
    'Scaling the brightness…');
  if (d) { _brtLoaded = false; invalidateBrightness(); ensureBrightnessLoaded(); }
}

async function vceApply() {
  const n = Object.keys(_vceChanges || {}).length;
  if (!n) { _vceStatus('Every edit is already in the show.', 'ok'); return; }
  if (!(await _vceFlush())) return;
  _vceStatus(`✓ ${n} widget change(s) applied to the show — 💾 Save as new file… (top right) when you're ready.`, 'ok');
}

async function slApply() {
  if (typeof slSaveDetails === 'function') await slSaveDetails();
  setStatus('Building the setlist chasers in the show…', 'info');
  const r = await fetch('/api/setlist/apply-all', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  const d = await r.json();
  if (!r.ok || d.error) { setStatus(d.error || 'Failed.', 'error'); return; }
  if (d.skipped && d.skipped.length)
    setStatus(`⚠ Setlist built, but ${d.skipped.length} song(s) have no function and are not in the cue list: ${d.skipped.join(', ')} — assign them and apply again.`, 'warn');
  else
    setStatus('✓ Setlist chasers built in the show — 💾 Save as new file… when you\'re ready.', 'ok');
  await showRefresh();
  if (typeof _fetchChasers === 'function') await _fetchChasers();
}
