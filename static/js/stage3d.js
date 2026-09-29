/**
 * Stage & Meshes tab (WORKPLAN Phase 2.5).
 *
 * Plan (top) and front views of the 3D stage with its fixtures and meshes.
 * Meshes are placed by what you see — centre from the left / back edge and
 * height of the lowest point above the floor — not by QLC+'s raw XPos/YPos
 * (which depend on how the model was drawn).  Drag a mesh in either view,
 * or type the numbers; ⤓ puts it on the floor.  All edits stay on a working
 * copy (↶ undo) until 💾 Save → new file.
 */

let _stS = null;          // /api/stage/state
let _stSel = null;        // selected mesh id
let _stLib = null;        // {dirs, items}
let _stDrag = null;
const ST_SNAP = 10;       // mm

function stageInit() { if (!_stS) _stLoad(); }

function invalidateStage() {
  _stS = null; _stSel = null;
  const b = document.getElementById('st-body');
  if (b) b.innerHTML = '<div class="porter-placeholder">Open a workspace to see its 3D stage.</div>';
  if (document.getElementById('scr-stage')?.classList.contains('active')) _stLoad();
}

async function _stLoad() {
  try {
    const r = await fetch('/api/stage/state');
    const d = await r.json();
    if (!r.ok) return;
    _stS = d;
    if (_stSel && !_stS.meshes.some(m => m.id === _stSel)) _stSel = null;
    _stRender();
  } catch (e) { /* no workspace */ }
}

