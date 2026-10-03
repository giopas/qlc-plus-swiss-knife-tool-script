/**
 * VC Builder (WORKPLAN Phase 2.4) — extends the VC Visual Editor.
 *
 * Create / delete / duplicate widgets, wire them to functions (picker
 * filtered by nomenclature, or drag a function onto the canvas), pages
 * (rename, reorder, first page, delete), label panels (nomenclature legend),
 * auto-arrange by nomenclature, screen profiles, page templates, and the
 * setlist CueList.  Every change goes through /api/vc/op (undoable, saved
 * with 💾 Apply & Save QXW…).  Uses the editor's globals (_vcePage, _vceSel,
 * _vceNodes, _vceFlush, _vceOp, _vceReloadAt, _vceStatus, _vceHitTest …).
 */

let _vcbInfo = null;            // /api/vc/builder-info
let _vcbProfile = 'plain';

async function vcbLoadInfo() {
  try {
    const r = await fetch('/api/vc/builder-info?profile=' + encodeURIComponent(_vcbProfile));
    if (!r.ok) return;
    _vcbInfo = await r.json();
    _vcbRenderPanel();
    if (typeof _vceRenderProps === 'function') _vceRenderProps();
  } catch (e) { /* no workspace */ }
}

function _vcbFn(id) { return (_vcbInfo?.functions || []).find(f => f.id === String(id)); }
const _VCB_WIRABLE = new Set(['Button', 'CueList', 'Slider']);

async function _vcbRun(body, focus, sel, msg) {
  try {
    if (!(await _vceFlush())) return null;
    const d = await _vceOp(body);
    await _vceReloadAt(focus ?? (_vcePage && _vcePage.id), sel ?? (d.new_ids || []));
    _vceStatus('✓ ' + (typeof msg === 'function' ? msg(d) : msg) + ' · not saved yet', 'ok');
    return d;
  } catch (e) {
    _vceStatus('✗ ' + e.message, 'error');
    return null;
  }
}

// ── selection panel (in the properties) ──────────────────────────────────────
function _vcbSelectionHtml(selArr) {
  if (!selArr.length || !_vcbInfo) return '';
  const first = selArr[0];
  const single = selArr.length === 1;
  const isPage = single && _vcePage && first.id === _vcePage.id && !first.parent_id;
  let html = '';
  if (single && first.type === 'Button' && ['StopAll', 'Blackout'].includes(first.action)) {
    html += `<div class="vce-sec">Function</div><div class="vce-hint" style="margin-bottom:4px">${first.action === 'StopAll'
      ? 'Stop all functions' : 'Blackout'} button — it needs no function.</div>`;
  } else if (single && _VCB_WIRABLE.has(first.type)) {
    const fns = _vcbInfo.functions.filter(f => first.type !== 'CueList' || f.type === 'Chaser');
    html += `<div class="vce-sec">Function <span class="vce-hint">what this ${first.type === 'CueList' ? 'CueList plays (a chaser)' : first.type === 'Slider' ? 'slider plays' : 'button runs'}</span></div>
      <div style="font-size:11px;margin-bottom:4px">${first.func_id
        ? `→ <b>${_esc(first.func_name || '?')}</b> <span class="vce-hint">[${_esc(first.func_id)}]</span>`
        : '<span style="color:#f9e2af">not wired</span> <span class="vce-hint">— pick one here, or drag one from ＋ Add &amp; wire onto it</span>'}</div>
      <div class="vce-row">
        <select id="vcb-wire-sel" class="vce-pi" style="flex:1;min-width:0">${first.func_id ? '' : '<option value="">— choose —</option>'}${fns.map(f =>
          `<option value="${_esc(f.id)}" ${f.id === first.func_id ? 'selected' : ''}>${_esc(f.name)} · ${_esc(f.type)}</option>`).join('')}</select>
        <button class="vce-ab" onclick="vcbWire(document.getElementById('vcb-wire-sel').value)">Wire</button>
        ${first.func_id ? `<button class="vce-ab" onclick="vcbWire('')" title="Unwire">✕</button>` : ''}
      </div>${first.type === 'CueList' ? `
      <div class="vce-row">
        <button class="vce-ab" onclick="vcbNewSetlistFor('${_esc(first.id)}')" title="Creates an empty chaser 'Setlist' and wires this CueList to it">▶ Use for a new setlist</button>
        <span class="vce-hint">then fill it in the <a href="#" onclick="go('setlist');return false">Setlist</a></span>
      </div>` : ''}`;
  }
  if (!isPage) {
    html += `<div class="vce-sec">Edit</div>
      <div class="vce-row">
        <button class="vce-ab" onclick="vcbDuplicate()" title="⌘D — copies next to the originals (key/MIDI not copied)">⧉ Duplicate</button>
        <button class="vce-ab" onclick="vcbDelete()" title="Delete / Backspace">🗑 Delete</button>
        ${single && (first.type === 'Frame' || first.type === 'SoloFrame') ? `
          <button class="vce-ab" onclick="vcbAutoArrange('${_esc(first.id)}')" title="One row per naming group (the name prefix), in the profile's order — profile chosen in ＋ Add &amp; wire">⇶ Arrange buttons by name group</button>` : ''}
      </div>`;
  }
  return html;
}

