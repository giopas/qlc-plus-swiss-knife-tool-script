/**
 * Workspace Doctor tab (WORKPLAN Phase 2.1).
 *
 * Check runs the Doctor on the open workspace; findings are grouped by
 * code, fixable ones get a tick box (recommended fixes ticked; removals of
 * functions — D004 / D015 / D016 — are offered but not ticked).
 * Fix selected writes a NEW workspace (Save dialog, default
 * <name>_v<N+1>.qxw) and the fix report next to it.  The open workspace
 * and its file are never changed.
 */

let _docData = null;          // last /api/doctor/check result
let _docSel = new Set();      // ticked finding keys
let _docOpen = new Set();     // expanded codes
let _docFilter = 'attention'; // 'attention' (errors and warnings) | 'error' | 'warning' | 'info'
const _DOC_SHOW = 150;
// per-kind choices (v2.4): how a fix is done; sent with the fix as `options`
let _docOpt = { d003: 'unlink', d004: 'merge', d015: 'remove', d013mode: 'ms', d013val: 500 };
function _docOptions() {
  const o = { d003: _docOpt.d003, d004: _docOpt.d004, d015: _docOpt.d015 };
  const v = Number(_docOpt.d013val) || 0;
  if (v > 0) o.d013 = _docOpt.d013mode === 'bpm' ? { bpm: v } : { ms: v };
  return o;
}
function doctorOpt(k, v) { _docOpt[k] = v; if (k === 'd013mode') _docOpt.d013val = v === 'bpm' ? 120 : 500; doctorRender(); }
function _docOptBar(code) {
  const sel = (k, opts) => `<select onchange="doctorOpt('${k}', this.value)" aria-label="${code} option">` +
    opts.map(([v, t]) => `<option value="${v}" ${_docOpt[k] === v ? 'selected' : ''}>${t}</option>`).join('') + '</select>';
  if (code === 'D003') return `<div class="doc-opt">When a link is broken: ${sel('d003', [['unlink', 'remove the link'], ['rewire', 'rewire to the function with the same name, else remove']])}</div>`;
  if (code === 'D004') return `<div class="doc-opt">A chaser with one step: ${sel('d004', [['merge', 'merge it into its scene'], ['remove', 'remove it']])}</div>`;
  if (code === 'D015') return `<div class="doc-opt">Unnamed functions: ${sel('d015', [['remove', 'remove when unused'], ['rename', 'name them from where they are used']])}</div>`;
  if (code === 'D013') return `<div class="doc-opt">Give 0 ms steps ${sel('d013mode', [['ms', 'a duration in ms'], ['bpm', 'a tempo in BPM']])}
    <input type="number" min="1" style="width:5em" value="${_docOpt.d013val}" onchange="_docOpt.d013val = this.value" aria-label="${_docOpt.d013mode === 'bpm' ? 'BPM' : 'milliseconds'}"> ${_docOpt.d013mode === 'bpm' ? 'BPM (one beat per step)' : 'ms'}</div>`;
  return '';
}        // rows shown per code (the rest follow the group tick)

