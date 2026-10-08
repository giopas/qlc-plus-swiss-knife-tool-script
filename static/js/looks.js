/**
 * Look and Chaser Builder tab (WORKPLAN Phase 2.3).
 *
 * Looks: tick fixture groups and palette colours → one scene per group ×
 * colour, every channel declared.  Chasers: group + pattern + colours +
 * timing (ms or BPM × note) + cut / fade, with a simulated DMX preview
 * (one colour strip per fixture, ▶ plays it at the step time).  Song
 * presets load / save a chaser recipe.  Everything added goes to the batch;
 * 🔍 Check runs the Workspace Doctor; 💾 Build writes a NEW workspace.
 */

let _lbOpts = null;              // /api/looks/options
let _lbBatch = { looks: [], chasers: [], matrices: [] };
let _lbLookCols = [];            // [{name, hex, white}] ticked for looks
let _lbChCols = [];              // ordered colours of the chaser
let _lbCustom = [];              // custom colours (both sections)
let _lbPrevTimer = null, _lbPlay = null, _lbPrev = null;

function looksInit() {
  if (!_lbOpts) _lbLoad();
}

function invalidateLooks() {
  _lbOpts = null; _lbBatch = { looks: [], chasers: [], matrices: [] };
  _lbStop();
  const b = document.getElementById('lb-body');
  if (b) b.innerHTML = '<div class="porter-placeholder">Open a workspace to build looks and chasers for its fixture groups.</div>';
  _lbSync();
  if (document.getElementById('scr-looks')?.classList.contains('active')) _lbLoad();
}

async function _lbLoad() {
  try {
    const r = await fetch('/api/looks/options');
    const d = await r.json();
    if (!r.ok) return;
    _lbOpts = d;
    _lbLookCols = []; _lbChCols = [_lbAllColours()[0]].filter(Boolean);
    _lbRender();
  } catch (e) { /* no workspace */ }
}

function _lbAllColours() {
  if (!_lbOpts) return [];
  const out = [];
  for (const k of _lbOpts.palette_order) for (const c of _lbOpts.palettes[k].colours) out.push(c);
  const seen = new Set();
  return out.concat(_lbCustom).filter(c => !seen.has(c.name) && seen.add(c.name));
}

function _lbGroupOpts(sel) {
  return _lbOpts.groups.map(g =>
    `<option value="${_esc(g.id)}" ${g.id === sel ? 'selected' : ''} ${g.supported ? '' : 'disabled'}>` +
    `${_esc(g.name)} (${g.fixtures.length}${g.supported < g.fixtures.length ? `, ${g.supported} with .qxf` : ''})</option>`).join('');
}

function _lbChip(c, on, fn) {
  return `<button class="lb-chip ${on ? 'on' : ''}" style="--c:${c.hex}" title="${_esc(c.hex)}"
            onclick="${fn}('${_esc(c.name).replace(/'/g, "\\'")}')"><i></i><span data-i18n-ctx="colour">${_esc(c.name)}</span></button>`;
}

// moving-head position (v2.5): a name from the list, or pan / tilt in percent (50 = centre)
function _lbPosHtml(id, onchange) {
  return `<label>Position <select id="${id}" class="filter-input" onchange="_lbPosForm('${id}'); ${onchange}">
      <option value="">— as it is —</option>${_lbOpts.positions.map(p => `<option value="${_esc(p.name)}">${_esc(p.name)} (pan ${p.pan} · tilt ${p.tilt} %)</option>`).join('')}
      <option value="custom">custom…</option></select></label>
    <span id="${id}-c" class="lb-poscustom" hidden>
      pan <input type="number" id="${id}-pan" class="filter-input rr-num" min="0" max="100" value="50" oninput="${onchange}"> %
      tilt <input type="number" id="${id}-tilt" class="filter-input rr-num" min="0" max="100" value="50" oninput="${onchange}"> %</span>`;
}
function _lbPosForm(id) { const c = _v(id + '-c'); if (c) c.hidden = _v(id).value !== 'custom'; }
function _lbPosVal(id) {
  const el = _v(id); if (!el || !el.value) return null;
  if (el.value === 'custom') return { pan: +_v(id + '-pan').value, tilt: +_v(id + '-tilt').value };
  return el.value;
}
function _lbPosName(p) { return !p ? '' : (typeof p === 'string' ? p : `pan ${p.pan}% tilt ${p.tilt}%`); }

// Inspector tabs (2.6): Looks and Chasers one at a time, To build always visible
let _lbTab = 'looks';
function looksTab(t) {
  _lbTab = t;
  document.querySelectorAll('#lb-body [data-lbtab]').forEach(b => b.classList.toggle('active', b.dataset.lbtab === t));
  document.querySelectorAll('#lb-body [data-lbpane]').forEach(p => { p.hidden = p.dataset.lbpane !== t; });
}

