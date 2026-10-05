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
let _stSel = null;        // selected mesh id (the last one clicked)
let _stSet = new Set();   // all selected mesh ids
let _stLib = null;        // {dirs, items}
let _stDrag = null;
const ST_SNAP = 10;       // mm

function stageInit() { if (!_stS) _stLoad(); }

function invalidateStage() {
  _stS = null; _stSel = null; _stSet = new Set();
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
    _stKeepSel();
    _stRender();
  } catch (e) { /* no workspace */ }
}

async function _stOp(body, quiet) {
  const r = await fetch('/api/stage/op', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Failed.', 'error'); return null; }
  _stS = d;
  if (d.result && d.result.id && body.op !== 'remove' && !String(body.op).startsWith('group_')) { _stSel = d.result.id; _stSet = new Set([_stSel]); }
  _stKeepSel();
  _stRender();
  if (!quiet && d.message) setStatus(d.message + ' Not saved yet.', 'ok');
  return d;
}

function _stKeepSel() {
  const ids = new Set([...(_stS?.meshes || []).map(m => m.id), ...(_stS?.fixtures || []).map(f => f.key)]);
  _stSet = new Set([..._stSet].filter(i => ids.has(i)));
  if (_stSel && !ids.has(_stSel)) _stSel = null;
  if (_stSel && !_stSet.size) _stSet.add(_stSel);
  if (!_stSet.has(_stSel)) _stSel = _stSet.size ? [..._stSet].pop() : null;
}

function _stMesh(id) { return _stS && _stS.meshes.find(m => m.id === id); }
function _stFx(key) { return _stS && _stS.fixtures.find(f => f.key === key); }
/** A mesh (id) or a fixture ("f:<id>") as {place, label, fixture}. */
function _stItem(id) {
  const f = _stFx(id);
  if (f) return { place: f.place, label: f.name, fixture: true };
  const m = _stMesh(id);
  return m ? { place: m.place, label: m.label, fixture: false } : null;
}
function _stKinds() {
  const ids = [..._stSet];
  return { fx: ids.filter(i => i.startsWith('f:')).length, ms: ids.filter(i => !i.startsWith('f:')).length };
}
const _stMm = v => (v == null ? '—' : (v / 1000).toFixed(2) + ' m');

// Inspector tabs (2.6): Selection · Place · Add · Stage — one at a time
let _stTab = 'select';
function stageTab(t) {
  _stTab = t;
  document.querySelectorAll('#st-body [data-sttab]').forEach(b => b.classList.toggle('active', b.dataset.sttab === t));
  document.querySelectorAll('#st-body [data-stpane]').forEach(p => { p.hidden = p.dataset.stpane !== t; });
}

// ── Fixture groups (2.8: the Pub test needs groups the show doesn't have) ──
// A group is one row of fixtures, left → right as seen from the audience.
// RGB matrices, the Look Builder and the VC use groups.
let _stGrpEdit = null;            // id of the group in the form, or null (= new)
let _stGrpPick = new Set();       // fixture ids ticked in the form
let _stGrpFlash = '';             // name of the group just made / saved: shown and scrolled to

function _stGroupsHtml() {
  const G = _stS.groups || [], F = _stS.all_fixtures || [];
  const nm = Object.fromEntries(F.map(f => [f.id, f.name]));
  const editing = G.find(g => g.id === _stGrpEdit);
  const list = G.length ? G.map(g => `<div class="st-item ${g.id === _stGrpEdit || g.name === _stGrpFlash ? 'on' : ''}"${g.name === _stGrpFlash ? ' data-grpflash="1"' : ''}>
      <span><b>${_esc(g.name)}</b> <span class="vce-hint">${g.fixtures.length} · ${_esc(g.fixtures.map(i => nm[i] || i).join(', '))}</span>
        ${g.used_by.length ? `<span class="vce-hint" title="${_esc(g.used_by.join(', '))}"> · ${g.used_by.length} matrix(es)</span>` : ''}</span>
      <span class="st-grp-acts"><button class="btn btn-surface btn-xs" onclick="stageGroupShow('${g.id}')" title="Select its fixtures in the views">Show</button>
        <button class="btn btn-surface btn-xs" onclick="stageGroupEdit('${g.id}')">Edit</button></span></div>`).join('')
    : '<div class="vce-hint">No fixture groups in this show yet.</div>';
  const picks = F.map(f => `<label class="st-grp-fx"><input type="checkbox" ${_stGrpPick.has(f.id) ? 'checked' : ''}
      onchange="stageGroupPick('${f.id}', this.checked)"> ${_esc(f.name)}</label>`).join('');
  return `<h3>Fixture groups <span class="p-desc">used by RGB matrices, the Look Builder and the VC</span></h3>
    <div class="st-list st-grp-list">${list}</div>
    <h3 style="margin-top:10px">${editing ? `Edit '${_esc(editing.name)}'` : 'New group'}</h3>
    <div class="lb-row"><label>Name <input id="st-grp-name" class="filter-input" style="width:200px" value="${_esc(editing ? editing.name : '')}" placeholder="e.g. Singer Pair"></label>
      <button class="btn btn-surface btn-sm" onclick="stageGroupFromSel()" title="Tick the fixtures selected in the views (click / Shift-click them)">⬚ From the selection</button>
      <button class="btn btn-surface btn-sm" onclick="stageGroupPickAll(false)">None</button></div>
    <div class="st-grp-picks">${picks || '<span class="vce-hint">No fixtures in the show.</span>'}</div>
    <div class="lb-row"><label>Order <select id="st-grp-order" class="filter-input">
        <option value="stage">left → right on the stage</option><option value="given">as listed above</option></select></label></div>
    <div class="lb-row">${editing
      ? `<button class="btn btn-accent btn-sm" onclick="stageGroupSave()">✓ Save group</button>
         <button class="btn btn-surface btn-sm" onclick="stageGroupDelete()" title="${editing.used_by.length ? 'Used by RGB matrices — change them first' : 'Delete this group'}">🗑 Delete</button>
         <button class="btn btn-surface btn-sm" onclick="stageGroupEdit(null)">Cancel</button>`
      : `<button class="btn btn-accent btn-sm" onclick="stageGroupSave()">＋ Create group</button>`}</div>
    <div class="vce-hint">The group goes into the show in progress at once (↶ Undo here or in the History). Heads in one row, left → right as seen from the audience.</div>`;
}

function stageGroupPick(id, on) { if (on) _stGrpPick.add(id); else _stGrpPick.delete(id); }
function stageGroupPickAll(on) {
  const name = _stVal('st-grp-name');
  _stGrpPick = new Set(on ? (_stS.all_fixtures || []).map(f => f.id) : []);
  _stRender();
  const n = document.getElementById('st-grp-name'); if (n) n.value = name;
}
function stageGroupFromSel() {
  const ids = [..._stSet].filter(k => k.startsWith('f:')).map(k => k.slice(2));
  if (!ids.length) { setStatus('Select fixtures in the views first (click, Shift-click to add more).', 'warn'); return; }
  const name = _stVal('st-grp-name');
  _stGrpPick = new Set(ids);
  _stRender();
  const n = document.getElementById('st-grp-name'); if (n) n.value = name;
}
function stageGroupShow(gid) {
  const g = (_stS.groups || []).find(x => x.id === gid);
  if (!g) return;
  _stSet = new Set(g.fixtures.map(i => 'f:' + i).filter(k => _stFx(k)));
  _stSel = _stSet.size ? [..._stSet][0] : null;
  _stRender();
  if (!_stSet.size) setStatus(`'${g.name}': its fixtures have no 3D position.`, 'warn');
}
function stageGroupEdit(gid) {
  _stGrpEdit = gid;
  const g = (_stS.groups || []).find(x => x.id === gid);
  _stGrpPick = new Set(g ? g.fixtures : []);
  _stRender();
}
async function stageGroupSave() {
  const name = _stVal('st-grp-name').trim(), order = _stVal('st-grp-order') || 'stage';
  const fixtures = (_stS.all_fixtures || []).map(f => f.id).filter(i => _stGrpPick.has(i));
  const d = _stGrpEdit
    ? await _stOp({ op: 'group_update', gid: _stGrpEdit, name, fixtures, order })
    : await _stOp({ op: 'group_new', name, fixtures, order });
  if (d) {
    _stGrpEdit = null; _stGrpPick = new Set(); _stGrpFlash = name.replace(/\s+/g, ' ').replace(/^["']+|["']+$/g, '').replace(/[:;,.]+$/, '').trim();
    _stRender();
    const el = document.querySelector('#st-body [data-grpflash]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }
}
async function stageGroupDelete() {
  const g = (_stS.groups || []).find(x => x.id === _stGrpEdit);
  if (!g || !confirm(`Delete the group '${g.name}'?`)) return;
  const d = await _stOp({ op: 'group_delete', gid: _stGrpEdit });
  if (d) { _stGrpEdit = null; _stGrpPick = new Set(); _stGrpFlash = ''; _stRender(); }
}

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
        <span class="st-k st-k-f"></span>fixture (click to select) <span class="st-k st-k-x"></span>model file not found</div>
    </div>
    <div class="st-side">
      <div class="lb-tabs" role="tablist">${[
        ['select', `Selection${_stSet.size ? ` (${_stSet.size})` : ''}`, 'The meshes and fixtures on the stage; click one to edit it'],
        ['place', 'Place', 'Push to an edge, centre, floor or ceiling; line up; space evenly — for what is selected'],
        ['add', 'Add', 'Add a mesh from your mesh folders'],
        ['stage', 'Stage', 'The stage type and size'],
        ['groups', `Groups${(_stS.groups || []).length ? ` (${_stS.groups.length})` : ''}`, 'Fixture groups: make one from the fixtures you select, rename, change, delete'],
      ].map(([k, l, t]) => `<button class="subtab-btn${_stTab === k ? ' active' : ''}" data-sttab="${k}" onclick="stageTab('${k}')" title="${t}">${l}</button>`).join('')}</div>
      <div class="lb-card" data-stpane="stage"${_stTab === 'stage' ? '' : ' hidden'}>
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

      <div class="lb-card" data-stpane="select"${_stTab === 'select' ? '' : ' hidden'}>
        <h3>Meshes <span class="p-desc">${_stS.meshes.length} on this stage</span></h3>
        <div class="st-list">${_stS.meshes.map(m => {
          const p = m.place;
          const off = p && p.bottom !== 0;
          return `<div class="st-item ${_stSet.has(m.id) ? 'on' : ''}" onclick="stageSelect('${m.id}', event)">
            <span>${m.found ? '' : '⚠ '}${m.hidden ? '<span title="Hidden in the 3D view">🙈 </span>' : ''}${_esc(m.label)}</span>
            <span class="vce-hint">${p ? `${off ? `<b style="color:var(--warning)">${p.bottom > 0 ? 'floats ' + p.bottom : 'sinks ' + (-p.bottom)} mm</b>` : 'on the floor'}` : 'file not found'}</span></div>`;
        }).join('') || '<div class="vce-hint">No meshes yet — add one below.</div>'}</div>
        <div class="lb-row">
          <button class="btn btn-surface btn-sm" onclick="stageSelectAll(true)">Select all</button>
          <button class="btn btn-surface btn-sm" onclick="stageSelectAll(false)">None</button>
          <button class="btn btn-surface btn-sm" onclick="stageFloor(null)" title="Every mesh with its lowest point on the floor">⤓ Put all on the floor</button>
        </div>
        <div class="vce-hint">Click to select · Shift/⌘-click to select several (here or in the views)</div>
        <details class="vce-sub" ${_stKinds().fx ? 'open' : ''}><summary>Fixtures (${_stS.fixtures.length}) — select them to place meshes around them, or to move them</summary>
          <div class="st-list">${_stS.fixtures.map(f => `<div class="st-item ${_stSet.has(f.key) ? 'on' : ''}" onclick="stageSelect('${f.key}', event)">
            <span><i class="st-k st-k-f"></i>${_esc(f.name)}</span>
            <span class="vce-hint">${f.place.bottom} mm up${f.size_known ? '' : ' · size ?'}</span></div>`).join('') || '<div class="vce-hint">No fixtures on the 3D stage.</div>'}</div>
          <div class="lb-row"><button class="btn btn-surface btn-sm" onclick="stageSelectFixtures()">Select all fixtures</button></div>
        </details>
      </div>

      <div class="lb-card" id="st-edit" data-stpane="select"${_stTab === 'select' ? '' : ' hidden'}>${_stEditHtml()}</div>

      <div class="lb-card" id="st-place" data-stpane="place"${_stTab === 'place' ? '' : ' hidden'}>${_stPlaceHtml()}</div>

      <div class="lb-card" data-stpane="groups"${_stTab === 'groups' ? '' : ' hidden'}>${_stGroupsHtml()}</div>

      <div class="lb-card" data-stpane="add"${_stTab === 'add' ? '' : ' hidden'}>
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
    (_stS.dirty ? '<span class="doc-chip" title="These edits are in the show in progress — 💾 Save as new file… keeps them">edited</span>' : '');
}

function _stEditHtml() {
  if (_stSet.size > 1) {
    const k = _stKinds();
    return `<h3>${_stSet.size} items selected</h3><div class="vce-hint">Place them together in the <a href="#" onclick="stageTab('place');return false">Place</a> tab; click one to edit it.</div>
      ${k.ms ? `<div class="lb-row"><button class="btn btn-surface btn-sm" onclick="stageHide(true)" title="Hide the selected meshes in QLC+'s 3D view (kept in the show)">🙈 Hide meshes</button>
        <button class="btn btn-surface btn-sm" onclick="stageHide(false)">👁 Show meshes</button></div>` : ''}
      ${k.fx ? _stAimHtml() : ''}`;
  }
  const f = _stFx(_stSel);
  if (f) {
    const p = f.place;
    return `<h3>${_esc(f.name)} <span class="p-desc">fixture ${f.id}</span></h3>
      <div class="st-grid">
        <label>Centre X <input id="st-x" type="number" step="10" class="filter-input rr-num" value="${p.x}"> mm</label><span class="vce-hint">from the left edge</span>
        <label>Centre Z <input id="st-z" type="number" step="10" class="filter-input rr-num" value="${p.z}"> mm</label><span class="vce-hint">from the back edge</span>
        <label>Bottom <input id="st-b" type="number" step="10" class="filter-input rr-num" value="${p.bottom}"> mm</label><span class="vce-hint">underside above the floor</span>
      </div>
      <div class="lb-row"><button class="btn btn-surface btn-sm" onclick="stageMoveFixture()">Move</button>
        <span class="vce-hint">body ${p.w} × ${p.h} × ${p.d} mm ${f.size_known ? '(from its .qxf)' : '(assumed — no .qxf dimensions)'} · tilt and pan stay as they are</span></div>
      ${_stAimHtml()}
      <div class="vce-hint">In the file (QLC+ 3D view): X ${f.x} · Y ${f.y} · Z ${f.z} mm · tilt ${f.rot[0]}°</div>`;
  }
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
      <button class="btn btn-surface btn-sm" onclick="stageHide(${m.hidden ? 'false' : 'true'})" title="Hide or show it in QLC+'s 3D view — the mesh stays in the show">${m.hidden ? '👁 Show' : '🙈 Hide'}</button>
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

function _stPlaceHtml() {
  const n = _stSet.size;
  if (!n) return `<h3>Place <span class="p-desc">select meshes and/or fixtures first — in the views or the <a href="#" onclick="stageTab('select');return false">Selection</a> tab</span></h3>
    <div class="vce-hint">Then: push to a stage edge, centre, floor or ceiling; line up; space evenly; nudge (also with the arrow keys). Mix meshes and fixtures to place one kind around the other.</div>`;
  const k = _stKinds();
  const mv = _stVal('st-move') || 'meshes';
  const mixed = k.fx && k.ms;
  const b = (a, t, tip, min = 1) => `<button class="btn btn-surface btn-sm" ${n < min ? 'disabled' : ''} title="${tip}" onclick="stageArrange('${a}')">${t}</button>`;
  return `<h3>Place <span class="p-desc">${n} selected${mixed ? ` — ${k.ms} mesh(es), ${k.fx} fixture(s)` : ''}</span></h3>
    ${mixed ? `<div class="lb-row"><label>Move <select id="st-move" class="filter-input">
        <option value="meshes" ${mv === 'meshes' ? 'selected' : ''}>only the meshes</option>
        <option value="fixtures" ${mv === 'fixtures' ? 'selected' : ''}>only the fixtures</option>
        <option value="all" ${mv === 'all' ? 'selected' : ''}>everything</option></select></label>
      <span class="vce-hint">the others stay put as the reference: e.g. a mesh + two fixtures, only the meshes, <b>centres ↔</b> → the mesh between the fixtures</span></div>` : ''}
    <div class="st-sec">To the stage <span class="vce-hint">several meshes move together, keeping their spacing</span></div>
    <div class="lb-row">
      ${b('left', '⇤ Left', 'Against the left edge')}
      ${b('centre_x', '↔ Centre', 'In the middle, left–right')}
      ${b('right', 'Right ⇥', 'Against the right edge')}
      ${b('back', '⤒ Back', 'Against the back edge')}
      ${b('centre_z', '↕ Middle', 'In the middle, back–front')}
      ${b('front', 'Front ⤓', 'Against the front edge (audience)')}
    </div>
    <div class="lb-row">
      ${b('centre', '⊕ Centre of the stage', 'In the middle of the stage')}
      ${b('floor', '▁ On the floor', 'Each one standing on the floor')}
      ${b('ceiling', '▔ To the ceiling', 'Each one hanging with its top at the stage height')}
      <label class="vce-hint">gap to the edge <input id="st-margin" type="number" min="0" step="50" class="filter-input st-n" value="${_stVal('st-margin') || 0}"> mm</label>
    </div>
    <div class="st-sec">Line up <span class="vce-hint">2 or more</span></div>
    <div class="lb-row">
      ${b('align_left', 'left edges', 'Left edges in line', 2)}
      ${b('align_centre_x', 'centres ↔', 'Centres in line (left–right)', 2)}
      ${b('align_right', 'right edges', 'Right edges in line', 2)}
      ${b('align_back', 'backs', 'Back edges in line', 2)}
      ${b('align_centre_z', 'centres ↕', 'Centres in line (back–front)', 2)}
      ${b('align_front', 'fronts', 'Front edges in line', 2)}
      ${b('align_bottom', 'bottoms', 'Same height of the lowest point', 2)}
      ${b('align_top', 'tops', 'Same height of the highest point', 2)}
    </div>
    <div class="st-sec">Space evenly</div>
    <div class="lb-row">
      ${b('distribute_x', '⇹ between the outer two, left–right', 'Equal gaps; the outer two stay', 3)}
      ${b('distribute_z', '⇳ back–front', 'Equal gaps; the outer two stay', 3)}
    </div>
    <div class="lb-row">
      ${b('spread_x', '⟷ across the stage width', 'Equal gaps across the whole width (inside the gap to the edge)')}
      ${b('spread_z', '⟷ across the depth', 'Equal gaps across the whole depth')}
    </div>
    <div class="st-sec">Nudge <span class="vce-hint">or arrow keys (← → back/front ↑ ↓, PgUp/PgDn height; Shift = ÷10)</span></div>
    <div class="lb-row">
      <button class="btn btn-surface btn-sm" onclick="stageNudge(-1,0,0)" title="Left">←</button>
      <button class="btn btn-surface btn-sm" onclick="stageNudge(1,0,0)" title="Right">→</button>
      <button class="btn btn-surface btn-sm" onclick="stageNudge(0,-1,0)" title="Back">↑ back</button>
      <button class="btn btn-surface btn-sm" onclick="stageNudge(0,1,0)" title="Front">↓ front</button>
      <button class="btn btn-surface btn-sm" onclick="stageNudge(0,0,1)" title="Up">▲ up</button>
      <button class="btn btn-surface btn-sm" onclick="stageNudge(0,0,-1)" title="Down">▼ down</button>
      <label class="vce-hint">step <input id="st-step" type="number" min="1" step="10" class="filter-input st-n" value="${_stVal('st-step') || 100}"> mm</label>
    </div>`;
}

function _stMoveMode() {
  const k = _stKinds();
  return (k.fx && k.ms) ? (_stVal('st-move') || 'meshes') : 'all';
}

function stageArrange(action) {
  _stOp({ op: 'arrange', ids: [..._stSet], action, margin: +_stVal('st-margin') || 0, move: _stMoveMode() });
}

function stageSelectFixtures() {
  _stSet = new Set(_stS.fixtures.map(f => f.key));
  _stSel = _stSet.size ? [..._stSet][0] : null;
  _stRender();
}

function stageMoveFixture() {
  _stOp({ op: 'move_fixture', id: _stSel.slice(2), x: _stVal('st-x'), z: _stVal('st-z'), bottom: _stVal('st-b') });
}

function stageNudge(sx, sz, sy, div) {
  if (!_stSet.size) return;
  const step = (+_stVal('st-step') || 100) / (div || 1);
  _stOp({ op: 'arrange', ids: [..._stSet], action: 'nudge', dx: sx * step, dz: sz * step, dy: sy * step, move: _stMoveMode() }, true);
}

function stageSelectAll(on) {
  _stSet = new Set(on ? _stS.meshes.filter(m => m.place).map(m => m.id) : []);
  _stSel = _stSet.size ? [..._stSet][0] : null;
  _stRender();
}

document.addEventListener('keydown', e => {
  if (!document.getElementById('scr-stage')?.classList.contains('active') || !_stSet.size) return;
  const t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')) return;
  const k = { ArrowLeft: [-1, 0, 0], ArrowRight: [1, 0, 0], ArrowUp: [0, -1, 0], ArrowDown: [0, 1, 0],
              PageUp: [0, 0, 1], PageDown: [0, 0, -1] }[e.key];
  if (!k) return;
  e.preventDefault();
  stageNudge(...k, e.shiftKey ? 10 : 1);
});

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
      <div class="st-item"><span class="st-libname"><img class="st-thumb" loading="lazy" alt="" src="/api/stage/thumb?path=${encodeURIComponent(i.path)}">${_esc(i.name)} <span class="vce-hint">${_esc(i.folder)}</span></span>
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
function stageSelect(id, ev) {
  if (ev && (ev.shiftKey || ev.metaKey || ev.ctrlKey)) {
    if (_stSet.has(id)) _stSet.delete(id); else _stSet.add(id);
    _stSel = _stSet.has(id) ? id : ([..._stSet].pop() || null);
  } else {
    _stSel = id; _stSet = new Set([id]);
  }
  _stRender();
}
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
function _stAimHtml() {
  const ms = (_stS.meshes || []).filter(m => m.place);
  const sel = _stVal('st-aim-t') || (ms[0] ? 'm:' + ms[0].id : 'p');
  const opts = ms.map(m => `<option value="m:${m.id}" ${sel === 'm:' + m.id ? 'selected' : ''}>${_esc(m.label)}</option>`).join('')
    + `<option value="p" ${sel === 'p' ? 'selected' : ''}>a point…</option>`;
  const wh = _stVal('st-aim-w') || 'centre';
  return `<div class="st-sec">Aim <span class="vce-hint">tilt only — pan and roll stay as they are</span></div>
    <div class="lb-row"><label>at <select id="st-aim-t" class="filter-input" onchange="_stRender()">${opts}</select></label>
      ${sel === 'p'
        ? `<label>Z <input id="st-aim-z" type="number" step="100" class="filter-input rr-num" value="${_stVal('st-aim-z') || 3000}"> mm</label>
           <label>height <input id="st-aim-h" type="number" step="100" class="filter-input rr-num" value="${_stVal('st-aim-h') || 0}"> mm</label>`
        : `<label><select id="st-aim-w" class="filter-input">${[['centre', 'its centre'], ['top', 'its top'], ['floor', 'the floor under it']].map(([v, l]) =>
            `<option value="${v}" ${wh === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>`}
      <button class="btn btn-surface btn-sm" onclick="stageAim()">🎯 Aim</button></div>
    <div class="vce-hint">Z is measured from the back edge; the height from the floor. Undo brings the old tilt back.</div>`;
}
function stageAim() {
  const fx = [..._stSet].filter(k => k.startsWith('f:')).map(k => k.slice(2));
  if (!fx.length) return;
  const t = _stVal('st-aim-t');
  const body = { op: 'aim', fixtures: fx };
  if (t.startsWith('m:')) { body.mesh = t.slice(2); body.where = _stVal('st-aim-w') || 'centre'; }
  else body.point = { z: _stVal('st-aim-z'), height: _stVal('st-aim-h') };
  _stOp(body);
}
function stageHide(h) {
  const ids = [..._stSet].filter(k => !k.startsWith('f:'));
  if (ids.length) _stOp({ op: h ? 'hide' : 'show', ids });
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
  const cls = m => 'st-m' + (_stSet.has(m.id) ? ' sel' : '') + (m.hidden ? ' hid' : '');
  // plan
  box.innerHTML = `<svg width="${W * k + 2 * pad}" height="${ph}" data-k="${k}">
    <rect x="${pad}" y="${pad}" width="${W * k}" height="${D * k}" class="st-floor"/>
    <text x="${pad + W * k / 2}" y="${pad - 6}" class="st-t" text-anchor="middle">back</text>
    <text x="${pad + W * k / 2}" y="${ph - 4}" class="st-t" text-anchor="middle">front · audience</text>
    ${fx.map(f => `<g class="st-fx${_stSet.has(f.key) ? ' sel' : ''}" data-id="${f.key}" onmousedown="_stDown(event,'plan','${f.key}')"><title>${_esc(f.name)}</title>
      <rect x="${pad + f.place.x0 * k}" y="${pad + f.place.z0 * k}" width="${Math.max(6, f.place.w * k)}" height="${Math.max(6, f.place.d * k)}" rx="2"/></g>`).join('')}
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
    ${fx.map(f => `<g class="st-fx${_stSet.has(f.key) ? ' sel' : ''}" data-id="${f.key}" onmousedown="_stDown(event,'front','${f.key}')"><title>${_esc(f.name)}</title>
      <rect x="${pad + f.place.x0 * k}" y="${floorY - f.place.top * k}" width="${Math.max(6, f.place.w * k)}" height="${Math.max(6, f.place.h * k)}" rx="2"/></g>`).join('')}
    ${ms.map(m => `<g class="${cls(m)}" data-id="${m.id}" onmousedown="_stDown(event,'front','${m.id}')">
      <rect x="${pad + m.place.x0 * k}" y="${floorY - m.place.top * k}" width="${Math.max(3, m.place.w * k)}" height="${Math.max(3, m.place.h * k)}"/>
      <text x="${pad + m.place.x * k}" y="${floorY - m.place.top * k - 3}" text-anchor="middle">${_esc(m.label.slice(0, 16))}</text></g>`).join('')}
  </svg>`;
  _stS._k = k;
  const miss = _stS.meshes.filter(m => !m.place).length;
  if (miss) box.insertAdjacentHTML('beforeend', `<div class="vce-hint">${miss} mesh(es) not drawn — their model file is not found here.</div>`);
}

function _stDown(e, view, id) {
  e.preventDefault();
  if (e.shiftKey || e.metaKey || e.ctrlKey) { stageSelect(id, e); return; }
  if (!_stSet.has(id)) { _stSet = new Set([id]); }
  _stSel = id;
  const m = _stItem(id);
  const svg = e.currentTarget.ownerSVGElement;
  const gs = [..._stSet].map(i => svg.querySelector(`g[data-id="${i}"]`)).filter(Boolean);
  _stDrag = { view, id, sx: e.clientX, sy: e.clientY, p: { ...m.place }, gs, moved: false };
  document.addEventListener('mousemove', _stMoveEv);
  document.addEventListener('mouseup', _stUpEv, { once: true });
}

function _stMoveEv(e) {
  const d = _stDrag; if (!d) return;
  const dx = (e.clientX - d.sx), dy = (e.clientY - d.sy);
  if (Math.hypot(dx, dy) > 3) d.moved = true;
  d.gs.forEach(g => g.setAttribute('transform', `translate(${dx},${dy})`));
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
  if (!d.moved) { _stSet = new Set([d.id]); _stRender(); return; }
  if (_stSet.size > 1) {
    const ddx = d.nx - d.p.x;
    _stOp(d.view === 'plan' ? { op: 'arrange', action: 'nudge', ids: [..._stSet], dx: ddx, dz: d.nz - d.p.z, move: 'all' }
                            : { op: 'arrange', action: 'nudge', ids: [..._stSet], dx: ddx, dy: d.nb - d.p.bottom, move: 'all' });
    return;
  }
  const isFx = d.id.startsWith('f:');
  const base = isFx ? { op: 'move_fixture', id: d.id.slice(2) } : { op: 'move', id: d.id };
  _stOp(d.view === 'plan' ? { ...base, x: d.nx, z: d.nz } : { ...base, x: d.nx, bottom: d.nb });
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
    setStatus(msg + ' A separate copy — the show in progress already has these stage edits.', 'ok');
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
  }
}