// what each rule means, in everyday words (3.9.5, stage E); the technical title stays beside it
const _DOC_PLAIN = {
  D001: 'The file is not a QLC+ show.',
  D002: 'Two items share one ID, so QLC+ can mix them up.',
  D003: 'Something points to a function that no longer exists.',
  D004: 'A chaser with fewer than two steps does nothing a scene would not.',
  D005: 'A scene leaves some channels out, so older values can stay on.',
  D006: 'A strobe or built-in program channel is on outside an effect.',
  D007: 'A button and a chaser step use the same scene and can fight.',
  D008: 'The Virtual Console has no panic button to black everything out.',
  D009: 'Two fixtures use the same DMX channels.',
  D010: 'The setlist page is not the first page of the Virtual Console.',
  D011: 'A widget sits outside its page or frame, so you cannot see it.',
  D012: 'Buttons listen to a controller that is not patched, so they stay silent.',
  D013: 'Chaser steps with no duration go by instantly.',
  D014: 'A cue list plays a chaser that has no steps.',
  D015: 'A function has no name.',
  D016: 'No button, cue or chaser uses this function.',
  D017: 'The panic reset is a scene, so it cannot darken what is running.',
  D018: 'A setlist song whose look lights nothing: the stage goes dark.',
  D019: 'A palette or fixture group that the show uses is missing.',
  D020: 'A palette sets nothing on its fixtures.',
  D021: 'The fixture mode is not in its definition, so QLC+ treats it as a plain dimmer.',
  D022: 'The channel count differs from the one in the definition.',
  D023: 'A scene sets a channel the fixture does not have.',
  I001: 'A button used only as a text label.',
  I002: 'The pages of your Virtual Console.',
  I003: 'No fixture definition found, so channel checks are skipped.',
  I004: 'Layer scenes, meant to be played together.',
  I005: 'Show Wizard functions that no button plays.',
  I006: 'Fixtures that switch pages, not lights.',
  I007: 'A Show Wizard effect that was never created.',
  I008: 'QLC+ 5.3 content that QLC+ 5.2.2 ignores.',
  I009: 'A fixture definition QLC+ does not ship; it travels with the show.',
};

function doctorInit() {
  if (_docData) return;
  // a show is open: check it straight away (the list follows the show in progress)
  if (typeof _show !== 'undefined' && _show.active) doctorCheck(); else _docRenderEmpty();
}

function _docStatus(msg, level) {
  // the app's single status bar (like the Porter)
  if (typeof setStatus === 'function') setStatus(msg, level || 'info');
}

function _docRenderEmpty() {
  const el = document.getElementById('doc-list');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace and press Check.</div>';
}

async function doctorCheck() {
  _docStatus('Checking…', 'info');
  document.getElementById('doc-result').hidden = true;
  try {
    const r = await fetch('/api/doctor/check');
    const d = await r.json();
    if (!r.ok) { _docStatus(d.error || 'Check failed.', 'error'); return; }
    _docData = d;
    _docSel = new Set(d.findings.filter(f => f.default).map(f => f.key));
    _docOpen = new Set(Object.keys(d.counts).filter(c => d.counts[c] <= 20));
    doctorRender();
    const s = d.summary;
    _docStatus(`${d.source}: ${s.error} error(s), ${s.warning} warning(s), ${s.info} info.`,
               s.error ? 'error' : (s.warning ? 'warn' : 'ok'));
  } catch (e) {
    _docStatus('Network error: ' + e.message, 'error');
  }
}

