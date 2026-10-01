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
  if (p) p.innerHTML = '<div class="porter-placeholder">Untick the fixtures to remove, edit names / addresses if needed, then 🔍 Preview.</div>';
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

async function reducerPreview() {
  if (!_rrFx) { setStatus('Open a workspace first.', 'warn'); return; }
  const el = document.getElementById('rr-preview');
  setStatus('Preview…', 'info');
  try {
    const r = await fetch('/api/reducer/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_rrPlan()),
    });
    const d = await r.json();
    if (!r.ok) { setStatus(d.error || 'Preview failed.', 'error'); return; }
    const c = d.removed, doc = d.doctor;
    el.innerHTML = `<h3>What will change</h3>
      <p><b>${c.fixtures}</b> fixture(s), <b>${c.groups}</b> fixture group(s), <b>${c.functions}</b> function(s),
         <b>${c.widgets}</b> VC widget(s) and <b>${c.values}</b> scene value set(s) removed.</p>
      <p>Doctor on the result: ${doc.total_errors} error(s), ${doc.total_warnings} warning(s)
         ${doc.new_errors.length || doc.new_warnings.length ? `— <b>new</b>: ${doc.new_errors.length} error(s), ${doc.new_warnings.length} warning(s)` : '— nothing new'}.</p>
      ${d.blocked ? '<p class="porter-warn">⛔ The result has new Doctor errors — it will not be exported.</p>' : ''}
      ${[...doc.new_errors, ...doc.new_warnings].slice(0, 20).map(x => `<div class="porter-warn">⚠ ${_esc(x)}</div>`).join('')}
      <details open><summary>Changes (${d.log.length + d.more})</summary>
        <div class="rr-log">${d.log.map(x => `<div>${_esc(x)}</div>`).join('')}${d.more ? `<div>… ${d.more} more in the report</div>` : ''}</div>
      </details>`;
    setStatus('Preview ready.', 'ok');
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