function _lbRender() {
  const el = document.getElementById('lb-body');
  if (!el || !_lbOpts) return;
  const pal = _lbOpts.palette_order.map(k => [k, _lbOpts.palettes[k]]);
  const hasPick = _lbLookCols.map(c => c.name);
  el.innerHTML = `
  <div class="lb-cols">
   <div class="lb-left">
    <div class="lb-tabs" role="tablist">
      <button class="subtab-btn${_lbTab === 'looks' ? ' active' : ''}" data-lbtab="looks" onclick="looksTab('looks')"
              title="A look = a fixture group in one colour: one scene each">🎨 Looks</button>
      <button class="subtab-btn${_lbTab === 'chaser' ? ' active' : ''}" data-lbtab="chaser" onclick="looksTab('chaser')"
              title="A chaser = a pattern across a fixture group, with BPM timing">🔁 Chasers</button>
      <button class="subtab-btn${_lbTab === 'matrix' ? ' active' : ''}" data-lbtab="matrix" onclick="looksTab('matrix')"
              title="An RGB-matrix pattern across the pixels of LED / pixel bars">▦ Matrix</button>
      <span class="lb-tabs-note">both go into <b>To build</b> on the right</span>
    </div>
    <div class="lb-card" data-lbpane="looks"${_lbTab === 'looks' ? '' : ' hidden'}>
      <h3>Looks <span class="p-desc">fixture group × palette — one scene each, every channel declared</span></h3>
      <div class="lb-groups">${_lbOpts.groups.map(g => `
        <label class="${g.supported ? '' : 'lb-dis'}"><input type="checkbox" class="lb-lg" value="${_esc(g.id)}"
          ${g.supported ? '' : 'disabled'} onchange="_lbLookPreview()"> <span data-i18n="off">${_esc(g.name)}</span> <span class="lb-n">${g.fixtures.length}</span></label>`).join('')}
      </div>
      ${pal.map(([id, p]) => `<div class="lb-pal"><span class="lb-pal-h">${_esc(p.label)}</span>
          ${p.colours.map(c => _lbChip(c, hasPick.includes(c.name), 'looksToggleLookColour')).join('')}
          <button class="btn btn-surface btn-sm" onclick="looksPalette('${id}')">all</button></div>`).join('')}
      <div class="lb-pal"><span class="lb-pal-h">Custom</span>
        ${_lbCustom.map(c => _lbChip(c, hasPick.includes(c.name), 'looksToggleLookColour')).join('')}
        <input type="color" id="lb-cust-hex" value="#ff8800" title="Pick a colour">
        <input class="filter-input lb-cname" id="lb-cust-name" placeholder="name">
        <button class="btn btn-surface btn-sm" onclick="looksAddCustom()">+ add</button></div>
      <div class="lb-row">
        ${_lbPosHtml('lb-lpos', '_lbLookPreview()')}
        <input class="filter-input lb-cname" id="lb-palname" placeholder="palette name">
        <button class="btn btn-surface btn-sm" onclick="looksSavePalette()" title="Keep the ticked colours as a palette of your own">★ Save ticked as palette</button>
        <button class="btn btn-surface btn-sm" onclick="looksDeletePalette()" title="Delete the palette named in the box (yours only)">🗑</button>
      </div>
      <div class="lb-row">
        <label>Level <input type="range" id="lb-level" min="5" max="100" step="5" value="100"
          oninput="document.getElementById('lb-level-v').textContent=this.value+' %'; _lbLookPreview()"></label>
        <span id="lb-level-v">100 %</span>
        <div class="spacer"></div>
        <button class="btn btn-surface" onclick="looksAddLooks()">+ Add looks</button>
      </div>
      <div id="lb-look-prev" class="lb-prev"></div>
    </div>

    <div class="lb-card" data-lbpane="chaser"${_lbTab === 'chaser' ? '' : ' hidden'}>
      <h3>Chaser <span class="p-desc">a pattern across a fixture group</span></h3>
      <div class="lb-row">
        <label>Song preset <select id="lb-preset" class="filter-input" onchange="looksLoadPreset(this.value)">
          <option value="">—</option>${_lbOpts.presets.map((p, i) =>
            `<option value="${i}">${p.builtin ? '' : '★ '}${_esc(p.name)}</option>`).join('')}</select></label>
        <input class="filter-input" id="lb-pname" placeholder="save as…">
        <button class="btn btn-surface btn-sm" onclick="looksSavePreset()">💾 Save preset</button>
        <button class="btn btn-surface btn-sm" onclick="looksDeletePreset()" title="Delete the selected preset (yours only)">🗑</button>
      </div>
      <div class="lb-grid">
        <label>Group <select id="lb-cg" class="filter-input" onchange="_lbChPreview()">${_lbGroupOpts(
          (_lbOpts.groups.find(g => g.id !== 'all' && g.supported) || _lbOpts.groups[0]).id)}</select></label>
        <label>Pattern <select id="lb-pat" class="filter-input" onchange="_lbChForm()">${_lbOpts.patterns.map(p =>
          `<option value="${p.id}" ${p.id === 'chase' ? 'selected' : ''}>${_esc(p.label)}</option>`).join('')}</select></label>
        <label>Steps <input type="number" id="lb-steps" class="filter-input rr-num" min="1" max="256" placeholder="auto" oninput="_lbChPreview()"></label>
        <label class="lb-rnd">Seed <input type="number" id="lb-seed" class="filter-input rr-num" value="1" oninput="_lbChPreview()"></label>
        <label class="lb-rnd">On per step <input type="number" id="lb-on" class="filter-input rr-num" min="1" value="1" oninput="_lbChPreview()"></label>
        <label class="lb-alt">Split <select id="lb-split" class="filter-input" onchange="_lbChPreview()">
          <option value="halves">left / right halves</option><option value="odd_even">odd / even</option></select></label>
        <label>Timing <select id="lb-tm" class="filter-input" onchange="_lbChForm()">
          <option value="bpm">BPM + note</option><option value="ms">ms per step</option></select></label>
        <label class="lb-bpm">BPM <input type="number" id="lb-bpm" class="filter-input rr-num" min="20" max="400" value="120" oninput="_lbChPreview()"></label>
        <label class="lb-bpm">Note <select id="lb-note" class="filter-input" onchange="_lbChPreview()">${_lbOpts.notes.map(n =>
          `<option ${n === '1/4' ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
        <label class="lb-bpm" title="The chaser follows the BPM of QLC+ itself (speed dial / tap) instead of a fixed time: steps are stored in beats">
          <input type="checkbox" id="lb-beats" onchange="_lbChPreview()"> follow the QLC+ tempo (beats)</label>
        <label class="lb-ms">Step ms <input type="number" id="lb-ms" class="filter-input rr-num" min="20" value="500" oninput="_lbChPreview()"></label>
        ${_lbPosHtml('lb-cpos', '_lbChPreview()')}
        <label>Fade <select id="lb-fade" class="filter-input" onchange="_lbChForm()">
          <option value="cut">cut</option><option value="fade">fade</option></select></label>
        <label class="lb-fd">% of step <input type="number" id="lb-fpct" class="filter-input rr-num" min="0" max="100" value="100" oninput="_lbChPreview()"></label>
        <label>Colours <select id="lb-cmode" class="filter-input" onchange="_lbChPreview()">
          <option value="step">change per step</option><option value="fixture">one per fixture</option></select></label>
        <label>Type <select id="lb-kind" class="filter-input">
          <option value="dynamic">dynamic</option><option value="pulse">pulse</option>
          <option value="movement">movement</option><option value="fx">special FX</option></select></label>
        <label><input type="checkbox" id="lb-bg" onchange="_lbChPreview()"> Background
          <select id="lb-bgc" class="filter-input" onchange="_lbChPreview()">${_lbAllColours().map(c =>
            `<option data-i18n-ctx="colour" ${c.name === 'Blue' ? 'selected' : ''}>${_esc(c.name)}</option>`).join('')}</select>
          <input type="number" id="lb-bgl" class="filter-input rr-num" min="5" max="100" value="30" oninput="_lbChPreview()"> %</label>
      </div>
      <div class="lb-pal"><span class="lb-pal-h">Colours</span><span id="lb-chcols"></span></div>
      <div class="lb-pal lb-small">${_lbAllColours().map(c => _lbChip(c, false, 'looksAddChColour')).join('')}</div>
      <div class="lb-row">
        <input class="filter-input" id="lb-cname" placeholder="name (default: pattern + colours)">
        <div class="spacer"></div>
        <button class="btn btn-surface btn-sm" id="lb-playbtn" onclick="looksPlay()">▶ Play</button>
        <button class="btn btn-surface" onclick="looksAddChaser()">+ Add chaser</button>
      </div>
      <div id="lb-ch-prev" class="lb-prev"></div>
    </div>

    <div class="lb-card" data-lbpane="matrix"${_lbTab === 'matrix' ? '' : ' hidden'}>
      <h3>Matrix pattern <span class="p-desc">an RGB-matrix pattern across the pixels of LED / pixel bars</span></h3>
      ${_lbOpts.pixel_bars.length ? `
      <div class="lb-groups">${_lbOpts.pixel_bars.map(b => `
        <label><input type="checkbox" class="lb-mb" value="${_esc(b.id)}" checked> ${_esc(b.name)} <span class="lb-n">${b.heads} pixels</span></label>`).join('')}
      </div>
      <div class="lb-grid">
        <label>Pattern <select id="lb-mpat" class="filter-input" onchange="_lbMatrixForm()">${_lbOpts.matrix_patterns.map(m =>
          `<option value="${_esc(m.name)}">${_esc(m.name)}</option>`).join('')}</select></label>
        <label>Colour 1 <input type="color" id="lb-mc1"></label>
        <label>Colour 2 <input type="color" id="lb-mc2"></label>
        <label>Speed <input type="number" id="lb-mdur" class="filter-input rr-num" min="20" max="600000" step="10"> ms</label>
        <label>Name <input class="filter-input" id="lb-mname" placeholder="default: bars + pattern"></label>
      </div>
      <p class="p-desc">The bars in a row make one grid: the pattern runs across the pixels (and from bar to bar when you tick several).
        A bar with a master dimmer gets it opened by the same button.</p>
      <div class="lb-row"><div class="spacer"></div><button class="btn btn-surface" onclick="looksAddMatrix()">+ Add matrix pattern</button></div>`
      : '<div class="porter-placeholder">No pixel bar in this show — a pixel bar is a fixture whose mode has several heads (pixels) in its definition.</div>'}
    </div>
   </div>

   <div class="lb-right">
    <div class="lb-card">
      <h3>To build</h3>
      <div id="lb-batch"></div>
      <div class="lb-grid">
        <label>Names <select id="lb-nom" class="filter-input">${_lbOpts.nomenclature.map(p =>
          `<option value="${_esc(p.id)}">${_esc(p.label)}</option>`).join('')}</select></label>
        <label>Function folder <input class="filter-input" id="lb-folder" value="Look Builder"></label>
        <label><input type="checkbox" id="lb-vc" checked> Buttons on a new VC page
          <input class="filter-input" id="lb-vcname" value="Looks"></label>
      </div>
      <div class="lb-row"><div class="spacer"></div><button class="btn btn-surface" onclick="looksCheck()">🔍 Check</button></div>
      <div id="lb-check"></div>
    </div>
   </div>
  </div>`;
  _lbChForm();
  _lbRenderChCols();
  _lbRenderBatch();
  if (_lbOpts.pixel_bars.length) _lbMatrixForm();
}

function _lbMatrixForm() {
  const m = _lbOpts.matrix_patterns.find(x => x.name === _v('lb-mpat').value) || _lbOpts.matrix_patterns[0];
  _v('lb-mc1').value = (m.colours[0] || '#ff0000').toLowerCase();
  _v('lb-mc2').value = (m.colours[1] || m.colours[0] || '#0000ff').toLowerCase();
  _v('lb-mc2').closest('label').style.display = m.colours.length > 1 ? '' : 'none';
  _v('lb-mdur').value = m.duration;
}

function looksAddMatrix() {
  const ids = [...document.querySelectorAll('.lb-mb:checked')].map(x => x.value);
  if (!ids.length) { setStatus('Tick at least one pixel bar.', 'warn'); return; }
  const m = _lbOpts.matrix_patterns.find(x => x.name === _v('lb-mpat').value);
  const cols = [_v('lb-mc1').value];
  if (m.colours.length > 1) cols.push(_v('lb-mc2').value);
  const spec = { fixtures: ids, pattern: m.name, colours: cols.map(h => ({ name: h.toUpperCase(), hex: h })), duration: +_v('lb-mdur').value };
  const nm = (_v('lb-mname').value || '').trim(); if (nm) spec.name = nm;
  _lbBatch.matrices.push(spec);
  _lbRenderBatch();
  setStatus('Matrix pattern added.', 'ok');
}

async function looksSavePalette() {
  const name = (_v('lb-palname').value || '').trim();
  if (!name) { setStatus('Type a name for the palette.', 'warn'); return; }
  if (!_lbLookCols.length) { setStatus('Tick the colours to keep first.', 'warn'); return; }
  const r = await fetch('/api/looks/palettes', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, colours: _lbLookCols }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.palettes = d.palettes; _lbOpts.palette_order = d.palette_order;
  _lbGroupsTicked = [...document.querySelectorAll('.lb-lg:checked')].map(x => x.value);
  _lbRender(); _lbRestoreLooks();
  setStatus(`Palette '${name}' saved in ~/.qlc_swiss_knife/look_palettes.json.`, 'ok');
}

async function looksDeletePalette() {
  const name = (_v('lb-palname').value || '').trim();
  if (!name) { setStatus('Type the name of your palette to delete.', 'warn'); return; }
  const r = await fetch('/api/looks/palettes/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.palettes = d.palettes; _lbOpts.palette_order = d.palette_order;
  _lbRender();
  setStatus(`Palette '${name}' deleted.`, 'ok');
}

// ── looks ──────────────────────────────────────────────────────────────────
function _lbColour(name) { return _lbAllColours().find(c => c.name === name); }

function looksToggleLookColour(name) {
  const i = _lbLookCols.findIndex(c => c.name === name);
  if (i >= 0) _lbLookCols.splice(i, 1); else _lbLookCols.push(_lbColour(name));
  _lbRender(); _lbRestoreLooks();
}

function looksPalette(id) {
  for (const c of _lbOpts.palettes[id].colours) if (!_lbLookCols.some(x => x.name === c.name)) _lbLookCols.push(c);
  _lbRender(); _lbRestoreLooks();
}

let _lbGroupsTicked = [];
function _lbRestoreLooks() {
  document.querySelectorAll('.lb-lg').forEach(x => { x.checked = _lbGroupsTicked.includes(x.value); });
  _lbLookPreview();
}

function looksAddCustom() {
  const hex = document.getElementById('lb-cust-hex').value.toUpperCase();
  const name = (document.getElementById('lb-cust-name').value || '').trim() || hex;
  if (_lbAllColours().some(c => c.name.toLowerCase() === name.toLowerCase())) { setStatus(`'${name}' already exists.`, 'warn'); return; }
  const c = { name, hex };
  _lbCustom.push(c); _lbLookCols.push(c);
  _lbGroupsTicked = [...document.querySelectorAll('.lb-lg:checked')].map(x => x.value);
  _lbRender(); _lbRestoreLooks();
}

function _lbLookPreview() {
  _lbGroupsTicked = [...document.querySelectorAll('.lb-lg:checked')].map(x => x.value);
  clearTimeout(_lbPrevTimer);
  _lbPrevTimer = setTimeout(async () => {
    const el = document.getElementById('lb-look-prev');
    if (!el) return;
    if (!_lbGroupsTicked.length || !_lbLookCols.length) {
      el.innerHTML = `<div class="porter-placeholder">${_lbGroupsTicked.length ? 'Tick' : 'Tick fixture groups and'} colours to preview the looks.</div>`;
      return;
    }
    const g = _lbGroupsTicked[0];
    const r = await fetch('/api/looks/preview-look', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group: g, colours: _lbLookCols, level: +document.getElementById('lb-level').value / 100, position: _lbPosVal('lb-lpos') }) });
    const d = await r.json();
    if (!r.ok) { el.innerHTML = `<div class="porter-warn">${_esc(d.error)}</div>`; return; }
    const gn = _lbOpts.groups.find(x => x.id === g).name;
    el.innerHTML = `<div class="lb-cap">Simulated output — ${_esc(gn)}${_lbGroupsTicked.length > 1 ? ` (+${_lbGroupsTicked.length - 1} more group(s))` : ''}:
        ${_lbGroupsTicked.length * _lbLookCols.length} look(s)</div>
      <table class="lb-strip"><tr><th></th>${d.fixtures.map(f => `<th title="${_esc(f)}">${_esc(f)}</th>`).join('')}</tr>
      ${d.looks.map(l => `<tr><td data-i18n-ctx="colour">${_esc(l.colour.name)}</td>${l.cells.map(c =>
        `<td><span class="lb-cell" style="background:${c || 'transparent'}" title="${c || 'no .qxf — skipped'}">${c ? '' : '–'}</span></td>`).join('')}</tr>`).join('')}</table>`;
  }, 150);
}

function looksAddLooks() {
  const gs = [...document.querySelectorAll('.lb-lg:checked')].map(x => x.value);
  if (!gs.length || !_lbLookCols.length) { setStatus('Tick at least one group and one colour.', 'warn'); return; }
  const level = +document.getElementById('lb-level').value / 100;
  const position = _lbPosVal('lb-lpos');
  for (const g of gs) _lbBatch.looks.push({ group: g, colours: _lbLookCols.map(c => ({ ...c })), level, ...(position ? { position } : {}) });
  _lbRenderBatch();
  setStatus(`${gs.length * _lbLookCols.length} look(s) added.`, 'ok');
}

// ── chaser ─────────────────────────────────────────────────────────────────
function _v(id) { return document.getElementById(id); }

function _lbChForm() {
  const pat = _v('lb-pat').value, tm = _v('lb-tm').value, fade = _v('lb-fade').value;
  document.querySelectorAll('.lb-rnd').forEach(x => x.style.display = pat === 'random' ? '' : 'none');
  document.querySelectorAll('.lb-alt').forEach(x => x.style.display = pat === 'alternate' ? '' : 'none');
  document.querySelectorAll('.lb-bpm').forEach(x => x.style.display = tm === 'bpm' ? '' : 'none');
  if (_v('lb-beats') && tm !== 'bpm') _v('lb-beats').checked = false;
  document.querySelectorAll('.lb-ms').forEach(x => x.style.display = tm === 'ms' ? '' : 'none');
  document.querySelectorAll('.lb-fd').forEach(x => x.style.display = fade === 'fade' ? '' : 'none');
  _lbChPreview();
}

function _lbRenderChCols() {
  const el = _v('lb-chcols');
  if (!el) return;
  el.innerHTML = _lbChCols.length ? _lbChCols.map((c, i) =>
    `<button class="lb-chip on" style="--c:${c.hex}" onclick="looksRemoveChColour(${i})" title="remove"><i></i><span data-i18n-ctx="colour">${_esc(c.name)}</span> ✕</button>`).join('')
    : '<span class="p-desc">click colours below (in order)</span>';
}

function looksAddChColour(name) { _lbChCols.push(_lbColour(name)); _lbRenderChCols(); _lbChPreview(); }
function looksRemoveChColour(i) { _lbChCols.splice(i, 1); _lbRenderChCols(); _lbChPreview(); }

function _lbSpec() {
  const s = {
    group: _v('lb-cg').value, pattern: _v('lb-pat').value, colours: _lbChCols.map(c => ({ ...c })),
    colour_mode: _v('lb-cmode').value, fade: _v('lb-fade').value, kind: _v('lb-kind').value,
  };
  const steps = parseInt(_v('lb-steps').value, 10);
  if (steps) s.steps = steps;
  if (_v('lb-tm').value === 'bpm') {
    s.bpm = +_v('lb-bpm').value; s.note = _v('lb-note').value;
    if (_v('lb-beats').checked) s.tempo = 'beats';
  }
  const pos = _lbPosVal('lb-cpos'); if (pos) s.position = pos;
  else s.step_ms = +_v('lb-ms').value;
  if (s.fade === 'fade') s.fade_pct = +_v('lb-fpct').value;
  if (s.pattern === 'random') { s.seed = +_v('lb-seed').value || 0; s.on_count = +_v('lb-on').value || 1; }
  if (s.pattern === 'alternate') s.split = _v('lb-split').value;
  if (_v('lb-bg').checked) s.background = { colour: _lbColour(_v('lb-bgc').value), level: +_v('lb-bgl').value / 100 };
  const name = (_v('lb-cname').value || '').trim();
  if (name) s.name = name;
  return s;
}

function _lbChPreview() {
  clearTimeout(_lbPrevTimer);
  _lbPrevTimer = setTimeout(async () => {
    const el = _v('lb-ch-prev');
    if (!el || !_lbOpts) return;
    if (!_lbChCols.length) { el.innerHTML = '<div class="porter-placeholder">Pick at least one colour.</div>'; return; }
    const r = await fetch('/api/looks/preview-chaser', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_lbSpec()) });
    const d = await r.json();
    if (!r.ok) { el.innerHTML = `<div class="porter-warn">${_esc(d.error)}</div>`; return; }
    _lbPrev = d;
    el.innerHTML = `<div class="lb-cap">Simulated output — ${d.steps} step(s) × ${d.step_ms} ms${d.fade_ms ? `, fade ${d.fade_ms} ms` : ', cut'}
        ${d.skipped.length ? ` · skipped (no .qxf): ${_esc(d.skipped.join(', '))}` : ''}</div>
      <table class="lb-strip"><tr><th></th>${Array.from({ length: d.steps }, (_, i) => `<th class="lb-st" data-s="${i}">${i + 1}</th>`).join('')}</tr>
      ${d.fixtures.map(f => `<tr><td>${_esc(f.name)}</td>${f.cells.map((c, i) =>
        `<td class="lb-st" data-s="${i}"><span class="lb-cell" style="background:${c}"></span></td>`).join('')}</tr>`).join('')}</table>
      ${d.notes.length ? `<details><summary>${d.notes.length} note(s)</summary>${d.notes.map(n => `<div class="p-desc">${_esc(n)}</div>`).join('')}</details>` : ''}`;
    if (_lbPlay) { _lbStop(); looksPlay(); }
  }, 200);
}

function _lbStop() {
  if (_lbPlay) clearInterval(_lbPlay.t);
  _lbPlay = null;
  document.querySelectorAll('.lb-st.cur').forEach(x => x.classList.remove('cur'));
  const b = _v('lb-playbtn'); if (b) b.textContent = '▶ Play';
}

function looksPlay() {
  if (_lbPlay) { _lbStop(); return; }
  if (!_lbPrev || !_lbPrev.steps) return;
  _lbPlay = { k: 0 };
  const tick = () => {
    document.querySelectorAll('.lb-st.cur').forEach(x => x.classList.remove('cur'));
    document.querySelectorAll(`.lb-st[data-s="${_lbPlay.k}"]`).forEach(x => x.classList.add('cur'));
    _lbPlay.k = (_lbPlay.k + 1) % _lbPrev.steps;
  };
  tick();
  _lbPlay.t = setInterval(tick, Math.max(40, _lbPrev.step_ms));
  _v('lb-playbtn').textContent = '■ Stop';
}

function looksAddChaser() {
  if (!_lbChCols.length) { setStatus('Pick at least one colour.', 'warn'); return; }
  _lbBatch.chasers.push(_lbSpec());
  _lbRenderBatch();
  setStatus('Chaser added.', 'ok');
}

function looksLoadPreset(i) {
  if (i === '') return;
  const p = _lbOpts.presets[+i];
  const set = (id, v) => { if (v !== undefined && v !== null) _v(id).value = v; };
  set('lb-pat', p.pattern || 'chase');
  _v('lb-steps').value = p.steps || '';
  if (p.bpm) { _v('lb-tm').value = 'bpm'; set('lb-bpm', p.bpm); set('lb-note', p.note || '1/4'); }
  else { _v('lb-tm').value = 'ms'; set('lb-ms', p.step_ms || 500); }
  _v('lb-beats').checked = p.tempo === 'beats';
  set('lb-cpos', typeof p.position === 'string' ? p.position : ''); _lbPosForm('lb-cpos');
  set('lb-fade', p.fade || 'cut'); set('lb-fpct', p.fade_pct ?? 100);
  set('lb-cmode', p.colour_mode || 'step'); set('lb-kind', p.kind || 'dynamic');
  set('lb-seed', p.seed ?? 1); set('lb-on', p.on_count ?? 1); set('lb-split', p.split || 'halves');
  _lbChCols = (p.colours || []).map(c => typeof c === 'string' ? _lbColour(c) : (_lbColour(c.name) || c)).filter(Boolean);
  const bg = p.background;
  _v('lb-bg').checked = !!bg;
  if (bg) { set('lb-bgc', typeof bg.colour === 'string' ? bg.colour : bg.colour?.name); set('lb-bgl', Math.round((bg.level ?? 0.3) * 100)); }
  _v('lb-cname').value = '';
  _v('lb-pname').value = p.builtin ? '' : p.name;
  _lbRenderChCols();
  _lbChForm();
}

async function looksSavePreset() {
  const name = (_v('lb-pname').value || '').trim();
  if (!name) { setStatus('Type a name for the preset.', 'warn'); return; }
  const s = _lbSpec();
  delete s.group; delete s.name;
  const r = await fetch('/api/looks/presets', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...s, name }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.presets = d.presets;
  const sel = _v('lb-preset');
  sel.innerHTML = '<option value="">—</option>' + d.presets.map((p, i) =>
    `<option value="${i}" ${p.name === name ? 'selected' : ''}>${p.builtin ? '' : '★ '}${_esc(p.name)}</option>`).join('');
  setStatus(`Preset '${name}' saved.`, 'ok');
}

async function looksDeletePreset() {
  const i = _v('lb-preset').value;
  if (i === '') return;
  const p = _lbOpts.presets[+i];
  if (p.builtin) { setStatus('Built-in presets cannot be deleted.', 'warn'); return; }
  const r = await fetch('/api/looks/presets/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: p.name }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.presets = d.presets;
  _v('lb-preset').innerHTML = '<option value="">—</option>' + d.presets.map((q, k) =>
    `<option value="${k}">${q.builtin ? '' : '★ '}${_esc(q.name)}</option>`).join('');
  setStatus(`Preset '${p.name}' deleted.`, 'ok');
}

// ── batch, check, build ────────────────────────────────────────────────────
function _lbGName(id) { return (_lbOpts.groups.find(g => g.id === id) || {}).name || id; }

function _lbRenderBatch() {
  const el = _v('lb-batch');
  if (!el) { _lbSync(); return; }
  const L = _lbBatch.looks.map((l, i) => `<div class="lb-item">
      <span>🎨 ${_esc(_lbGName(l.group))} × ${l.colours.map(c => `<i class="lb-dot" style="background:${c.hex}"></i>${_esc(c.name)}`).join(' ')}
        ${l.level < 1 ? ` @ ${Math.round(l.level * 100)} %` : ''}${l.position ? ` · ${_esc(_lbPosName(l.position))}` : ''}</span>
      <button class="btn btn-surface btn-sm" onclick="looksRemove('looks', ${i})">✕</button></div>`);
  const M = _lbBatch.matrices.map((m, i) => `<div class="lb-item">
      <span>▦ ${_esc(m.name || m.pattern)} — ${_esc(m.pattern)} on ${m.fixtures.map(id => _esc((_lbOpts.pixel_bars.find(b => b.id === id) || {}).name || id)).join(', ')},
        ${m.duration} ms ${m.colours.map(x => `<i class="lb-dot" style="background:${x.hex}"></i>`).join('')}</span>
      <button class="btn btn-surface btn-sm" onclick="looksRemove('matrices', ${i})">✕</button></div>`);
  const C = _lbBatch.chasers.map((c, i) => {
    const pat = (_lbOpts.patterns.find(p => p.id === c.pattern) || {}).label;
    const t = c.bpm ? (c.tempo === 'beats' ? `${c.note} beat (QLC+ tempo)` : `${c.bpm} BPM ${c.note}`) : `${c.step_ms} ms`;
    return `<div class="lb-item">
      <span>🔁 ${_esc(c.name || pat)} — ${_esc(_lbGName(c.group))}, ${_esc(pat)}, ${t}${c.position ? `, ${_esc(_lbPosName(c.position))}` : ''}, ${c.fade === 'fade' ? `fade ${c.fade_pct}%` : 'cut'}
        ${c.colours.map(x => `<i class="lb-dot" style="background:${x.hex}"></i>`).join('')}</span>
      <button class="btn btn-surface btn-sm" onclick="looksRemove('chasers', ${i})">✕</button></div>`;
  });
  el.innerHTML = (L.concat(C, M).join('')) || '<div class="porter-placeholder">Add looks or chasers on the left.</div>';
  _v('lb-check').innerHTML = '';
  _lbSync();
}

function looksRemove(kind, i) { _lbBatch[kind].splice(i, 1); _lbRenderBatch(); }

function _lbSync() {
  const s = _v('lb-summary'), b = _v('lb-go');
  const nl = _lbBatch.looks.reduce((a, l) => a + l.colours.length, 0), nc = _lbBatch.chasers.length, nm = _lbBatch.matrices.length;
  if (s) s.innerHTML = _lbOpts ? `<span class="doc-chip">${nl} look(s)</span><span class="doc-chip">${nc} chaser(s)</span>${nm ? `<span class="doc-chip">${nm} matrix</span>` : ''}` : '';
  if (b) b.disabled = !(nl || nc || nm);
  const x = _v('lb-export'); if (x) x.disabled = !(nl || nc || nm);
  if (typeof setOutcome === 'function') setOutcome('looks', nl || nc || nm
    ? [nl ? `+${nl} look${nl > 1 ? 's' : ''}` : '', nc ? `+${nc} chaser${nc > 1 ? 's' : ''}` : '', nm ? `+${nm} matrix pattern${nm > 1 ? 's' : ''}` : ''].filter(Boolean)
    : 'nothing yet — add looks, chasers or matrix patterns to the batch', '', nl || nc || nm ? 'Apply will add' : 'Apply will do');
}

function _lbPlan() {
  return {
    looks: _lbBatch.looks, chasers: _lbBatch.chasers, matrices: _lbBatch.matrices,
    nomenclature: _v('lb-nom')?.value || 'plain', folder: _v('lb-folder')?.value || '',
    vc_page: _v('lb-vc')?.checked ? (_v('lb-vcname').value || 'Looks') : '',
  };
}

async function looksCheck() {
  const el = _v('lb-check');
  setStatus('Checking…', 'info');
  const r = await fetch('/api/looks/check', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_lbPlan()) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Check failed.', 'error'); return; }
  const c = d.created, doc = d.doctor;
  el.innerHTML = `<p><b>${c.looks}</b> look(s), <b>${c.chasers}</b> chaser(s) with <b>${c.step_scenes}</b> step scene(s),
      ${c.matrices ? `<b>${c.matrices}</b> matrix pattern(s), ` : ''}<b>${c.buttons}</b> button(s).</p>
    <p>Doctor on the result: ${doc.total_errors} error(s), ${doc.total_warnings} warning(s)
      ${doc.new_errors.length || doc.new_warnings.length ? `— <b>new</b>: ${doc.new_errors.length} error(s), ${doc.new_warnings.length} warning(s)` : '— nothing new'}.</p>
    ${d.blocked ? '<p class="porter-warn">⛔ The result has new Doctor errors — it will not be exported.</p>' : ''}
    ${[...doc.new_errors, ...doc.new_warnings].slice(0, 20).map(x => `<div class="porter-warn">⚠ ${_esc(x)}</div>`).join('')}
    <details open><summary>Changes (${d.log.length})</summary><div class="rr-log">${d.log.map(x => `<div>${_esc(x)}</div>`).join('')}</div></details>
    ${d.notes.length ? `<details><summary>Notes (${d.notes.length})</summary><div class="rr-log">${d.notes.map(x => `<div>${_esc(x)}</div>`).join('')}</div></details>` : ''}`;
  setStatus('Check done.', 'ok');
}

async function looksBuild() {
  setStatus('Building…', 'info');
  try {
    const r = await fetch('/api/looks/build', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_lbPlan()) });
    if (!r.ok) {
      const d = await r.json();
      setStatus((d.error || 'Failed.') + (d.findings ? ' ' + d.findings.slice(0, 3).join(' | ') : ''), 'error');
      return;
    }
    const name = r.headers.get('X-Suggested-Filename') || 'workspace_v2.qxw';
    const blob = await r.blob();
    const saved = await saveFileWithPicker(blob, name,
      [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }], 'Save workspace with the new looks');
    if (!saved) { setStatus('Not saved.', 'info'); return; }
    const full = saveFileWithPicker.lastPath;
    let msg = `Saved ${full || saved}.`;
    if (full) {
      const rr = await fetch('/api/looks/save-report', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qxw_path: full }) });
      const d = await rr.json();
      msg += rr.ok ? ` Report: ${d.name}.` : ' Report not saved.';
    }
    setStatus(msg + ' A separate copy — the show in progress is unchanged.', 'ok');
  } catch (e) {
    setStatus('Error: ' + e.message, 'error');
  }
}