function doctorRender() {
  const el = document.getElementById('doc-list');
  if (!el || !_docData) return;
  const s = _docData.summary;
  const byCode = {};
  for (const f of _docData.findings) (byCode[f.code] = byCode[f.code] || []).push(f);
  // the summary counts kinds of problem, not places: 851 copies of one rule are one kind (3.9.5, stage D)
  const kinds = sev => Object.keys(byCode).filter(c => byCode[c][0].severity === sev).length;
  const places = n => t(n === 1 ? '{0} place' : '{0} places', n);
  const block = (sev, big, label, sub) =>
    `<button type="button" class="doc-block doc-${sev}" aria-pressed="${_docFilter === sev}" onclick="doctorFilter('${sev}')">` +
    `<b>${_esc(big)}</b><span>${_esc(label)}</span>${sub ? `<small>${_esc(sub)}</small>` : ''}</button>`;
  const wk = kinds('warning'), ik = kinds('info');
  document.getElementById('doc-summary').innerHTML =
    block('error', s.error, t(s.error === 1 ? 'error' : 'errors'), '') +
    block('warning', wk, t(wk === 1 ? 'kind of warning' : 'kinds of warning'), s.warning ? places(s.warning) : '') +
    block('info', ik, t(ik === 1 ? 'kind of info' : 'kinds of info'), s.info ? places(s.info) : '');
  const keep = c => _docFilter === 'attention' ? byCode[c][0].severity !== 'info' : byCode[c][0].severity === _docFilter;
  const codes = Object.keys(byCode).filter(keep);
  if (!codes.length && _docFilter !== 'attention') {
    el.innerHTML = '<div class="porter-placeholder">' + _esc(t('Nothing of this kind.')) + '</div>';
    _docSyncButton();
    return;
  }
  if (!codes.length) {
    el.innerHTML = '<div class="porter-placeholder"><svg class="ic" aria-hidden="true"><use href="/static/icons.svg#check"/></svg> No errors or warnings.' +
      (s.info ? ' Choose <b>Info</b> above to see the info findings.' : '') + '</div>';
    _docSyncButton();
    return;
  }
  el.innerHTML = codes.map(code => {
    const items = byCode[code];
    const fixable = items.filter(f => f.fixable);
    const ticked = fixable.filter(f => _docSel.has(f.key)).length;
    const sev = items[0].severity;
    const open = _docOpen.has(code);
    // the hint and its warning in two pieces, so each is translated on its own
    const hint = fixable.length ? fixable[0].hint : 'no automatic fix';
    const hintWarn = fixable.length && items[0].removing ? '— deletes functions' : '';
    const box = fixable.length
      ? `<input type="checkbox" class="doc-group" data-code="${code}" ${ticked === fixable.length ? 'checked' : ''}
           onclick="event.stopPropagation()" onchange="doctorTickGroup('${code}', this.checked)">`
      : '<span class="doc-nobox"></span>';
    const rows = open ? items.slice(0, _DOC_SHOW).map(f => `
        <label class="doc-row">
          ${f.fixable ? `<input type="checkbox" ${_docSel.has(f.key) ? 'checked' : ''} onchange="doctorTick(${JSON.stringify(f.key).replace(/"/g, '&quot;')}, this.checked)">` : '<span class="doc-nobox"></span>'}
          <span class="doc-loc">${_esc(f.location)}</span>
          <span class="doc-msg">${_esc(f.message)}</span>
        </label>`).join('') + (items.length > _DOC_SHOW
          ? `<div class="doc-more">… ${items.length - _DOC_SHOW} more — they follow the group tick box.</div>` : '')
      : '';
    return `<div class="doc-group-box doc-${sev}">
      <div class="doc-group-h" onclick="doctorToggle('${code}')">
        ${box}
        <span class="doc-code">${code}</span>
        <span class="doc-title">${_esc(_docData.titles[code] || '')}</span>
        <span class="doc-count">${places(items.length)}${fixable.length ? ` · ${ticked}/${fixable.length} ticked` : ''}</span>
        <span class="doc-hint"><span>${_esc(hint)}</span>${hintWarn ? `<span class="doc-hint-warn">${hintWarn}</span>` : ''}</span>
        <span class="doc-caret">${_esc(t(open ? 'Hide them' : 'Show them'))} ${open ? '▾' : '▸'}</span>
      </div>
      ${_DOC_PLAIN[code] ? `<div class="doc-plain">${_esc(t(_DOC_PLAIN[code]))}</div>` : ''}
      ${open && fixable.length ? _docOptBar(code) : ''}
      <div class="doc-rows">${rows}</div>
    </div>`;
  }).join('');
  el.querySelectorAll('.doc-group').forEach(cb => {
    const code = cb.dataset.code;
    const fx = byCode[code].filter(f => f.fixable);
    const n = fx.filter(f => _docSel.has(f.key)).length;
    cb.indeterminate = n > 0 && n < fx.length;
  });
  _docSyncButton();
}

function _docSyncButton() {
  const b = document.getElementById('doc-fix-btn');
  if (b) {
    b.disabled = _docSel.size === 0;
    b.textContent = _docSel.size ? `✓ Fix ${_docSel.size} selected in the show` : '✓ Fix selected in the show';
  }
  const x = document.getElementById('doc-export-btn');
  if (x) x.disabled = _docSel.size === 0;
  if (typeof setOutcome === 'function') {
    const by = {};
    for (const k of _docSel) { const c = String(k).split('|')[0]; by[c] = (by[c] || 0) + 1; }
    const codes = Object.keys(by).sort();
    setOutcome('doctor', codes.length ? codes.slice(0, 6).map(c => `${c} × ${by[c]}`)
      .concat(codes.length > 6 ? [t('+{0} more kinds', codes.length - 6)] : []) : 'nothing — tick the findings to fix',
      '', codes.length ? 'Apply will fix' : 'Apply will do');
  }
}

function doctorFilter(sev) {
  _docFilter = _docFilter === sev ? 'attention' : sev;
  doctorRender();
}

function doctorToggle(code) {
  if (_docOpen.has(code)) _docOpen.delete(code); else _docOpen.add(code);
  doctorRender();
}

function doctorTick(key, on) {
  if (on) _docSel.add(key); else _docSel.delete(key);
  doctorRender();
}

function doctorTickGroup(code, on) {
  for (const f of _docData.findings) {
    if (f.code === code && f.fixable) { if (on) _docSel.add(f.key); else _docSel.delete(f.key); }
  }
  doctorRender();
}

function doctorSelect(mode) {
  if (!_docData) return;
  _docSel = new Set(_docData.findings.filter(f =>
    f.fixable && (mode === 'all' || (mode === 'default' && f.default))).map(f => f.key));
  doctorRender();
}

async function doctorFix() {
  if (!_docSel.size) return;
  _docStatus('Fixing…', 'info');
  try {
    const r = await fetch('/api/doctor/fix', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys: [..._docSel], options: _docOptions() }),
    });
    if (!r.ok) { const d = await r.json(); _docStatus(d.error || 'Fix failed.', 'error'); return; }
    const name = r.headers.get('X-Suggested-Filename') || 'workspace_v2.qxw';
    const blob = await r.blob();
    const res = await (await fetch('/api/doctor/last-result')).json();
    const saved = await saveFileWithPicker(blob, name,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save fixed workspace');
    if (!saved) { _docStatus('Not saved.', 'info'); return; }
    const full = saveFileWithPicker.lastPath;
    let reportMsg = 'Fix report not saved (no folder known) — use Copy Report.';
    if (full) {
      try {
        const rr = await fetch('/api/doctor/save-report', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ qxw_path: full }),
        });
        const d = await rr.json();
        if (rr.ok) reportMsg = `Fix report: ${d.name}`;
      } catch (e) { /* keep the message */ }
    }
    const box = document.getElementById('doc-result');
    box.hidden = false;
    box.innerHTML = `<h3>Saved</h3>
      <p><b>${_esc(full || saved)}</b><br>${_esc(reportMsg)}</p>
      <p>${res.actions} fix(es) applied${res.skipped ? `, ${res.skipped} not fixed (see the report)` : ''}.
         Before: ${res.before.error} error(s), ${res.before.warning} warning(s) →
         after: <b>${res.after.error} error(s), ${res.after.warning} warning(s)</b>.</p>
      <p>This is a separate copy: the show in progress is unchanged (use ✓ Fix selected in the show to change it).</p>`;
    _docStatus(`Saved ${full || saved}. ${reportMsg}`, 'ok');
  } catch (e) {
    _docStatus('Error: ' + e.message, 'error');
  }
}

async function doctorCopyReport() {
  try {
    const d = await (await fetch('/api/doctor/last-result')).json();
    if (!d.report) { _docStatus('No fix report yet.', 'info'); return; }
    await navigator.clipboard.writeText(d.report);
    _docStatus('Fix report copied.', 'ok');
  } catch (e) {
    _docStatus('Could not copy: ' + e.message, 'error');
  }
}

function invalidateDoctor() {
  _docData = null;
  _docSel = new Set();
  _docRenderEmpty();
  const s = document.getElementById('doc-summary');
  if (s) s.innerHTML = '';
  _docSyncButton();
}