async function vcbWire(fid) {
  const id = [..._vceSel][0];
  if (!id) return;
  await _vcbRun({ op: 'wire', widget_id: id, func_id: fid }, id, [id], d => d.wired);
}

async function vcbDelete() {
  const ids = [..._vceSel].filter(id => !_vcePage || id !== _vcePage.id);
  if (!ids.length) return;
  await _vcbRun({ op: 'delete', ids }, _vcePage.id, [], d => `Deleted ${d.deleted} widget(s)`);
}

async function vcbDuplicate() {
  const ids = [..._vceSel].filter(id => !_vcePage || id !== _vcePage.id);
  if (!ids.length) return;
  await _vcbRun({ op: 'duplicate', ids }, null, null, d => `Duplicated ${d.count} widget(s)`);
}

async function vcbAutoArrange(frameId) {
  await _vcbRun({ op: 'auto_arrange', frame_id: frameId, profile: _vcbProfile }, frameId, [frameId],
    d => `Arranged ${d.arranged} button(s) in ${d.groups} group(s)`);
}

function _vcbOnKey(e, mod) {
  if (!_vceSel.size) return false;
  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); vcbDelete(); return true; }
  if (mod && (e.key === 'd' || e.key === 'D')) { e.preventDefault(); vcbDuplicate(); return true; }
  return false;
}

// ── drag a function onto the canvas ──────────────────────────────────────────
function _vcbSetupCanvas(cv) {
  cv.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/x-qsk-fn')) e.preventDefault(); });
  cv.addEventListener('drop', async e => {
    const fid = e.dataTransfer.getData('text/x-qsk-fn');
    if (!fid || !_vcePage) return;
    e.preventDefault();
    const [ax, ay] = _vceCanvasXY(e);
    const hit = _vceHitTest(ax, ay);
    const fn = _vcbFn(fid);
    if (hit && _VCB_WIRABLE.has(hit.type)) {
      await _vcbRun({ op: 'wire', widget_id: hit.id, func_id: fid }, hit.id, [hit.id], d => d.wired);
      return;
    }
    const box = hit && (hit.type === 'Frame' || hit.type === 'SoloFrame') ? hit : _vceNodes[_vcePage.id];
    const x = Math.max(0, Math.round(ax - box._absX)), y = Math.max(0, Math.round(ay - box._absY));
    await _vcbRun({ op: 'create', parent_id: box.id, kind: fn && fn.type === 'Chaser' && e.altKey ? 'CueList' : 'Button',
                    caption: fn ? fn.name : '', x, y, func_id: fid }, box.id, null,
      d => `New button for '${fn ? fn.name : fid}'`);
  });
}

function vcbDragFn(e, fid) {
  e.dataTransfer.setData('text/x-qsk-fn', fid);
  e.dataTransfer.effectAllowed = 'copy';
}

