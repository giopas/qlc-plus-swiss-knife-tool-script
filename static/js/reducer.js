/**
 * Rig Reducer tab (WORKPLAN Phase 2.2).
 *
 * Lists the fixtures of the open workspace: untick the ones to remove, edit
 * name / universe / address of the kept ones (re-patch).  🔍 Preview shows
 * what will be removed (values, groups, functions, VC widgets) and what the
 * Doctor says; 💾 Reduce writes a NEW workspace (Save dialog) and the report
 * next to it.  The open workspace is never changed.
 */

let _rrFx = null;             // [{id, name, manufacturer, model, mode, universe, address, channels}]
let _rrKeep = new Set();
let _rrEdit = {};             // id → {name, universe, address} (only changed fields)

function reducerInit() {
  if (!_rrFx) _rrLoad();
}

function invalidateReducer() {
  _rrFx = null; _rrKeep = new Set(); _rrEdit = {};
  const t = document.getElementById('rr-table');
  if (t) t.innerHTML = '<div class="porter-placeholder">Open a workspace to list its fixtures.</div>';
  const p = document.getElementById('rr-preview');
  if (p) p.innerHTML = '<div class="porter-placeholder">Untick the fixtures the venue doesn\'t have: what Apply will do shows here.</div>';
  _rrSync();
  if (document.getElementById('scr-reducer')?.classList.contains('active')) _rrLoad();
}

async function _rrLoad() {
  try {
    const r = await fetch('/api/reducer/fixtures');
    const d = await r.json();
    if (!r.ok) return;
    _rrFx = d.fixtures;
    _rrKeep = new Set(_rrFx.map(f => f.id));
    _rrEdit = {};
    _rrRender();
  } catch (e) { /* no workspace */ }
}

function _rrRender() {
  const el = document.getElementById('rr-table');
  if (!el || !_rrFx) return;
  el.innerHTML = `<table class="sb-table rr-tbl"><thead><tr>
      <th>Keep</th><th>ID</th><th>Name</th><th>Fixture</th><th>Mode</th><th>Universe</th><th>Address</th><th>Ch</th>
    </tr></thead><tbody>${_rrFx.map(f => {
      const e = _rrEdit[f.id] || {};
      const k = _rrKeep.has(f.id);
      return `<tr class="${k ? '' : 'rr-gone'}">
        <td><input type="checkbox" ${k ? 'checked' : ''} onchange="reducerKeep('${f.id}', this.checked)"></td>
        <td>${_esc(f.id)}</td>
        <td><input class="filter-input rr-in" value="${_esc(e.name ?? f.name)}" ${k ? '' : 'disabled'}
                   onchange="reducerEdit('${f.id}', 'name', this.value)"></td>
        <td>${_esc(f.manufacturer)} ${_esc(f.model)}</td>
        <td>${_esc(f.mode)}</td>
        <td><input type="number" min="1" class="filter-input rr-num" value="${e.universe ?? f.universe}" ${k ? '' : 'disabled'}
                   onchange="reducerEdit('${f.id}', 'universe', this.value)"></td>
        <td><input type="number" min="1" max="512" class="filter-input rr-num" value="${e.address ?? f.address}" ${k ? '' : 'disabled'}
                   onchange="reducerEdit('${f.id}', 'address', this.value)"></td>
        <td>${f.channels}</td>
      </tr>`;
    }).join('')}</tbody></table>`;
  _rrSync();
}

function _rrSync() {
  const s = document.getElementById('rr-summary');
  const b = document.getElementById('rr-go');
  if (!_rrFx) {
    if (s) s.innerHTML = ''; if (b) b.disabled = true;
    const x = document.getElementById('rr-export'); if (x) x.disabled = true;
    setOutcome('reducer', '');
    return;
  }
  const gone = _rrFx.length - _rrKeep.size;
  if (s) s.innerHTML = `<span class="doc-chip">${_rrKeep.size} kept</span>` +
    `<span class="doc-chip doc-warning">${gone} removed</span>` +
    (() => {
      const ed = Object.entries(_rrEdit).filter(([id]) => _rrKeep.has(id)).map(([, e]) => e);
      const ren = ed.filter(e => 'name' in e).length;
      const pat = ed.filter(e => 'universe' in e || 'address' in e).length;
      return (ren ? `<span class="doc-chip">${ren} renamed</span>` : '') +
             (pat ? `<span class="doc-chip">${pat} re-patched</span>` : '');
    })();
  if (b) b.disabled = !_rrKeep.size || (!gone && !Object.keys(_rrEdit).length);
  const x = document.getElementById('rr-export'); if (x) x.disabled = b ? b.disabled : true;
  _rrAutoPreview();
}

function reducerKeep(id, on) {
  if (on) _rrKeep.add(id); else _rrKeep.delete(id);
  _rrRender();
}

function reducerKeepAll(on) {
  if (!_rrFx) return;
  _rrKeep = new Set(on ? _rrFx.map(f => f.id) : []);
  _rrRender();
}

function reducerEdit(id, field, value) {
  const f = _rrFx.find(x => x.id === id);
  const e = _rrEdit[id] || {};
  const v = field === 'name' ? value : parseInt(value, 10);
  if (String(v) === String(f[field])) delete e[field]; else e[field] = v;
  if (Object.keys(e).length) _rrEdit[id] = e; else delete _rrEdit[id];
  _rrSync();
}

function _rrPlan() {
  const repatch = {};
  for (const [id, e] of Object.entries(_rrEdit)) if (_rrKeep.has(id)) repatch[id] = e;
  return { keep: [..._rrKeep], repatch };
}

let _rrPreviewTimer = null;
let _rrPreviewSeq = 0;