async function _stOp(body, quiet) {
  const r = await fetch('/api/stage/op', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Failed.', 'error'); return null; }
  _stS = d;
  if (d.result && d.result.id && body.op !== 'remove') _stSel = d.result.id;
  if (body.op === 'remove') _stSel = null;
  _stRender();
  if (!quiet && d.message) setStatus(d.message + ' Not saved yet.', 'ok');
  return d;
}

function _stMesh(id) { return _stS && _stS.meshes.find(m => m.id === id); }
const _stMm = v => (v == null ? '—' : (v / 1000).toFixed(2) + ' m');

// ── layout ──────────────────────────────────────────────────────────────────
function _stRender() {
  const el = document.getElementById('st-body');
  if (!el || !_stS) return;
  const S = _stS.stage;
  el.innerHTML = `
  <div class="st-cols">
    <div class="st-views">
      <div class="st-vh">Plan — seen from above <span class="vce-hint">back at the top, audience at the bottom · drag a mesh to move it</span></div>
      <div id="st-plan" class="st-view"></div>
      <div class="st-vh">Front — seen from the audience <span class="vce-hint">drag a mesh sideways or up/down</span></div>
      <div id="st-front" class="st-view"></div>
      <div class="st-legend"><span class="st-k st-k-m"></span>mesh <span class="st-k st-k-s"></span>selected
        <span class="st-k st-k-f"></span>fixture <span class="st-k st-k-x"></span>model file not found</div>
    </div>
    <div class="st-side">
      <div class="lb-card">
        <h3>Stage <span class="p-desc">the floor and the space around the rig</span></h3>
        <div class="lb-row">
          <select id="st-type" class="filter-input">${_stS.types.map((t, i) =>
            `<option value="${i}" ${i === S.type ? 'selected' : ''}>${_esc(t)}</option>`).join('')}</select>
          <label>W <input id="st-w" type="number" step="0.5" min="1" class="filter-input rr-num" value="${S.w}"></label>
          <label>H <input id="st-h" type="number" step="0.5" min="1" class="filter-input rr-num" value="${S.h}"></label>
          <label>D <input id="st-d" type="number" step="0.5" min="1" class="filter-input rr-num" value="${S.d}"></label> m
          <button class="btn btn-surface btn-sm" onclick="stageSetStage()">Apply</button>
        </div>
        <div class="vce-hint">The floor is at ${S.floor ? S.floor * 1000 + ' mm (the Simple ground slab is centred on 0)' : '0'}; meshes keep their place when the stage changes.</div>
      </div>

      <div class="lb-card">
        <h3>Meshes <span class="p-desc">${_stS.meshes.length} on this stage</span></h3>
        <div class="st-list">${_stS.meshes.map(m => {
          const p = m.place;
          const off = p && p.bottom !== 0;
          return `<div class="st-item ${m.id === _stSel ? 'on' : ''}" onclick="stageSelect('${m.id}')">
            <span>${m.found ? '' : '⚠ '}${_esc(m.label)}</span>
            <span class="vce-hint">${p ? `${off ? `<b style="color:#f9e2af">${p.bottom > 0 ? 'floats ' + p.bottom : 'sinks ' + (-p.bottom)} mm</b>` : 'on the floor'}` : 'file not found'}</span></div>`;
        }).join('') || '<div class="vce-hint">No meshes yet — add one below.</div>'}</div>
        <div class="lb-row">
          <button class="btn btn-surface btn-sm" onclick="stageFloor(null)" title="Every mesh with its lowest point on the floor">⤓ Put all on the floor</button>
        </div>
      </div>

      <div class="lb-card" id="st-edit">${_stEditHtml()}</div>

      <div class="lb-card">
        <h3>Add a mesh <span class="p-desc">from your mesh folders</span></h3>
        <div id="st-lib">${_stLibHtml()}</div>
      </div>
    </div>
  </div>`;
  _stDraw();
  const u = document.getElementById('st-undo'); if (u) u.disabled = !_stS.undo;
  const g = document.getElementById('st-go'); if (g) g.disabled = !_stS.dirty;
  const s = document.getElementById('st-summary');
  if (s) s.innerHTML = `<span class="doc-chip">${_esc(S.type_name)} ${S.w}×${S.d} m</span>` +
    `<span class="doc-chip">${_stS.meshes.length} mesh(es)</span><span class="doc-chip">${_stS.fixtures.length} fixture(s)</span>` +
    (_stS.dirty ? '<span class="doc-chip doc-warning">unsaved changes</span>' : '');
}

function _stEditHtml() {
  const m = _stMesh(_stSel);
  if (!m) return `<h3>Selected mesh</h3><div class="vce-hint">Click a mesh in a view or in the list.</div>`;
  const p = m.place || {};
  const sc = m.scale.map(v => Math.round(v * 1000) / 10);
  return `<h3>${_esc(m.label)} <span class="p-desc">mesh ${m.id}</span></h3>
    ${m.found ? '' : `<div class="porter-warn">⚠ Model file not found here: ${_esc(m.res)}. Relink it below to place it.</div>`}
    <div class="st-grid">
      <label>Centre X <input id="st-x" type="number" step="10" class="filter-input rr-num" value="${p.x ?? ''}" ${m.found ? '' : 'disabled'}> mm</label>
      <span class="vce-hint">from the left edge</span>
      <label>Centre Z <input id="st-z" type="number" step="10" class="filter-input rr-num" value="${p.z ?? ''}" ${m.found ? '' : 'disabled'}> mm</label>
      <span class="vce-hint">from the back edge</span>
      <label>Bottom <input id="st-b" type="number" step="10" class="filter-input rr-num" value="${p.bottom ?? ''}" ${m.found ? '' : 'disabled'}> mm</label>
      <span class="vce-hint">above the floor · 0 = standing on it</span>
    </div>
    <div class="lb-row">
      <button class="btn btn-surface btn-sm" onclick="stageMove()" ${m.found ? '' : 'disabled'}>Move</button>
      <button class="btn btn-surface btn-sm" onclick="stageFloor(['${m.id}'])" ${m.found ? '' : 'disabled'}>⤓ On the floor</button>
      <span class="vce-hint">size ${p.w ?? '?'} × ${p.h ?? '?'} × ${p.d ?? '?'} mm (W×H×D as placed)</span>
    </div>
    <div class="lb-row"><span style="width:62px">Rotation</span>
      <label>X <input id="st-rx" type="number" step="5" class="filter-input st-n" value="${m.rot[0]}"></label>
      <label>Y <input id="st-ry" type="number" step="5" class="filter-input st-n" value="${m.rot[1]}"></label>
      <label>Z <input id="st-rz" type="number" step="5" class="filter-input st-n" value="${m.rot[2]}"></label> °</div>
    <div class="lb-row"><span style="width:62px">Scale</span>
      <label>X <input id="st-sx" type="number" step="5" min="1" class="filter-input st-n" value="${sc[0]}" oninput="_stLockScale(this)"></label>
      <label>Y <input id="st-sy" type="number" step="5" min="1" class="filter-input st-n" value="${sc[1]}" oninput="_stLockScale(this)"></label>
      <label>Z <input id="st-sz" type="number" step="5" min="1" class="filter-input st-n" value="${sc[2]}" oninput="_stLockScale(this)"></label> %</div>
    <div class="lb-row">
      <label class="vce-hint"><input type="checkbox" id="st-lock" ${sc[0] === sc[1] && sc[1] === sc[2] ? 'checked' : ''}> same scale on X/Y/Z</label>
      <label class="vce-hint"><input type="checkbox" id="st-keep" checked> keep it on its spot and height</label>
    </div>
    <div class="lb-row">
      <label>Name <input id="st-name" class="filter-input" style="width:150px" value="${_esc(m.name)}" placeholder="${_esc(m.label)}"></label>
      <button class="btn btn-surface btn-sm" onclick="stageTransform()">Apply</button>
    </div>
    <details class="vce-sub"><summary>Model file, duplicate, remove, QLC+ values</summary>
      <div class="lb-row"><input id="st-res" class="filter-input" style="flex:1;min-width:0" value="${_esc(m.res)}">
        <button class="btn btn-surface btn-sm" onclick="stageRelink()">Relink</button></div>
      <div class="vce-hint" style="margin-bottom:6px">${m.file ? 'found: ' + _esc(m.file) : m.builtin ? 'QLC+ built-in model' : 'not found on this computer'}</div>
      <div class="lb-row">
        <button class="btn btn-surface btn-sm" onclick="_stOp({op:'duplicate',id:'${m.id}'})">⧉ Duplicate</button>
        <button class="btn btn-surface btn-sm" onclick="_stOp({op:'remove',id:'${m.id}'})">🗑 Remove</button>
      </div>
      <div class="vce-hint">In the file (QLC+ 3D view): X ${m.pos[0]} · Y ${m.pos[1]} · Z ${m.pos[2]} mm${m.size ? ` · model ${m.size.join(' × ')} mm` : ''}</div>
    </details>`;
}

function _stLockScale(inp) {
  if (!document.getElementById('st-lock')?.checked) return;
  ['st-sx', 'st-sy', 'st-sz'].forEach(id => { const e = document.getElementById(id); if (e !== inp) e.value = inp.value; });
}

function _stLibHtml() {
  if (!_stLib) { _stLoadLib(); return '<div class="vce-hint">Loading…</div>'; }
  const q = (document.getElementById('st-lq')?.value || '').toLowerCase();
  const items = _stLib.items.filter(i => !q || (i.folder + '/' + i.name).toLowerCase().includes(q));
  return `
    <div class="vce-hint" style="margin-bottom:4px">Folders with .obj models (one per line):</div>
    <textarea id="st-dirs" class="filter-input" rows="2" style="width:100%">${_esc(_stLib.dirs.join('\n'))}</textarea>
    <div class="lb-row"><button class="btn btn-surface btn-sm" onclick="stageSaveDirs()">Save folders</button>
      <input id="st-lq" class="filter-input" style="flex:1;min-width:0" placeholder="search models" value="${_esc(q)}" oninput="stageLibFilter()"></div>
    <div class="st-lib">${items.slice(0, 200).map(i => `
      <div class="st-item"><span>${_esc(i.name)} <span class="vce-hint">${_esc(i.folder)}</span></span>
        <button class="btn btn-surface btn-sm" onclick="stageAdd('${_esc(i.path).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')">＋ Add</button></div>`).join('')
      || '<div class="vce-hint">No models found — add a folder above.</div>'}</div>
    <div class="lb-row"><input id="st-addpath" class="filter-input" style="flex:1;min-width:0" placeholder="…or the full path of an .obj file">
      <button class="btn btn-surface btn-sm" onclick="stageAdd(document.getElementById('st-addpath').value)">＋ Add</button></div>
    <div class="vce-hint">New meshes go to the centre of the stage, standing on the floor.</div>`;
}

async function _stLoadLib() {
  const r = await fetch('/api/stage/library');
  _stLib = await r.json();
  const el = document.getElementById('st-lib'); if (el) el.innerHTML = _stLibHtml();
}

function stageLibFilter() {
  const el = document.getElementById('st-lib'); if (!el) return;
  const pos = document.getElementById('st-lq').selectionStart;
  el.innerHTML = _stLibHtml();
  const q = document.getElementById('st-lq'); q.focus(); q.setSelectionRange(pos, pos);
}

async function stageSaveDirs() {
  const dirs = document.getElementById('st-dirs').value.split('\n').map(s => s.trim()).filter(Boolean);
  const r = await fetch('/api/stage/library-dirs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dirs }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _stLib = d; document.getElementById('st-lib').innerHTML = _stLibHtml();
  setStatus(`${d.items.length} model(s) found.`, 'ok');
  _stLoad();
}

// ── actions ─────────────────────────────────────────────────────────────────
function stageSelect(id) { _stSel = id; _stRender(); }
function _stVal(id) { const e = document.getElementById(id); return e ? e.value : ''; }

function stageMove() {
  _stOp({ op: 'move', id: _stSel, x: _stVal('st-x'), z: _stVal('st-z'), bottom: _stVal('st-b') });
}
function stageFloor(ids) { _stOp({ op: 'floor', ids }); }
function stageTransform() {
  _stOp({ op: 'transform', id: _stSel, name: _stVal('st-name'),
          rot: [+_stVal('st-rx'), +_stVal('st-ry'), +_stVal('st-rz')],
          scale: [+_stVal('st-sx') / 100, +_stVal('st-sy') / 100, +_stVal('st-sz') / 100],
          keep_floor: document.getElementById('st-keep').checked });
}
function stageRelink() { _stOp({ op: 'transform', id: _stSel, res: _stVal('st-res') }); }
function stageAdd(path) { if ((path || '').trim()) _stOp({ op: 'add', res: path.trim() }); }
function stageSetStage() {
  _stOp({ op: 'stage', type: _stVal('st-type'), w: _stVal('st-w'), h: _stVal('st-h'), d: _stVal('st-d'), keep_meshes: true });
}
function stageUndo() { _stOp({ op: 'undo' }); }
function stageReset() { if (confirm('Discard all stage changes?')) _stOp({ op: 'reset' }); }

// ── the two views (SVG) ─────────────────────────────────────────────────────
function _stDraw() {
  const S = _stS.stage, W = S.w * 1000, D = S.d * 1000, H = Math.max(S.h * 1000, 2000);
  const pad = 20;
  const box = document.getElementById('st-plan');
  const vw = Math.max(300, box.clientWidth || 600);
  const k = Math.min((vw - 2 * pad) / W, 420 / D);
  const ph = D * k + 2 * pad, fh = H * k + 2 * pad;
  const fx = _stS.fixtures;
  const ms = _stS.meshes.filter(m => m.place);
  const cls = m => 'st-m' + (m.id === _stSel ? ' sel' : '');
  // plan
  box.innerHTML = `<svg width="${W * k + 2 * pad}" height="${ph}" data-k="${k}">
    <rect x="${pad}" y="${pad}" width="${W * k}" height="${D * k}" class="st-floor"/>
    <text x="${pad + W * k / 2}" y="${pad - 6}" class="st-t" text-anchor="middle">back</text>
    <text x="${pad + W * k / 2}" y="${ph - 4}" class="st-t" text-anchor="middle">front · audience</text>
    ${fx.map(f => `<circle cx="${pad + (f.x + 150) * k}" cy="${pad + (f.z + 150) * k}" r="4" class="st-f"><title>${_esc(f.name)}</title></circle>`).join('')}
    ${ms.map(m => `<g class="${cls(m)}" data-id="${m.id}" onmousedown="_stDown(event,'plan','${m.id}')">
      <rect x="${pad + m.place.x0 * k}" y="${pad + m.place.z0 * k}" width="${Math.max(3, m.place.w * k)}" height="${Math.max(3, m.place.d * k)}"/>
      <text x="${pad + m.place.x * k}" y="${pad + m.place.z * k + 4}" text-anchor="middle">${_esc(m.label.slice(0, 16))}</text></g>`).join('')}
  </svg>`;
  // front
  const fbox = document.getElementById('st-front');
  const floorY = fh - pad;
  fbox.innerHTML = `<svg width="${W * k + 2 * pad}" height="${fh}">
    <line x1="0" x2="${W * k + 2 * pad}" y1="${floorY}" y2="${floorY}" class="st-fl"/>
    <rect x="${pad}" y="${floorY - S.h * 1000 * k}" width="${W * k}" height="${S.h * 1000 * k}" class="st-space"/>
    <text x="${pad + 4}" y="${floorY - 4}" class="st-t">floor</text>
    ${fx.map(f => `<circle cx="${pad + (f.x + 150) * k}" cy="${floorY - (f.y + 150) * k}" r="4" class="st-f"><title>${_esc(f.name)}</title></circle>`).join('')}
    ${ms.map(m => `<g class="${cls(m)}" onmousedown="_stDown(event,'front','${m.id}')">
      <rect x="${pad + m.place.x0 * k}" y="${floorY - m.place.top * k}" width="${Math.max(3, m.place.w * k)}" height="${Math.max(3, m.place.h * k)}"/>
      <text x="${pad + m.place.x * k}" y="${floorY - m.place.top * k - 3}" text-anchor="middle">${_esc(m.label.slice(0, 16))}</text></g>`).join('')}
  </svg>`;
  _stS._k = k;
  const miss = _stS.meshes.filter(m => !m.place).length;
  if (miss) box.insertAdjacentHTML('beforeend', `<div class="vce-hint">${miss} mesh(es) not drawn — their model file is not found here.</div>`);
}

function _stDown(e, view, id) {
  e.preventDefault();
  _stSel = id;
  const m = _stMesh(id);
  _stDrag = { view, id, sx: e.clientX, sy: e.clientY, p: { ...m.place }, g: e.currentTarget, moved: false };
  document.addEventListener('mousemove', _stMoveEv);
  document.addEventListener('mouseup', _stUpEv, { once: true });
}

function _stMoveEv(e) {
  const d = _stDrag; if (!d) return;
  const dx = (e.clientX - d.sx), dy = (e.clientY - d.sy);
  if (Math.hypot(dx, dy) > 3) d.moved = true;
  d.g.setAttribute('transform', `translate(${dx},${dy})`);
  const k = _stS._k;
  const snap = v => Math.round(v / ST_SNAP) * ST_SNAP;
  d.nx = snap(d.p.x + dx / k);
  if (d.view === 'plan') d.nz = snap(d.p.z + dy / k); else d.nb = snap(d.p.bottom - dy / k);
  setStatus(d.view === 'plan' ? `x ${d.nx} · z ${d.nz} mm` : `x ${d.nx} mm · bottom ${d.nb} mm above the floor`, 'info');
}

function _stUpEv() {
  document.removeEventListener('mousemove', _stMoveEv);
  const d = _stDrag; _stDrag = null;
  if (!d) return;
  if (!d.moved) { _stRender(); return; }
  _stOp(d.view === 'plan' ? { op: 'move', id: d.id, x: d.nx, z: d.nz }
                          : { op: 'move', id: d.id, x: d.nx, bottom: d.nb });
}

async function stageSave() {
  setStatus('Saving…', 'info');
  try {
    const r = await fetch('/api/stage/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    if (!r.ok) {
      const d = await r.json();
      setStatus((d.error || 'Failed.') + (d.findings ? ' ' + d.findings.slice(0, 3).join(' | ') : ''), 'error');
      return;
    }
    const name = r.headers.get('X-Suggested-Filename') || 'workspace_v2.qxw';
    const blob = await r.blob();
    const saved = await saveFileWithPicker(blob, name,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save workspace with the stage changes');
    if (!saved) { setStatus('Not saved.', 'info'); return; }
    const full = saveFileWithPicker.lastPath;
    let msg = `Saved ${full || saved}.`;
    if (full) {
      const rr = await fetch('/api/stage/save-report', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qxw_path: full }) });
      const d = await rr.json();
      msg += rr.ok ? ` Report: ${d.name}.` : ' Report not saved.';
    }
    setStatus(msg + ' The open workspace is unchanged — open the new file to continue.', 'ok');
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
  }
}
