/**
 * Workspace Doctor tab (WORKPLAN Phase 2.1).
 *
 * 🔍 Check runs the Doctor on the open workspace; findings are grouped by
 * code, fixable ones get a tick box (recommended fixes ticked; removals of
 * functions — D004 / D015 / D016 — are offered but not ticked).
 * 💾 Fix selected writes a NEW workspace (Save dialog, default
 * <name>_v<N+1>.qxw) and the fix report next to it.  The open workspace
 * and its file are never changed.
 */

let _docData = null;          // last /api/doctor/check result
let _docSel = new Set();      // ticked finding keys
let _docOpen = new Set();     // expanded codes
const _DOC_SHOW = 150;        // rows shown per code (the rest follow the group tick)

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
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace and press 🔍 Check.</div>';
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
  const showInfo = document.getElementById('doc-show-info')?.checked;
  const s = _docData.summary;
  document.getElementById('doc-summary').innerHTML =
    `<span class="doc-chip doc-error">${s.error} error(s)</span>` +
    `<span class="doc-chip doc-warning">${s.warning} warning(s)</span>` +
    `<span class="doc-chip doc-info">${s.info} info</span>`;
  const byCode = {};
  for (const f of _docData.findings) (byCode[f.code] = byCode[f.code] || []).push(f);
  const codes = Object.keys(byCode).filter(c => showInfo || byCode[c][0].severity !== 'info');
  if (!codes.length) {
    el.innerHTML = '<div class="porter-placeholder">✅ No errors or warnings.' +
      (s.info ? ' Tick <b>Show info</b> to see the info findings.' : '') + '</div>';
    _docSyncButton();
    return;
  }
  el.innerHTML = codes.map(code => {
    const items = byCode[code];
    const fixable = items.filter(f => f.fixable);
    const ticked = fixable.filter(f => _docSel.has(f.key)).length;
    const sev = items[0].severity;
    const open = _docOpen.has(code);
    const hint = fixable.length ? (fixable[0].hint + (items[0].removing ? ' — deletes functions' : '')) : 'no automatic fix';
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
        <span class="doc-count">${items.length}${fixable.length ? ` · ${ticked}/${fixable.length} ticked` : ''}</span>
        <span class="doc-hint">${_esc(hint)}</span>
        <span class="doc-caret">${open ? '▾' : '▸'}</span>
      </div>
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
      .concat(codes.length > 6 ? [`+${codes.length - 6} more kinds`] : []) : 'nothing — tick the findings to fix',
      '', codes.length ? 'Apply will fix' : 'Apply will do');
  }
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
      body: JSON.stringify({ keys: [..._docSel] }),
    });
    if (!r.ok) { const d = await r.json(); _docStatus(d.error || 'Fix failed.', 'error'); return; }
    const name = r.headers.get('X-Suggested-Filename') || 'workspace_v2.qxw';
    const blob = await r.blob();
    const res = await (await fetch('/api/doctor/last-result')).json();
    const saved = await saveFileWithPicker(blob, name,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save fixed workspace');
    if (!saved) { _docStatus('Not saved.', 'info'); return; }
    const full = saveFileWithPicker.lastPath;
    let reportMsg = 'Fix report not saved (no folder known) — use 📋 Copy Report.';
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