// ── the Builder panel ────────────────────────────────────────────────────────
function _vcbTargetLabel() {
  const id = _vcbTarget();
  const n = id && _vceNodes[id];
  if (!n) return '—';
  return _vcePage && id === _vcePage.id ? `the page “${_esc(n.caption || 'page')}”` : `the frame “${_esc(n.caption || n.type)}”`;
}

function _vcbRenderPanel() {
  const add = document.getElementById('vcb-add');
  const pages = document.getElementById('vcb-pages');
  if (!add || !pages || !_vcbInfo) return;
  const I = _vcbInfo;
  const opt = (v, t, sel) => `<option value="${_esc(v)}" ${sel ? 'selected' : ''}>${_esc(t)}</option>`;
  const q = s => _esc(s).replace(/'/g, "\\'");

  add.innerHTML = `
    <div class="vce-intro">Put new widgets on the page and connect them to your functions. Everything is undoable, goes into the show in progress, and is kept with 💾 Save as new file….</div>

    ${_vcbSetlistCard()}

    <div class="vce-sec"><span class="vce-step">1</span>New widget</div>
    <div class="vce-row">
      <select id="vcb-kind" class="vce-pi" style="width:92px">${I.kinds.map(k => opt(k, k)).join('')}</select>
      <input id="vcb-caption" class="vce-pi" style="flex:1;min-width:80px" placeholder="caption">
      <button class="vce-ab" onclick="vcbCreate()">＋ Add</button>
    </div>
    <div class="vce-hint">goes into <span id="vcb-target">${_vcbTargetLabel()}</span> at the first free spot — select a frame first to put it there</div>

    <div class="vce-sec"><span class="vce-step">2</span>Wire to a function</div>
    <div class="vce-hint" style="margin-bottom:5px">
      <b>Drag</b> a function onto a button, CueList or slider to wire it — onto a frame or empty page to add a new button for it (⌥ Alt: a CueList).
      <b>Double-click</b> wires the selected widget.</div>
    <div class="vce-row">
      <input id="vcb-q" class="vce-pi" style="flex:1;min-width:80px" placeholder="search functions" oninput="_vcbRenderFnList()">
      <select id="vcb-type" class="vce-pi" style="width:92px" onchange="_vcbRenderFnList()">
        <option value="">all types</option>${[...new Set(I.functions.map(f => f.type))].sort().map(t => opt(t, t)).join('')}</select>
    </div>
    <div class="vce-row">
      <label class="vce-lb">names
        <select id="vcb-prof" class="vce-pi" style="width:130px" onchange="vcbSetProfile(this.value)" title="Naming profile: filters by group/effect letters and drives 'Arrange by name group'">${
          I.profiles.map(p => opt(p.id, p.label, p.id === _vcbProfile)).join('')}</select></label>
      ${Object.keys(I.groups).length ? `
      <select id="vcb-grp" class="vce-pi" style="width:100px" onchange="_vcbRenderFnList()">
        <option value="">all groups</option>${Object.entries(I.groups).map(([k, v]) => opt(k, `${k} · ${v}`)).join('')}</select>
      <select id="vcb-eff" class="vce-pi" style="width:100px" onchange="_vcbRenderFnList()">
        <option value="">all effects</option>${Object.entries(I.effects).map(([k, v]) => opt(k, `${k} · ${v}`)).join('')}</select>` : ''}
    </div>
    <div id="vcb-fnlist" class="vcb-fnlist"></div>

    <div class="vce-sec"><span class="vce-step">3</span>Ready-made blocks</div>
    <details class="vce-sub"><summary>🏷 Label panel — your naming legend, or any text, as labels in columns</summary>
      <div class="vce-row">
        <select id="vcb-lsrc" class="vce-pi" style="width:150px" onchange="document.getElementById('vcb-ltext').style.display=this.value==='custom'?'':'none'">
          ${I.legend.length ? opt('legend', 'Naming legend') : ''}${opt('custom', 'My text (one per line)')}</select>
        <label class="vce-lb">title <input id="vcb-ltitle" class="vce-pi" style="width:80px" value="Legend"></label>
        <label class="vce-lb">cols <input id="vcb-lcols" type="number" min="1" max="8" value="2" class="vce-pi vce-n"></label>
      </div>
      <textarea id="vcb-ltext" class="vce-pi" rows="3" style="${I.legend.length ? 'display:none;' : ''}margin-bottom:4px" placeholder="one label per line"></textarea>
      <div class="vce-row"><button class="vce-ab" onclick="vcbLabelPanel()">＋ Add label panel</button></div>
    </details>`;

  pages.innerHTML = `
    <div class="vce-intro">Pages are the tabs of the Virtual Console; QLC+ opens on the first one.</div>

    <div class="vce-sec">This page</div>
    <div class="vce-row">
      <input id="vcb-pname" class="vce-pi" style="flex:1;min-width:80px" value="${_esc(_vcePage ? _vcePage.caption : '')}">
      <button class="vce-ab" onclick="vcbRenamePage()">✎ Rename</button>
    </div>
    <div class="vce-row">
      <button class="vce-ab" onclick="vcbMovePage(-1)">◀ Move left</button>
      <button class="vce-ab" onclick="vcbMovePage(1)">Move right ▶</button>
      <button class="vce-ab" onclick="vcbMovePage(0, true)" title="QLC+ opens on the first page">★ Make first</button>
      <button class="vce-ab" onclick="vcbDeletePage()">🗑 Delete page</button>
    </div>

    <div class="vce-sec">New page</div>
    <div class="vce-row">
      <input id="vce-page-name" class="vce-pi" style="flex:1;min-width:80px" placeholder="name (optional)">
    </div>
    <div class="vce-row">
      <button class="vce-ab" onclick="vceNewPage()">＋ Empty page</button>
      <button class="vce-ab" onclick="vceDuplicatePage()" title="Copy this page with all its widgets (new IDs)">⧉ Copy of this page</button>
      <label class="vce-lb"><input type="checkbox" id="vce-page-keep"> keep key/MIDI</label>
    </div>

    <div class="vce-sec">Screen size</div>
    <div class="vce-row">
      <select id="vcb-screen" class="vce-pi" style="width:160px">${I.screens.map(s => opt(s.id, s.label)).join('')}</select>
      <select id="vcb-sall" class="vce-pi" style="width:90px">${opt('page', 'this page')}${opt('all', 'all pages')}</select>
    </div>
    <div class="vce-row">
      <label class="vce-lb" title="Move and resize every widget in proportion"><input type="checkbox" id="vcb-scale"> scale the widgets too</label>
      <button class="vce-ab" onclick="vcbScreen()">Apply size</button>
    </div>

    <div class="vce-sec">Templates <span class="vce-hint">reuse a page in another show</span></div>
    <div class="vce-row">
      <input id="vcb-tname" class="vce-pi" style="flex:1;min-width:80px" placeholder="template name">
      <button class="vce-ab" onclick="vcbSaveTemplate()" title="Layout, colours and function names — no key/MIDI">💾 Save this page</button>
    </div>
    <div class="vce-hint" style="margin-bottom:4px">Saved templates — ＋ adds one as a new page; its buttons find their functions by name:</div>
    ${I.templates.length ? I.templates.map(t => `
      <div class="vce-row" style="justify-content:space-between">
        <span>${_esc(t.name)} <span class="vce-hint">${t.widgets} widgets · ${t.functions} functions</span></span>
        <span><button class="vce-ab" onclick="vcbApplyTemplate('${q(t.name)}')">＋ Add as page</button>
              <button class="vce-ab" onclick="vcbDeleteTemplate('${q(t.name)}')" title="Delete template">🗑</button></span>
      </div>`).join('') : '<div class="vce-hint">none yet</div>'}`;
  _vcbRenderFnList();
}

// ── Setlist cue list: always on top of "Add & wire" ─────────────────────────
function _vcbSelCueList() {
  const s = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  return s.length === 1 && s[0].type === 'CueList' ? s[0] : null;
}

function _vcbSetlistBtnLabel() {
  const cl = _vcbSelCueList();
  return cl ? `Wire “${_esc(cl.caption || 'CueList')}”` : '＋ Add a CueList on this page';
}

function _vcbSetlistCard() {
  const I = _vcbInfo;
  const opt = (v, t) => `<option value="${_esc(v)}">${_esc(t)}</option>`;
  const cls = I.cuelists || [];
  const state = cls.length
    ? `This show has ${cls.length} CueList${cls.length > 1 ? 's' : ''}: ${cls.slice(0, 3).map(c => `<b>${_esc(c.caption || 'CueList')}</b>`).join(', ')}${cls.length > 3 ? '…' : ''}.`
    : '<b style="color:#f9e2af">This show has no CueList yet</b> — add one here and the Setlist can fill it.';
  return `
    <div class="vcb-card">
      <div class="vcb-card-t">▶ Setlist cue list</div>
      <div class="vce-hint" style="margin-bottom:5px">${state}</div>
      <div class="vce-row">
        <label class="vce-lb">plays</label>
        <select id="vcb-chaser" class="vce-pi" style="flex:1;min-width:0">${opt('__new__', '＋ a new, empty setlist chaser')}${I.chasers.map(c => opt(c.id, c.name)).join('')}</select>
      </div>
      <div class="vce-row">
        <button class="vce-ab vcb-primary" id="vcb-sl-btn" onclick="vcbSetlist()">${_vcbSetlistBtnLabel()}</button>
      </div>
      <div class="vce-hint">Select a CueList on the canvas to re-wire it instead. Then fill the songs in the <a href="#" onclick="go('setlist');return false">Setlist</a>.</div>
    </div>`;
}

function _vcbSyncSetlistBtn() {
  const b = document.getElementById('vcb-sl-btn');
  if (b) b.innerHTML = _vcbSetlistBtnLabel();
}

function _vcbRenderFnList() {
  const el = document.getElementById('vcb-fnlist');
  if (!el || !_vcbInfo) return;
  const q = (document.getElementById('vcb-q')?.value || '').toLowerCase();
  const t = document.getElementById('vcb-type')?.value || '';
  const g = document.getElementById('vcb-grp')?.value || '';
  const e = document.getElementById('vcb-eff')?.value || '';
  const fns = _vcbInfo.functions.filter(f => (!q || f.name.toLowerCase().includes(q) || f.id === q) &&
    (!t || f.type === t) && (!g || f.group === g) && (!e || f.effect === e));
  el.innerHTML = fns.slice(0, 300).map(f =>
    `<div class="vcb-fn" draggable="true" ondragstart="vcbDragFn(event,'${_esc(f.id)}')"
          ondblclick="vcbWire('${_esc(f.id)}')" title="Drag onto the canvas · double-click: wire the selected widget">
       <span>${_esc(f.name)}</span><span class="vcb-t">${_esc(f.type)} ${_esc(f.id)}</span></div>`).join('') +
    (fns.length > 300 ? `<div class="vcb-t">… ${fns.length - 300} more — narrow the search</div>` : '') +
    (!fns.length ? '<div class="vcb-t">no match</div>' : '');
}

function vcbSetProfile(p) { _vcbProfile = p; vcbLoadInfo(); }

function _vcbTarget() {
  const s = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (s.length === 1 && (s[0].type === 'Frame' || s[0].type === 'SoloFrame')) return s[0].id;
  return _vcePage && _vcePage.id;
}

async function vcbCreate() {
  const kind = document.getElementById('vcb-kind').value;
  const caption = document.getElementById('vcb-caption').value;
  const parent = _vcbTarget();
  if (!parent) return;
  await _vcbRun({ op: 'create', parent_id: parent, kind, caption }, parent, null, `${kind} added`);
}

async function vcbRenamePage() {
  if (!_vcePage) return;
  const caption = document.getElementById('vcb-pname').value;
  const d = await _vcbRun({ op: 'rename_page', page_id: _vcePage.id, caption }, _vcePage.id, [], 'Page renamed');
  if (d) vcbLoadInfo();
}

async function vcbMovePage(dir, first) {
  if (!_vcePage) return;
  const idx = _vcePages.findIndex(p => p.id === _vcePage.id);
  const to = first ? 0 : idx + dir;
  if (to < 0 || to >= _vcePages.length || to === idx) return;
  await _vcbRun({ op: 'move_page', page_id: _vcePage.id, index: to }, _vcePage.id, [],
    first ? 'Page is now page 1 (QLC+ opens on it)' : 'Page moved');
}

async function vcbDeletePage() {
  if (!_vcePage) return;
  if (!confirm(`Delete the page '${_vcePage.caption}' and everything on it? (Undo is available until you reload.)`)) return;
  await _vcbRun({ op: 'delete_page', page_id: _vcePage.id }, null, [], d => `Page deleted (${d.deleted} widgets)`);
}

async function vcbLabelPanel() {
  const src = document.getElementById('vcb-lsrc').value;
  const lines = src === 'legend' ? _vcbInfo.legend
    : document.getElementById('vcb-ltext').value.split('\n').map(s => s.trim()).filter(Boolean);
  if (!lines.length) { _vceStatus('Type the labels, one per line.', 'warn'); return; }
  const parent = _vcbTarget();
  await _vcbRun({ op: 'label_panel', parent_id: parent, lines, title: document.getElementById('vcb-ltitle').value || 'Legend',
                  columns: +document.getElementById('vcb-lcols').value || 2 }, parent, null,
    d => `Label panel with ${d.labels} label(s)`);
}

async function vcbScreen() {
  const profile_id = document.getElementById('vcb-screen').value;
  const all = document.getElementById('vcb-sall').value === 'all';
  const scale = document.getElementById('vcb-scale').checked;
  await _vcbRun({ op: 'screen', profile_id, scale, page_ids: all ? [] : [_vcePage.id] }, _vcePage.id, [],
    d => `${d.pages} page(s) set to ${d.size}` + (d.outside ? ` — ${d.outside} widget(s) now outside the page (move them, or use "scale")` : ''));
}

async function vcbSaveTemplate() {
  const name = document.getElementById('vcb-tname').value.trim();
  if (!name || !_vcePage) { _vceStatus('Type a template name.', 'warn'); return; }
  if (!(await _vceFlush())) return;
  const r = await fetch('/api/vc/template', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'save', page_id: _vcePage.id, name }) });
  const d = await r.json();
  if (!r.ok) { _vceStatus('✗ ' + d.error, 'error'); return; }
  _vcbInfo.templates = d.templates; _vcbRenderPanel();
  _vceStatus(`✓ Template '${d.template}' saved — ${d.widgets} widgets, ${d.functions} function(s) by name`, 'ok');
}