/** What Apply will do, computed as you tick (v2.2: no Preview click needed). */
function _rrAutoPreview() {
  clearTimeout(_rrPreviewTimer);
  if (!_rrFx) return;
  const gone = _rrFx.length - _rrKeep.size, edits = Object.keys(_rrEdit).length;
  if (!gone && !edits) {
    const el = document.getElementById('rr-preview');
    if (el) el.innerHTML = '<div class="porter-placeholder">Untick the fixtures the venue doesn\'t have (or rename / re-patch the ones you keep): what Apply will do shows here.</div>';
    setOutcome('reducer', 'nothing yet — untick the fixtures to remove', '', 'Apply will do');
    return;
  }
  if (!_rrKeep.size) { setOutcome('reducer', 'keep at least one fixture', 'warn', ''); return; }
  setOutcome('reducer', 'working it out…', '', 'Apply will');
  _rrPreviewTimer = setTimeout(() => reducerPreview(true), 350);
}

const _RR_GROUPS = [
  ['Fixtures removed', l => /^fixture \d+ '/.test(l)],
  ['Renamed / re-patched', l => /^fixture \d+:/.test(l)],
  ['Fixture groups', l => l.startsWith('fixture group')],
  ['Functions removed', l => l.startsWith('function')],
  ['VC widgets removed', l => l.startsWith('VC ')],
  ['Other', () => true],
];

async function reducerPreview(auto) {
  if (!_rrFx) { setStatus('Open a workspace first.', 'warn'); return; }
  const el = document.getElementById('rr-preview');
  const seq = ++_rrPreviewSeq;
  if (!auto) setStatus('Preview…', 'info');
  try {
    const r = await fetch('/api/reducer/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_rrPlan()),
    });
    const d = await r.json();
    if (seq !== _rrPreviewSeq) return;            // a newer tick is on its way
    if (!r.ok) { setStatus(d.error || 'Preview failed.', 'error'); setOutcome('reducer', d.error || 'no preview', 'error', ''); return; }
    const c = d.removed, doc = d.doctor;
    const groups = _RR_GROUPS.map(([t]) => [t, []]);
    for (const l of d.log) groups[_RR_GROUPS.findIndex(([, f]) => f(l))][1].push(l);
    const newBad = doc.new_errors.length, newWarn = doc.new_warnings.length;
    el.innerHTML = `<h3 class="rr-h">What Apply will do</h3>
      <div class="rr-sub">updated as you tick · ${c.values} scene value set(s) go with the fixtures</div>
      ${d.blocked ? '<div class="rr-block">⛔ The result has new Doctor errors — Apply is refused until they are gone.</div>' : ''}
      ${groups.filter(([, ls]) => ls.length).map(([t, ls], i) => `
        <details class="rr-grp"${i === 0 ? ' open' : ''}><summary><span>${t}</span><b>${ls.length}</b></summary>
          <ul>${ls.map(x => `<li>${_esc(x)}</li>`).join('')}</ul></details>`).join('')}
      ${d.more ? `<div class="rr-sub">… ${d.more} more lines in the report</div>` : ''}
      <details class="rr-grp"${newBad || newWarn ? ' open' : ''}><summary><span>Doctor on the result</span>
        <b class="${newBad ? 'rr-bad' : newWarn ? 'rr-warn' : 'rr-ok'}">${newBad || newWarn ? `${newBad} new error(s), ${newWarn} new warning(s)` : 'nothing new'}</b></summary>
        <ul>${[...doc.new_errors, ...doc.new_warnings].slice(0, 40).map(x => `<li>${_esc(x)}</li>`).join('') ||
          `<li>${doc.total_errors} error(s), ${doc.total_warnings} warning(s) in all — none of them caused by this step</li>`}</ul></details>`;
    const ren = Object.values(_rrEdit).length;
    const chips = [];
    if (c.fixtures) chips.push(`−${c.fixtures} fixture${c.fixtures > 1 ? 's' : ''}`);
    if (c.groups) chips.push(`−${c.groups} group${c.groups > 1 ? 's' : ''}`);
    if (c.functions) chips.push(`−${c.functions} function${c.functions > 1 ? 's' : ''}`);
    if (c.widgets) chips.push(`−${c.widgets} VC widget${c.widgets > 1 ? 's' : ''}`);
    if (ren) chips.push(`${ren} renamed / re-patched`);
    chips.push(newBad ? { text: `⛔ ${newBad} new Doctor error(s)`, kind: 'error' }
      : { text: '✓ no new Doctor errors', kind: 'ok' });
    setOutcome('reducer', chips, newBad ? 'error' : '');
    if (!auto) setStatus('Preview ready.', 'ok');
  } catch (e) {
    setStatus('Network error: ' + e.message, 'error');
  }
}

async function reducerRun() {
  setStatus('Reducing…', 'info');
  try {
    const r = await fetch('/api/reducer/reduce', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_rrPlan()),
    });
    if (!r.ok) {
      const d = await r.json();
      setStatus((d.error || 'Failed.') + (d.findings ? ' ' + d.findings.slice(0, 3).join(' | ') : ''), 'error');
      return;
    }
    const name = r.headers.get('X-Suggested-Filename') || 'workspace_v2.qxw';
    const blob = await r.blob();
    const saved = await saveFileWithPicker(blob, name,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save reduced workspace');
    if (!saved) { setStatus('Not saved.', 'info'); return; }
    const full = saveFileWithPicker.lastPath;
    let msg = `Saved ${full || saved}.`;
    if (full) {
      const rr = await fetch('/api/reducer/save-report', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ qxw_path: full }),
      });
      const d = await rr.json();
      msg += rr.ok ? ` Report: ${d.name}.` : ' Report not saved.';
    }
    setStatus(msg + ' A separate copy — the show in progress is unchanged.', 'ok');
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
  }
}
