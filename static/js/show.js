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
    ch.textContent = n ? `${n} change${n > 1 ? 's' : ''}, not saved`
      : (_show.saved_name ? `saved as ${_show.saved_name}` : 'no changes yet');
    ch.className = 'sb-pill' + (n ? ' sb-unsaved' : '');
    ch.title = n ? 'Open the History to see every change' : '';
  }
  const d = _show.doctor, dr = document.getElementById('sb-doctor');
  if (dr) {
    if (d) {
      const e = d.error || 0, w = d.warning || 0;
      dr.innerHTML = `<span class="sb-long">Doctor: ${e} error${e === 1 ? '' : 's'} · ${w} warning${w === 1 ? '' : 's'}</span>` +
        `<span class="sb-short">Doctor ${e} err · ${w} warn</span>`;
      dr.className = 'sb-pill sb-doctor ' + (e ? 'sb-bad' : w ? 'sb-warn' : 'sb-good');
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
  if (cnt) cnt.textContent = steps.length ? `(${steps.length})` : '';
  if (!steps.length) {
    list.innerHTML = '<li class="sc-empty">No changes yet — each tool you apply adds a line here.</li>';
    return;
  }
  const SHOW = 5;
  const more = steps.length - SHOW;
  list.innerHTML = (more > 0 ? `<li class="sc-more" onclick="showHistoryToggle(true)">+ ${more} earlier…</li>` : '') +
    steps.slice(-SHOW).map(s => `<li class="sc-row${s.saved ? ' sc-saved' : ''}" title="${_esc(s.tool_title + ' — ' + s.title + (s.detail ? '\n' + s.detail : ''))}">
      <span class="sc-n">${s.n}</span>
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
    setStatus(`✓ Applied to the show — step ${s.n}: ${s.title}.${doc} 💾 Save as new file… when you're ready.`, 'ok');
    await showRefresh();
    return d;
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
    return null;
  }
}

async function doctorApply() {
  if (typeof _docSel === 'undefined' || !_docSel.size) return;
  const d = await showApply('/api/doctor/apply', { keys: [..._docSel] }, 'Fixing the show…');
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
  _vceStatus(`✓ ${n} widget change(s) applied to the show — 💾 Save as new file… when you're ready.`, 'ok');
}

async function slApply() {
  if (typeof slSaveDetails === 'function') await slSaveDetails();
  setStatus('Building the setlist chasers in the show…', 'info');
  const r = await fetch('/api/setlist/apply-all', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  const d = await r.json();
  if (!r.ok || d.error) { setStatus(d.error || 'Failed.', 'error'); return; }
  setStatus('✓ Setlist chasers built in the show — 💾 Save as new file… when you\'re ready.', 'ok');
  await showRefresh();
  if (typeof _fetchChasers === 'function') await _fetchChasers();
}