async function vcbApplyTemplate(name) {
  const d = await _vcbRun({ op: 'apply_template', name }, null, [],
    d => `Template added as a new page — ${d.matched} function(s) found` +
         (d.missing.length ? `, not in this show: ${d.missing.slice(0, 5).join(', ')}${d.missing.length > 5 ? '…' : ''} (buttons left unwired)` : ''));
  if (d) await _vceReloadAt(d.page_id, []);
}

async function vcbDeleteTemplate(name) {
  if (!confirm(`Delete the template '${name}'?`)) return;
  const r = await fetch('/api/vc/template', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'delete', name }) });
  const d = await r.json();
  if (!r.ok) { _vceStatus('✗ ' + d.error, 'error'); return; }
  _vcbInfo.templates = d.templates; _vcbRenderPanel();
}

async function vcbNewSetlistFor(cl) {
  await _vcbRun({ op: 'setlist_cuelist', chaser_id: '__new__', cuelist_id: cl }, cl, [cl],
    () => 'CueList wired to a new, empty setlist chaser — fill it in the Setlist');
  vcbLoadInfo();
}

async function vcbSetlist() {
  const chaser_id = document.getElementById('vcb-chaser').value;
  if (!chaser_id) return;
  const s = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  const cl = s.length === 1 && s[0].type === 'CueList' ? s[0].id : '';
  await _vcbRun({ op: 'setlist_cuelist', chaser_id, cuelist_id: cl, page_id: _vcePage && _vcePage.id },
    cl || null, cl ? [cl] : null, d => (d.wired || 'CueList added') + ' — fill it in the Setlist');
  vcbLoadInfo();
}
