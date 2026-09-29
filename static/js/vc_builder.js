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
  const isPage = single && _vcePage && first.id === _vcePage.id;
  let html = '';
  if (single && first.type === 'Button' && ['StopAll', 'Blackout'].includes(first.action)) {
    html += `<div class="vce-pl">Function</div><div style="font-size:10px;margin-bottom:6px">${first.action === 'StopAll'
      ? 'Stop all functions' : 'Blackout'} button — it needs no function</div>`;
  } else if (single && _VCB_WIRABLE.has(first.type)) {
    const fns = _vcbInfo.functions.filter(f => first.type !== 'CueList' || f.type === 'Chaser');
    html += `<div class="vce-pl">Function</div>
      <div style="font-size:10px;margin-bottom:3px">${first.func_id
        ? `→ ${_esc(first.func_name || '?')} <span style="color:var(--text-muted)">[${_esc(first.func_id)}]</span>`
        : '<span style="color:var(--text-muted)">not wired — pick one, or drag a function from the list below onto it</span>'}</div>
      <div style="display:flex;gap:4px;margin-bottom:6px">
        <select id="vcb-wire-sel" class="vce-pi" style="width:230px">${fns.map(f =>
          `<option value="${_esc(f.id)}" ${f.id === first.func_id ? 'selected' : ''}>${_esc(f.name)} · ${_esc(f.type)}</option>`).join('')}</select>
        <button class="vce-ab" onclick="vcbWire(document.getElementById('vcb-wire-sel').value)">Wire</button>
        ${first.func_id ? `<button class="vce-ab" onclick="vcbWire('')" title="Unwire">✕</button>` : ''}
      </div>`;
  }
  if (!isPage) {
    html += `<div style="display:flex;gap:4px;margin-bottom:6px">
      <button class="vce-ab" onclick="vcbDuplicate()" title="⌘D — copies next to the originals (key/MIDI not copied)">⧉ Duplicate</button>
      <button class="vce-ab" onclick="vcbDelete()" title="Delete / Backspace">🗑 Delete</button>
      ${single && (first.type === 'Frame' || first.type === 'SoloFrame') ? `
        <button class="vce-ab" onclick="vcbAutoArrange('${_esc(first.id)}')" title="One row per nomenclature group (the name prefix), in the profile's order">⇶ Arrange by name group</button>` : ''}
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
function _vcbRenderPanel() {
  const el = document.getElementById('vcb-panel');
  if (!el || !_vcbInfo) return;
  const I = _vcbInfo;
  const moreOpen = !!el.querySelector('details.vcb-more')?.open;
  const opt = (v, t, sel) => `<option value="${_esc(v)}" ${sel ? 'selected' : ''}>${_esc(t)}</option>`;
  el.innerHTML = `
    <div class="vce-pl" style="margin-top:0">Build</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <select id="vcb-kind" class="vce-pi" style="width:90px">${I.kinds.map(k => opt(k, k)).join('')}</select>
      <input id="vcb-caption" class="vce-pi" style="width:130px" placeholder="Caption">
      <button class="vce-ab" onclick="vcbCreate()" title="Into the selected frame, or the page">＋ Add</button>
    </div>
    <div style="font-size:9px;color:var(--text-muted);margin-bottom:6px">Goes into the selected frame (or the page) at the first free spot. Drag a function from the list onto the canvas: onto a button/CueList/slider = wire it; onto a frame or the page = a new button there (⌥ Alt: a CueList for a chaser).</div>

    <div class="vce-pl">Functions</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <select id="vcb-prof" class="vce-pi" style="width:120px" onchange="vcbSetProfile(this.value)" title="Naming profile">${
        I.profiles.map(p => opt(p.id, p.label, p.id === _vcbProfile)).join('')}</select>
      <input id="vcb-q" class="vce-pi" style="width:110px" placeholder="search" oninput="_vcbRenderFnList()">
      <select id="vcb-type" class="vce-pi" style="width:80px" onchange="_vcbRenderFnList()">
        <option value="">all types</option>${[...new Set(I.functions.map(f => f.type))].sort().map(t => opt(t, t)).join('')}</select>
      ${Object.keys(I.groups).length ? `
      <select id="vcb-grp" class="vce-pi" style="width:110px" onchange="_vcbRenderFnList()">
        <option value="">all groups</option>${Object.entries(I.groups).map(([k, v]) => opt(k, `${k} · ${v}`)).join('')}</select>
      <select id="vcb-eff" class="vce-pi" style="width:110px" onchange="_vcbRenderFnList()">
        <option value="">all effects</option>${Object.entries(I.effects).map(([k, v]) => opt(k, `${k} · ${v}`)).join('')}</select>` : ''}
    </div>
    <div id="vcb-fnlist" class="vcb-fnlist"></div>

    <div class="vce-pl">Page</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <input id="vcb-pname" class="vce-pi" style="width:120px" value="${_esc(_vcePage ? _vcePage.caption : '')}">
      <button class="vce-ab" onclick="vcbRenamePage()">✎ Rename</button>
      <button class="vce-ab" onclick="vcbMovePage(-1)" title="Move left">◀</button>
      <button class="vce-ab" onclick="vcbMovePage(1)" title="Move right">▶</button>
      <button class="vce-ab" onclick="vcbMovePage(0, true)" title="Make it page 1 — QLC+ opens on it">★ First</button>
      <button class="vce-ab" onclick="vcbDeletePage()">🗑</button>
    </div>

    <details class="vcb-more"><summary class="vce-pl" style="cursor:pointer">Label panel · screen · templates · setlist</summary>
    <div class="vce-pl">Label panel</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <select id="vcb-lsrc" class="vce-pi" style="width:150px" onchange="document.getElementById('vcb-ltext').style.display=this.value==='custom'?'':'none'">
        ${I.legend.length ? opt('legend', 'Naming legend') : ''}${opt('custom', 'My text (one per line)')}</select>
      <input id="vcb-ltitle" class="vce-pi" style="width:90px" value="Legend">
      <label style="font-size:10px;color:var(--text-muted)">cols</label>
      <input id="vcb-lcols" type="number" min="1" max="8" value="2" class="vce-pi" style="width:44px">
      <button class="vce-ab" onclick="vcbLabelPanel()">＋ Panel</button>
    </div>
    <textarea id="vcb-ltext" class="vce-pi" rows="3" style="${I.legend.length ? 'display:none;' : ''}margin-bottom:4px" placeholder="one label per line"></textarea>

    <div class="vce-pl">Screen</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;margin-bottom:4px">
      <select id="vcb-screen" class="vce-pi" style="width:150px">${I.screens.map(s => opt(s.id, s.label)).join('')}</select>
      <select id="vcb-sall" class="vce-pi" style="width:90px">${opt('page', 'this page')}${opt('all', 'all pages')}</select>
      <label style="font-size:10px;color:var(--text-muted)" title="Move and resize every widget in proportion"><input type="checkbox" id="vcb-scale"> scale</label>
      <button class="vce-ab" onclick="vcbScreen()">Apply</button>
    </div>

    <div class="vce-pl">Templates</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <input id="vcb-tname" class="vce-pi" style="width:140px" placeholder="Template name">
      <button class="vce-ab" onclick="vcbSaveTemplate()" title="This page's layout, colours and function names — no key/MIDI">💾 Save page</button>
    </div>
    <div style="margin-bottom:6px">${I.templates.length ? I.templates.map(t => `
      <div style="display:flex;gap:4px;align-items:center;font-size:10px;margin-bottom:2px">
        <span style="flex:1">${_esc(t.name)} <span style="color:var(--text-muted)">${t.widgets} widgets · ${t.functions} functions</span></span>
        <button class="vce-ab" onclick="vcbApplyTemplate('${_esc(t.name).replace(/'/g, "\\'")}')" title="Add as a new page; functions matched by name">＋ Page</button>
        <button class="vce-ab" onclick="vcbDeleteTemplate('${_esc(t.name).replace(/'/g, "\\'")}')">🗑</button>
      </div>`).join('') : '<span style="font-size:10px;color:var(--text-muted)">none saved yet</span>'}</div>

    <div class="vce-pl">Setlist CueList</div>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
      <select id="vcb-chaser" class="vce-pi" style="width:200px">${I.chasers.map(c => opt(c.id, c.name)).join('')}</select>
      <button class="vce-ab" onclick="vcbSetlist()" title="Wires the selected CueList, or adds a new CueList on this page">▶ CueList</button>
    </div>
    </details>`;
  if (moreOpen) el.querySelector('details.vcb-more').open = true;
  _vcbRenderFnList();
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

async function vcbSetlist() {
  const chaser_id = document.getElementById('vcb-chaser').value;
  if (!chaser_id) return;
  const s = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  const cl = s.length === 1 && s[0].type === 'CueList' ? s[0].id : '';
  await _vcbRun({ op: 'setlist_cuelist', chaser_id, cuelist_id: cl, page_id: _vcePage && _vcePage.id },
    cl || null, cl ? [cl] : null, d => d.wired);
}
