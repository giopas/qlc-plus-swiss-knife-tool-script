/**
 * Look and Chaser Builder (3.3.0: aligned with the QLC+ 5.3 Show Wizard).
 *
 * Three columns.  Groups: a card per fixture group with what it can do (read
 * from the fixture definitions) and its role.  Families, as in the wizard:
 * Colour, Intensity, Movement, Matrix; each effect is a card that says what
 * it makes and on which groups, greyed with the reason when no picked group
 * can do it.  "Start from" pre-ticks them the way the wizard does for a show
 * type.  Will add: a stage seen from above, the counts (from the Doctor
 * check, debounced), where the buttons go (a page per group, one page, none).
 *
 * A chaser card opens the effect panel: recipe, pattern, colours, speed and
 * fade, a step preview with ▶ Play, and every expert setting under More.
 * Every look declares every channel (Swiss Knife's rule).
 */

let _lbOpts = null;              // /api/looks/options
let _lbSel = new Set();          // picked groups
let _lbRole = {};                // group id → role
let _lbFx = new Map();           // effect id → Set of group ids it goes to
let _lbCols = [];                // [{name, hex}] ticked colours
let _lbCustom = [];              // custom colours
let _lbGobos = {};               // group id → [gobo numbers]
let _lbPlace = 'Centre';         // where the moving heads of the looks aim
let _lbEdits = {};               // effect id → chaser recipe (from the effect panel)
let _lbOwn = [];                 // chasers built in the effect panel ("+ New chaser")
let _lbBars = [];                // pixel-bar matrices (as before 3.3.0)
let _lbType = 'Custom';
let _lbEditing = null;           // effect id open in the panel, or 'new'
let _lbChCols = [];              // ordered colours of the chaser in the panel
let _lbPrevTimer = null, _lbPlay = null, _lbPrev = null, _lbCheckTimer = null, _lbLast = null;
let _lbBatch = { looks: [], chasers: [], matrices: [] };   // kept for older callers

const LB_WHITE = { name: 'White', hex: '#FFFFFF' };
const LB_RAINBOW = ['Red', 'Orange', 'Yellow', 'Green', 'Cyan', 'Blue', 'Magenta'];

// The families and their effects.  need: what a group must be able to do;
// fam: the role family ("Start from" gives an effect to the groups whose role has it).
const LB_FAM = [
  { id: 'colour', name: 'Colour', dot: '#a78bfa', items: [
    { id: 'colour', name: 'Colour looks', need: g => g.supported > 0, fam: 'colour', why: 'needs a fixture definition' },
    { id: 'rainbow', name: 'Rainbow', need: g => _lbHas(g, 'mix') || _lbHas(g, 'wheel'), fam: 'chase', chaser: true, why: 'needs colour' },
    { id: 'split', name: 'Split colour', need: g => _lbHas(g, 'mix') || _lbHas(g, 'wheel'), fam: 'chase', chaser: true, why: 'needs colour' },
    { id: 'gobo', name: 'Gobo looks', need: g => _lbHas(g, 'gobo'), fam: 'gobo', isNew: true, why: 'needs a gobo wheel' },
    { id: 'ambient', name: 'Ambient loop', need: g => _lbHas(g, 'mix') && !_lbHas(g, 'moves'), fam: 'colour', chaser: true,
      why: 'needs colour mixing on lights that don’t move' },
  ] },
  { id: 'intensity', name: 'Intensity', dot: '#f87171', items: [
    { id: 'levels', name: 'Full · Half · Off', need: g => g.supported > 0, fam: 'levels', why: 'needs a fixture definition' },
    { id: 'strobe', name: 'Strobe slow · fast', need: g => _lbHas(g, 'strobe'), fam: 'strobe', isNew: true, why: 'needs a strobe' },
    { id: 'strobechase', name: 'Strobe chase', need: g => g.fixtures.length > 1 && g.supported > 0, fam: 'strobe', chaser: true,
      why: 'needs two lights or more' },
    { id: 'blinder', name: 'Blinder hit', need: g => g.supported > 0, fam: 'blinder', why: 'needs a fixture definition' },
    { id: 'pulse', name: 'Pulse', need: g => g.supported > 0, fam: 'chase', chaser: true, why: 'needs a fixture definition' },
  ] },
  { id: 'movement', name: 'Movement', dot: '#60a5fa', items: [
    { id: 'places', name: 'Places on the stage', need: g => _lbHas(g, 'moves'), fam: 'places', isNew: true, why: 'needs a moving head' },
    { id: 'sweep', name: 'Audience sweep', need: g => _lbHas(g, 'moves'), fam: 'efx', why: 'needs a moving head' },
    { id: 'fly', name: 'Fly out · Fly in', need: g => _lbHas(g, 'moves'), fam: 'efx', isNew: true, why: 'needs a moving head' },
    { id: 'circle', name: 'Circle · Figure eight', need: g => _lbHas(g, 'moves'), fam: 'efx', isNew: true, why: 'needs a moving head' },
  ] },
  { id: 'matrix', name: 'Matrix', dot: '#34d399', items: [
    { id: 'mchase', name: 'Pixel chase', need: g => _lbHas(g, 'grid'), fam: 'matrix', why: 'needs a group laid out as a grid' },
    { id: 'mwave', name: 'Wave', need: g => _lbHas(g, 'grid'), fam: 'matrix', why: 'needs a group laid out as a grid' },
    { id: 'mmore', name: 'Plasma · Gradient · Stripes', need: g => _lbHas(g, 'grid'), fam: 'matrix', why: 'needs a group laid out as a grid' },
  ] },
];
const LB_ITEMS = Object.fromEntries(LB_FAM.flatMap(f => f.items.map(e => [e.id, e])));

// The wizard's show types (stagewizard.cpp applyShowTypeDefaults)
const LB_TYPES = {
  'Club night': ['colour', 'rainbow', 'split', 'blinder', 'strobechase', 'pulse', 'fly', 'circle', 'mchase'],
  'Concert': ['colour', 'rainbow', 'gobo', 'blinder', 'strobechase', 'places', 'fly', 'circle', 'sweep', 'ambient'],
  'Theatre': ['colour', 'places', 'gobo', 'ambient'],
  'Architectural': ['colour', 'mchase', 'mwave', 'mmore', 'ambient'],
  'Custom': [],
};

function looksInit() {
  if (!_lbOpts) _lbLoad();
}

function invalidateLooks() {
  _lbOpts = null; _lbSel = new Set(); _lbFx = new Map(); _lbEdits = {}; _lbOwn = []; _lbBars = [];
  _lbEditing = null; _lbLast = null; _lbType = 'Custom';
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
    _lbRole = Object.fromEntries(d.groups.map(g => [g.id, g.role || 'Fill']));
    _lbGobos = Object.fromEntries(d.groups.map(g => [g.id, (g.gobo_names || []).slice(0, 7).map((_, i) => i + 1)]));
    _lbCols = ['Red', 'Blue', 'Amber'].map(_lbColour).filter(Boolean);
    _lbPlace = (d.places[0] || {}).name || '';
    _lbRender();
  } catch (e) { /* no workspace */ }
}

// ── helpers ─────────────────────────────────────────────────────────────────
function _v(id) { return document.getElementById(id); }
function _lbHas(g, cap) { return (g.caps || []).includes(cap); }
function _lbGroup(id) { return _lbOpts.groups.find(g => g.id === id); }
function _lbGName(id) { return (_lbGroup(id) || {}).name || id; }

function _lbAllColours() {
  if (!_lbOpts) return [];
  const out = [];
  for (const k of _lbOpts.palette_order) for (const c of _lbOpts.palettes[k].colours) out.push(c);
  const seen = new Set();
  return out.concat(_lbCustom).filter(c => !seen.has(c.name) && seen.add(c.name));
}
function _lbColour(name) { return _lbAllColours().find(c => c.name === name) || (name === 'White' ? LB_WHITE : null); }

function _lbChip(c, on, fn) {
  return `<button class="lb-chip ${on ? 'on' : ''}" style="--c:${c.hex}" title="${_esc(c.hex)}"
            onclick="${fn}('${_esc(c.name).replace(/'/g, "\\'")}')"><i></i><span data-i18n-ctx="colour">${_esc(c.name)}</span></button>`;
}

// groups an effect can go to: picked, able to do it
function _lbCapable(eid) { return [..._lbSel].filter(id => LB_ITEMS[eid].need(_lbGroup(id))); }

// ── render ──────────────────────────────────────────────────────────────────
function _lbRender() {
  const el = _v('lb-body');
  if (!el || !_lbOpts) return;
  el.innerHTML = `
  <div class="lbx-top">
    <span class="lbx-lbl">Start from</span>
    <div class="lbx-seg" role="group" aria-label="Show type">${Object.keys(LB_TYPES).map(t =>
      `<button type="button" class="${_lbType === t ? 'on' : ''}" onclick="looksType('${t}')" data-i18n-ctx="lb">${_esc(t)}</button>`).join('')}</div>
    <span class="p-desc">pre-ticks effects the way the QLC+ 5.3 Show Wizard does; change anything after</span>
  </div>
  <div class="lbx-cols">
    <section class="lbx-groups lb-card" aria-label="Groups">
      <div class="lbx-h"><h3>Groups</h3><button class="btn btn-surface btn-sm" onclick="looksAllGroups()">Select all</button></div>
      <div id="lbx-glist"></div>
      <p class="p-desc">Roles are the QLC+ wizard’s, suggested from the group’s name and fixtures. <b>Start from</b> gives each effect to the groups whose role suits it.</p>
    </section>
    <section class="lbx-fams" id="lbx-fams" aria-label="Effects"></section>
    <aside class="lbx-add lb-card" aria-label="What Apply will add">
      <h3>Will add</h3>
      <div id="lbx-stage" class="lbx-stage" aria-label="The stage seen from above"></div>
      <div id="lb-batch" class="lbx-sum"></div>
      <fieldset class="lbx-vc"><legend>On the console</legend>
        <label><input type="radio" name="lb-vc" value="pages" checked onchange="_lbChanged()"> <span>A page per group, like the QLC+ wizard</span></label>
        <label><input type="radio" name="lb-vc" value="one" onchange="_lbChanged()"> <span>One page with every button</span></label>
        <label><input type="radio" name="lb-vc" value="none" onchange="_lbChanged()"> <span>No buttons</span></label>
        <label class="lbx-inl">Page name <input class="filter-input" id="lb-vcname" value="Looks" oninput="_lbChanged()"></label>
      </fieldset>
      <div class="lbx-opts">
        <label>Folder <input class="filter-input" id="lb-folder" value="Look Builder" oninput="_lbChanged()"></label>
        <label><input type="checkbox" id="lb-bygroup" checked onchange="_lbChanged()"> <span>a folder per group</span></label>
        <label>Names <select id="lb-nom" class="filter-input" onchange="_lbChanged()">${_lbOpts.nomenclature.map(p =>
          `<option value="${_esc(p.id)}">${_esc(p.label)}</option>`).join('')}</select></label>
        <label><input type="checkbox" id="lb-pal" onchange="_lbChanged()"> <span>also add QLC+ palettes</span></label>
      </div>
      <div class="lbx-promise">Every look declares every channel. Strobe stays off unless the effect is a strobe. PANIC RESET stops every new effect.</div>
      <div id="lb-check"></div>
    </aside>
  </div>
  <div id="lbx-panel" class="lbx-panel" hidden></div>`;
  _lbRenderGroups();
  _lbRenderFams();
  _lbChanged();
}

function _lbRenderGroups() {
  const el = _v('lbx-glist');
  if (!el) return;
  el.innerHTML = _lbOpts.groups.map(g => {
    const on = _lbSel.has(g.id), dis = !g.supported;
    return `<div class="lbx-g ${on ? 'on' : ''} ${dis ? 'dis' : ''}">
      <label class="lbx-gh"><input type="checkbox" ${on ? 'checked' : ''} ${dis ? 'disabled' : ''} onchange="looksGroup('${_esc(g.id)}', this.checked)">
        <b data-i18n="off">${_esc(g.name)}</b><span class="lb-n">${g.fixtures.length}</span></label>
      <div class="lbx-gm"><label>Role <select class="filter-input" onchange="looksRole('${_esc(g.id)}', this.value)">${_lbOpts.roles.map(r =>
        `<option ${_lbRole[g.id] === r ? 'selected' : ''} data-i18n="off">${r}</option>`).join('')}</select></label>
        <span class="lbx-model" data-i18n="off" title="${_esc(g.model || '')}">${_esc(g.model || '')}</span></div>
      <div class="lbx-caps">${(g.labels || []).map(c => `<span data-i18n-ctx="lb">${_esc(c)}</span>`).join('')}${dis ? '<span class="lbx-warn">no fixture definition</span>' : ''}</div>
    </div>`;
  }).join('');
}

// "1 look" / "12 looks": whole strings, so each language has its own form
const LB_UNITS = { look: 'looks', chaser: 'chasers', 'movement effect': 'movement effects', 'RGB matrix': 'RGB matrices' };
function _lbN(n, one) { return n === 1 ? `1 ${one}` : `${n} ${LB_UNITS[one]}`; }

function _lbMakes(e, gids) {
  const n = gids.length, nc = Math.max(_lbCols.length, 1);
  switch (e.id) {
    case 'colour': return [_lbN(_lbCols.length * n, 'look'), `${_lbCols.length} colours × ${n} groups`];
    case 'gobo': { const k = gids.reduce((a, id) => a + (_lbGobos[id] || []).length, 0) * nc; return [_lbN(k, 'look'), 'a gobo in each ticked colour']; }
    case 'levels': return [_lbN(3 * n, 'look'), 'white at 100, 50 and 0 %'];
    case 'strobe': return [_lbN(2 * n, 'look'), 'each light in its own strobe range'];
    case 'blinder': return ['1 flash button', 'every light at full'];
    case 'places': return [`aim at ${_lbPlace}`, 'the looks of the moving heads'];
    case 'fly': case 'circle': return [_lbN(2 * n, 'movement effect'), ''];
    case 'sweep': return [_lbN(n, 'movement effect'), ''];
    case 'mmore': return [_lbN(3 * n, 'RGB matrix'), ''];
    case 'mchase': case 'mwave': return [_lbN(n, 'RGB matrix'), ''];
    default: return [_lbN(n, 'chaser'), ''];
  }
}

function _lbRenderFams() {
  const el = _v('lbx-fams');
  if (!el) return;
  el.innerHTML = LB_FAM.map(f => {
    const ticked = f.items.filter(e => (_lbFx.get(e.id) || new Set()).size).length;
    return `<div class="lb-card lbx-fam">
      <div class="lbx-h"><i class="lbx-dot" style="background:${f.dot}"></i><h3 data-i18n-ctx="lb">${f.name}</h3>
        <span class="lb-n">${ticked} of ${f.items.length} ticked</span><span class="lbx-sp"></span>
        <button class="btn btn-surface btn-sm" onclick="looksFamily('${f.id}')">All / None</button></div>
      <div class="lbx-cards">${f.items.map(e => _lbCard(e)).join('')}</div>
      ${f.id === 'colour' ? _lbColourBar() : ''}
      ${f.id === 'colour' && (_lbFx.get('gobo') || new Set()).size ? _lbGoboBar() : ''}
      ${f.id === 'movement' && (_lbFx.get('places') || new Set()).size ? _lbPlaceBar() : ''}
      ${f.id === 'matrix' && _lbOpts.pixel_bars.length ? _lbBarsBar() : ''}
    </div>`;
  }).join('') + `<div class="lb-card lbx-fam">
      <div class="lbx-h"><i class="lbx-dot" style="background:#fbbf24"></i><h3>Your chasers</h3><span class="lb-n">${_lbOwn.length}</span>
        <span class="lbx-sp"></span><button class="btn btn-surface btn-sm" onclick="looksEdit('new')">+ New chaser</button></div>
      ${_lbOwn.map((c, i) => `<div class="lb-item"><span>🔁 ${_esc(c.name || (_lbOpts.patterns.find(p => p.id === c.pattern) || {}).label)} — ${_esc(_lbGName(c.group))}
        ${c.colours.map(x => `<i class="lb-dot" style="background:${x.hex}"></i>`).join('')}</span>
        <button class="btn btn-surface btn-sm" onclick="looksRemoveOwn(${i})" aria-label="Remove">✕</button></div>`).join('')
        || '<p class="p-desc">A chaser of your own: any group, pattern, colours and timing, with the song presets.</p>'}
    </div>`;
}

function _lbCard(e) {
  const gids = _lbFx.get(e.id) || new Set();
  const cap = _lbCapable(e.id);
  const ok = cap.length > 0;
  const on = gids.size > 0;
  const [makes, sub] = on ? _lbMakes(e, [...gids]) : ok ? _lbMakes(e, cap) : ['', ''];
  return `<div class="lbx-c ${on ? 'on' : ''} ${ok ? '' : 'dis'}">
    <label class="lbx-ch"><input type="checkbox" ${on ? 'checked' : ''} ${ok ? '' : 'disabled'} onchange="looksTick('${e.id}', this.checked)">
      <b data-i18n-ctx="lb">${e.name}</b>${e.isNew ? '<span class="lbx-new">NEW</span>' : ''}</label>
    ${ok ? `<div class="lbx-mk"><span>${makes}</span>${sub ? `<span class="lb-n">${sub}</span>` : ''}</div>` :
      `<div class="lbx-why">${_lbSel.size ? `<span>Not for these groups</span> <span>${e.why}</span>` : '<span>Pick a group</span>'}</div>`}
    ${on ? `<div class="lbx-on">${cap.map(id => `<button class="lbx-gchip ${gids.has(id) ? 'on' : ''}" onclick="looksFxGroup('${e.id}', '${_esc(id)}')" data-i18n="off">${_esc(_lbGName(id))}</button>`).join('')}
      ${e.chaser ? `<button class="btn btn-surface btn-sm" onclick="looksEdit('${e.id}')">Edit…</button>` : ''}</div>` : ''}
  </div>`;
}

function _lbColourBar() {
  const on = c => _lbCols.some(x => x.name === c.name);
  return _lbOpts.palette_order.map(k => { const p = _lbOpts.palettes[k];
    return `<div class="lbx-bar"><span class="lbx-lbl">${_esc(p.label)}</span>
      ${p.colours.map(c => _lbChip(c, on(c), 'looksColour')).join('')}
      <button class="btn btn-surface btn-sm" onclick="looksPalette('${_esc(k)}')">all</button></div>`; }).join('') +
  `<div class="lbx-bar"><span class="lbx-lbl">Custom</span>
    ${_lbCustom.map(c => _lbChip(c, on(c), 'looksColour')).join('')}
    <input type="color" id="lb-cust-hex" value="#ff8800" title="Pick a colour">
    <input class="filter-input lb-cname" id="lb-cust-name" placeholder="name">
    <button class="btn btn-surface btn-sm" onclick="looksAddCustom()">+ add</button>
    <input class="filter-input lb-cname" id="lb-palname" placeholder="palette name">
    <button class="btn btn-surface btn-sm" onclick="looksSavePalette()" title="Keep the ticked colours as a palette of your own">★ Save ticked as palette</button>
    <button class="btn btn-surface btn-sm" onclick="looksDeletePalette()" title="Delete the palette named in the box (yours only)" aria-label="Delete palette">🗑</button>
    <label class="lbx-inl">Level <input type="range" id="lb-level" min="5" max="100" step="5" value="100"
      oninput="document.getElementById('lb-level-v').textContent=this.value+' %'; _lbChanged()"> <span id="lb-level-v">100 %</span></label>
  </div>`;
}

function _lbGoboBar() {
  const gids = [..._lbFx.get('gobo')];
  return gids.map(id => {
    const g = _lbGroup(id), names = g.gobo_names || [], pick = _lbGobos[id] || [];
    return `<div class="lbx-bar"><span class="lbx-lbl" data-i18n="off">${_esc(g.name)}</span><span class="lb-n" data-i18n-ctx="lb">gobos</span>
      ${names.map((n, i) => `<button class="lbx-gchip ${pick.includes(i + 1) ? 'on' : ''}" onclick="looksGobo('${_esc(id)}', ${i + 1})" data-i18n="off">${_esc(n)}</button>`).join('')}
      <button class="btn btn-surface btn-sm" onclick="looksGoboAll('${_esc(id)}')">All / None</button></div>`;
  }).join('');
}

function _lbPlaceBar() {
  return `<div class="lbx-bar"><span class="lbx-lbl">Aim at</span>
    ${_lbOpts.places.map(p => `<button class="lbx-gchip ${_lbPlace === p.name ? 'on' : ''}" onclick="looksPlace('${_esc(p.name).replace(/'/g, "\\'")}')" data-i18n="off">${_esc(p.name)}</button>`).join('')}
    <span class="p-desc">The colour and gobo looks of the moving heads aim here. Musicians come from the models placed in Stage &amp; Meshes.</span></div>`;
}

function _lbBarsBar() {
  return `<details class="lbx-bars"><summary>Pixel bars (${_lbOpts.pixel_bars.length})</summary>
    <div class="lb-groups">${_lbOpts.pixel_bars.map(b => `
      <label><input type="checkbox" class="lb-mb" value="${_esc(b.id)}" checked> ${_esc(b.name)} <span class="lb-n">${b.heads} pixels</span></label>`).join('')}</div>
    <div class="lb-grid">
      <label>Pattern <select id="lb-mpat" class="filter-input" onchange="_lbMatrixForm()">${_lbOpts.matrix_patterns.map(m =>
        `<option value="${_esc(m.name)}">${_esc(m.name)}</option>`).join('')}</select></label>
      <label>Colour 1 <input type="color" id="lb-mc1"></label>
      <label>Colour 2 <input type="color" id="lb-mc2"></label>
      <label>Speed <input type="number" id="lb-mdur" class="filter-input rr-num" min="20" max="600000" step="10"> ms</label>
      <label>Name <input class="filter-input" id="lb-mname" placeholder="default: bars + pattern"></label>
    </div>
    <div class="lb-row"><span class="p-desc">The bars ticked make one grid: the pattern runs across their pixels.</span><span class="lbx-sp"></span>
      <button class="btn btn-surface btn-sm" onclick="looksAddMatrix()">+ Add matrix pattern</button></div>
    ${_lbBars.map((m, i) => `<div class="lb-item"><span>▦ ${_esc(m.name || m.pattern)} — ${m.fixtures.length} bar(s)</span>
      <button class="btn btn-surface btn-sm" onclick="looksRemoveBar(${i})" aria-label="Remove">✕</button></div>`).join('')}
  </details>`;
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
  _lbBars.push(spec);
  _lbRenderFams(); _lbChanged();
  setStatus('Matrix pattern added.', 'ok');
}
function looksRemoveBar(i) { _lbBars.splice(i, 1); _lbRenderFams(); _lbChanged(); }

// ── stage preview: lights seen from above, lit by the first look ────────────
function _lbRenderStage() {
  const el = _v('lbx-stage');
  if (!el) return;
  const st = _lbOpts.stage || {}, fx = (st.fixtures || []).filter(f => f.x != null);
  if (!fx.length) { el.innerHTML = '<div class="p-desc">Place the lights in Stage &amp; Meshes to see them here.</div>'; return; }
  const w = (st.size && st.size.w ? st.size.w * 1000 : Math.max(...fx.map(f => f.x)) + 500);
  const d = (st.size && st.size.d ? st.size.d * 1000 : Math.max(...fx.map(f => f.z)) + 500);
  const lit = {};
  const cols = _lbCols.length ? _lbCols : [LB_WHITE];
  if ((_lbFx.get('colour') || new Set()).size) {
    for (const id of _lbFx.get('colour')) (_lbGroup(id).fixtures || []).forEach((f, i) => { lit[f] = cols[i % cols.length].hex; });
  }
  for (const eid of ['levels', 'blinder', 'strobe']) for (const id of (_lbFx.get(eid) || [])) (_lbGroup(id).fixtures || []).forEach(f => { lit[f] = lit[f] || '#ffffff'; });
  const sel = new Set([..._lbSel].flatMap(id => _lbGroup(id).fixtures));
  el.innerHTML = `<div class="lbx-st-l"><span>BACK</span></div><div class="lbx-st-map">${fx.map(f => {
    const c = lit[f.id];
    return `<i style="left:${(100 * f.x / w).toFixed(1)}%;top:${(100 * f.z / d).toFixed(1)}%;${c ? `background:${c};box-shadow:0 0 8px ${c}` : ''}" class="${sel.has(f.id) ? 'sel' : ''}"></i>`;
  }).join('')}</div><div class="lbx-st-l"><span>FRONT</span></div>`;
}

// ── actions ─────────────────────────────────────────────────────────────────
function looksType(t) {
  _lbType = t;
  _lbFx = new Map();
  if (!_lbSel.size && t !== 'Custom') _lbOpts.groups.filter(g => g.supported && g.id !== 'all').forEach(g => _lbSel.add(g.id));
  const fams = _lbOpts.role_families || {};
  for (const eid of LB_TYPES[t] || []) {
    const cap = _lbCapable(eid);
    const byRole = cap.filter(id => (fams[_lbRole[id]] || []).includes(LB_ITEMS[eid].fam));
    const gs = byRole.length ? byRole : cap;
    if (gs.length) _lbFx.set(eid, new Set(gs));
  }
  _lbRender();
}

function looksAllGroups() {
  _lbOpts.groups.filter(g => g.supported && g.id !== 'all').forEach(g => looksGroup(g.id, true, true));
  _lbRenderGroups(); _lbRenderFams(); _lbChanged();
}

function looksGroup(id, on, quiet) {
  if (on) _lbSel.add(id); else _lbSel.delete(id);
  for (const [eid, gs] of _lbFx) {
    if (!on) gs.delete(id);
    else if (gs.size && LB_ITEMS[eid].need(_lbGroup(id))) gs.add(id);
    if (!gs.size) _lbFx.delete(eid);
  }
  if (!quiet) { _lbRenderGroups(); _lbRenderFams(); _lbChanged(); }
}

function looksRole(id, role) { _lbRole[id] = role; }

function looksTick(eid, on) {
  if (on) _lbFx.set(eid, new Set(_lbCapable(eid))); else _lbFx.delete(eid);
  _lbRenderFams(); _lbChanged();
}

function looksFamily(fid) {
  const f = LB_FAM.find(x => x.id === fid);
  const all = f.items.every(e => !_lbCapable(e.id).length || (_lbFx.get(e.id) || new Set()).size);
  f.items.forEach(e => { if (all) _lbFx.delete(e.id); else if (_lbCapable(e.id).length) _lbFx.set(e.id, new Set(_lbCapable(e.id))); });
  _lbRenderFams(); _lbChanged();
}

function looksFxGroup(eid, gid) {
  const s = _lbFx.get(eid);
  if (!s) return;
  if (s.has(gid)) s.delete(gid); else s.add(gid);
  if (!s.size) _lbFx.delete(eid);
  _lbRenderFams(); _lbChanged();
}

function looksColour(name) {
  const i = _lbCols.findIndex(c => c.name === name);
  if (i >= 0) _lbCols.splice(i, 1); else _lbCols.push(_lbColour(name));
  _lbRenderFams(); _lbChanged();
}

function looksPalette(k) {
  const cs = _lbOpts.palettes[k].colours;
  const all = cs.every(c => _lbCols.some(x => x.name === c.name));
  if (all) _lbCols = _lbCols.filter(x => !cs.some(c => c.name === x.name));
  else cs.forEach(c => { if (!_lbCols.some(x => x.name === c.name)) _lbCols.push(c); });
  _lbRenderFams(); _lbChanged();
}

function looksGobo(gid, n) {
  const a = _lbGobos[gid] || (_lbGobos[gid] = []);
  const i = a.indexOf(n);
  if (i >= 0) a.splice(i, 1); else { a.push(n); a.sort((x, y) => x - y); }
  _lbRenderFams(); _lbChanged();
}
function looksGoboAll(gid) {
  const n = (_lbGroup(gid).gobo_names || []).length;
  _lbGobos[gid] = (_lbGobos[gid] || []).length === n ? [] : Array.from({ length: n }, (_, i) => i + 1);
  _lbRenderFams(); _lbChanged();
}
function looksPlace(name) { _lbPlace = name; _lbRenderFams(); _lbChanged(); }

function looksAddCustom() {
  const hex = _v('lb-cust-hex').value.toUpperCase();
  const name = (_v('lb-cust-name').value || '').trim() || hex;
  if (_lbAllColours().some(c => c.name.toLowerCase() === name.toLowerCase())) { setStatus(`'${name}' already exists.`, 'warn'); return; }
  const c = { name, hex };
  _lbCustom.push(c); _lbCols.push(c);
  _lbRenderFams(); _lbChanged();
}

async function looksSavePalette() {
  const name = (_v('lb-palname').value || '').trim();
  if (!name) { setStatus('Type a name for the palette.', 'warn'); return; }
  if (!_lbCols.length) { setStatus('Tick the colours to keep.', 'warn'); return; }
  const r = await fetch('/api/looks/palettes', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, colours: _lbCols }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.palettes = d.palettes; _lbOpts.palette_order = d.palette_order;
  _lbRenderFams();
  setStatus(`Palette '${name}' saved.`, 'ok');
}

async function looksDeletePalette() {
  const name = (_v('lb-palname').value || '').trim();
  if (!name) { setStatus('Type the name of your palette to delete.', 'warn'); return; }
  const r = await fetch('/api/looks/palettes/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.palettes = d.palettes; _lbOpts.palette_order = d.palette_order;
  _lbRenderFams();
  setStatus(`Palette '${name}' deleted.`, 'ok');
}

function looksRemoveOwn(i) { _lbOwn.splice(i, 1); _lbRenderFams(); _lbChanged(); }

// ── chaser recipes of the cards ─────────────────────────────────────────────
function _lbRecipe(eid) {
  if (_lbEdits[eid]) return { ..._lbEdits[eid] };
  const cols = _lbCols.length ? _lbCols : [LB_WHITE];
  const named = n => _lbColour(n);
  switch (eid) {
    case 'rainbow': return { pattern: 'all', colours: LB_RAINBOW.map(named).filter(Boolean), step_ms: 1500, fade: 'fade', fade_pct: 33,
      colour_mode: 'step', kind: 'dynamic', name: 'Rainbow' };
    case 'split': return { pattern: 'alternate', colours: (cols.length > 1 ? cols : ['Red', 'Blue'].map(named)), step_ms: 1000, fade: 'cut',
      colour_mode: 'step', kind: 'dynamic', name: 'Split colour' };
    case 'ambient': return { pattern: 'all', colours: (cols.length > 1 ? cols : ['Warm White', 'Amber', 'Orange'].map(named)), step_ms: 6000,
      fade: 'fade', fade_pct: 100, colour_mode: 'step', kind: 'dynamic', name: 'Ambient loop' };
    case 'strobechase': return { pattern: 'chase', colours: [LB_WHITE], step_ms: 80, fade: 'cut', colour_mode: 'step', kind: 'fx', name: 'Strobe chase' };
    case 'pulse': return { pattern: 'all', colours: [cols[0]], bpm: 120, note: '1/4', fade: 'fade', fade_pct: 50, colour_mode: 'step',
      kind: 'pulse', name: 'Pulse' };
    default: return { pattern: 'chase', colours: cols.slice(0, 4), bpm: 120, note: '1/4', fade: 'cut', colour_mode: 'step', kind: 'dynamic' };
  }
}

// ── the effect panel (chasers: basics, preview, More) ───────────────────────
function looksEdit(eid) {
  _lbEditing = eid;
  const p = _v('lbx-panel');
  const r = _lbRecipe(eid);
  const title = eid === 'new' ? 'New chaser' : LB_ITEMS[eid].name;
  const firstG = [...(_lbFx.get(eid) || _lbSel)][0] || (_lbOpts.groups.find(g => g.supported) || _lbOpts.groups[0]).id;
  p.innerHTML = `<div class="lbx-ph">
      <button class="btn btn-surface btn-sm lbx-back" onclick="looksEditClose(false)">← Look &amp; Chaser Builder</button>
      <h3 data-i18n-ctx="lb">${_esc(title)}</h3><span class="lbx-sp"></span></div>
    <div class="lbx-pcols"><div class="lb-card" data-lbpane="chaser">
      <div class="lb-row"><span class="lbx-lbl">Recipe</span>
        <select id="lb-preset" class="filter-input" onchange="looksLoadPreset(this.value)">
          <option value="">—</option>${_lbOpts.presets.map((q, i) => `<option value="${i}">${q.builtin ? '' : '★ '}${_esc(q.name)}</option>`).join('')}</select>
        <input class="filter-input" id="lb-pname" placeholder="save as…">
        <button class="btn btn-surface btn-sm" onclick="looksSavePreset()">★ Save as recipe</button>
        <button class="btn btn-surface btn-sm" onclick="looksDeletePreset()" title="Delete the selected recipe (yours only)" aria-label="Delete recipe">🗑</button></div>
      <div class="lb-row" ${eid === 'new' ? '' : 'hidden'}><span class="lbx-lbl">Group</span>
        <select id="lb-cg" class="filter-input" onchange="_lbChPreview()">${_lbOpts.groups.map(g =>
          `<option value="${_esc(g.id)}" ${g.id === firstG ? 'selected' : ''} ${g.supported ? '' : 'disabled'}>${_esc(g.name)} (${g.fixtures.length})</option>`).join('')}</select></div>
      <div class="lb-row"><span class="lbx-lbl">Pattern</span><div class="lbx-pats">${_lbOpts.patterns.map(q =>
        `<button type="button" class="lbx-pat ${q.id === r.pattern ? 'on' : ''}" data-pat="${q.id}" onclick="looksPattern('${q.id}')"><i class="lbx-pic lbx-pic-${q.id}"></i><span>${_esc(q.label)}</span></button>`).join('')}</div>
        <input type="hidden" id="lb-pat" value="${r.pattern}"></div>
      <div class="lb-pal"><span class="lbx-lbl">Colours</span><span id="lb-chcols"></span></div>
      <div class="lb-pal lb-small">${_lbAllColours().map(c => _lbChip(c, false, 'looksAddChColour')).join('')}${_lbChip(LB_WHITE, false, 'looksAddChColour')}</div>
      <div class="lb-row"><span class="lbx-lbl">Speed</span>
        <label class="lb-bpm">BPM <input type="number" id="lb-bpm" class="filter-input rr-num" min="20" max="400" value="${r.bpm || 120}" oninput="_lbChPreview()"></label>
        <button class="btn btn-surface btn-sm lb-bpm" onclick="looksTap()">Tap</button>
        <label class="lb-bpm">Note <select id="lb-note" class="filter-input" onchange="_lbChPreview()">${_lbOpts.notes.map(n =>
          `<option ${n === (r.note || '1/4') ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
        <label class="lb-ms">Step <input type="number" id="lb-ms" class="filter-input rr-num" min="20" value="${r.step_ms || 500}" oninput="_lbChPreview()"> ms</label>
        <span class="lbx-sp"></span>
        <label>Fade <select id="lb-fade" class="filter-input" onchange="_lbChForm()">
          <option value="cut" ${r.fade !== 'fade' ? 'selected' : ''}>Cut</option><option value="fade" ${r.fade === 'fade' ? 'selected' : ''}>Soft</option></select></label></div>
      <details class="lbx-more"><summary>More: the expert settings</summary><div class="lb-grid">
        <label>Steps <input type="number" id="lb-steps" class="filter-input rr-num" min="1" max="256" placeholder="auto" value="${r.steps || ''}" oninput="_lbChPreview()"></label>
        <label class="lb-rnd">Seed <input type="number" id="lb-seed" class="filter-input rr-num" value="${r.seed ?? 1}" oninput="_lbChPreview()"></label>
        <label class="lb-rnd">On per step <input type="number" id="lb-on" class="filter-input rr-num" min="1" value="${r.on_count ?? 1}" oninput="_lbChPreview()"></label>
        <label class="lb-alt">Split <select id="lb-split" class="filter-input" onchange="_lbChPreview()">
          <option value="halves">left / right halves</option><option value="odd_even" ${r.split === 'odd_even' ? 'selected' : ''}>odd / even</option></select></label>
        <label>Timing <select id="lb-tm" class="filter-input" onchange="_lbChForm()">
          <option value="bpm" ${r.bpm ? 'selected' : ''}>BPM + note</option><option value="ms" ${r.bpm ? '' : 'selected'}>ms per step</option></select></label>
        <label class="lb-bpm" title="The chaser follows the BPM of QLC+ itself (speed dial / tap) instead of a fixed time: steps are stored in beats">
          <input type="checkbox" id="lb-beats" ${r.tempo === 'beats' ? 'checked' : ''} onchange="_lbChPreview()"> follow the QLC+ tempo (beats)</label>
        <label class="lb-fd">% of step <input type="number" id="lb-fpct" class="filter-input rr-num" min="0" max="100" value="${r.fade_pct ?? 100}" oninput="_lbChPreview()"></label>
        <label>Colours <select id="lb-cmode" class="filter-input" onchange="_lbChPreview()">
          <option value="step">change per step</option><option value="fixture" ${r.colour_mode === 'fixture' ? 'selected' : ''}>one per fixture</option></select></label>
        <label>Type <select id="lb-kind" class="filter-input">${['dynamic', 'pulse', 'movement', 'fx'].map(k =>
          `<option value="${k}" ${r.kind === k ? 'selected' : ''}>${{ dynamic: 'dynamic', pulse: 'pulse', movement: 'movement', fx: 'special FX' }[k]}</option>`).join('')}</select></label>
        <label><input type="checkbox" id="lb-bg" ${r.background ? 'checked' : ''} onchange="_lbChPreview()"> Background
          <select id="lb-bgc" class="filter-input" onchange="_lbChPreview()">${_lbAllColours().map(c =>
            `<option data-i18n-ctx="colour" ${c.name === ((r.background || {}).colour || {}).name || (!r.background && c.name === 'Blue') ? 'selected' : ''}>${_esc(c.name)}</option>`).join('')}</select>
          <input type="number" id="lb-bgl" class="filter-input rr-num" min="5" max="100" value="${Math.round(((r.background || {}).level ?? 0.3) * 100)}" oninput="_lbChPreview()"> %</label>
        <label>Position <select id="lb-cpos" class="filter-input" onchange="_lbChPreview()">
          <option value="">— as it is —</option>${_lbOpts.places.map(q => `<option value="place:${_esc(q.name)}">${_esc(q.name)}</option>`).join('')}
          ${_lbOpts.positions.map(q => `<option value="${_esc(q.name)}">${_esc(q.name)} (pan ${q.pan} · tilt ${q.tilt} %)</option>`).join('')}</select></label>
        <label>Name <input class="filter-input" id="lb-cname" placeholder="name (default: pattern + colours)" value="${_esc(eid === 'new' ? '' : (r.name || ''))}"></label>
      </div></details>
    </div>
    <div class="lb-card lbx-prevcard"><div class="lbx-h"><h3>Preview</h3><span class="lbx-sp"></span>
      <button class="btn btn-surface btn-sm" id="lb-playbtn" onclick="looksPlay()">▶ Play</button></div>
      <div id="lb-ch-prev" class="lb-prev"></div></div></div>`;
  _lbChCols = (r.colours || []).map(c => typeof c === 'string' ? _lbColour(c) : c).filter(Boolean);
  p.hidden = false;
  document.querySelector('#lb-body .lbx-cols').hidden = true;
  document.querySelector('#lb-body .lbx-top').hidden = true;
  _lbRenderChCols();
  _lbChForm();
  _lbEditFooter(eid);
  if (typeof toolPosition === 'function')
    toolPosition('looks', { crumb: [title], modal: true, back: () => looksEditClose(false) });
}

/** 3.4.0: while the effect panel is open, the footer is the panel's: Cancel
 *  and Keep these settings, the one way back; Add to the show waits. */
function _lbEditFooter(eid) {
  const foot = document.querySelector('#scr-looks .out-footer');
  if (!foot) return;
  const old = document.getElementById('lbx-foot-edit');
  if (old) old.remove();
  foot.classList.toggle('lbx-editing', !!eid);
  if (!eid) return;
  const box = document.createElement('span');
  box.id = 'lbx-foot-edit';
  box.className = 'lbx-foot-edit';
  box.innerHTML = `<button class="btn btn-surface" onclick="looksEditClose(false)">Cancel</button>
    <span class="lbx-foot-note">Nothing is added to the show yet.</span><span class="spacer"></span>
    <button class="btn btn-accent" id="lb-edit-done" onclick="looksEditClose(true)"
      title="Back to all the effects with these settings; Add to the show puts them in the show">${eid === 'new' ? '+ Add chaser' : 'Keep these settings ›'}</button>`;
  foot.appendChild(box);
}

function looksEditClose(save) {
  _lbStop();
  if (save) {
    if (!_lbChCols.length) { setStatus('Pick at least one colour.', 'warn'); return; }
    const s = _lbSpec();
    if (_lbEditing === 'new') _lbOwn.push(s);
    else { delete s.group; _lbEdits[_lbEditing] = s; }
  }
  _lbEditing = null;
  _lbEditFooter(null);
  if (typeof toolPosition === 'function') toolPosition('looks', null);
  _v('lbx-panel').hidden = true;
  document.querySelector('#lb-body .lbx-cols').hidden = false;
  document.querySelector('#lb-body .lbx-top').hidden = false;
  _lbRenderFams(); _lbChanged();
}

function looksPattern(id) {
  _v('lb-pat').value = id;
  document.querySelectorAll('.lbx-pat').forEach(b => b.classList.toggle('on', b.dataset.pat === id));
  _lbChForm();
}

let _lbTaps = [];
function looksTap() {
  const t = performance.now();
  _lbTaps = _lbTaps.filter(x => t - x < 3000).concat(t);
  if (_lbTaps.length >= 2) {
    const gaps = _lbTaps.slice(1).map((x, i) => x - _lbTaps[i]);
    _v('lb-bpm').value = Math.round(60000 / (gaps.reduce((a, b) => a + b, 0) / gaps.length));
    _v('lb-tm').value = 'bpm';
    _lbChForm();
  }
}

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
  } else s.step_ms = +_v('lb-ms').value;
  const pos = _v('lb-cpos').value;
  if (pos.startsWith('place:')) s.place = pos.slice(6); else if (pos) s.position = pos;
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
    const spec = _lbSpec();
    if (_lbEditing && _lbEditing !== 'new') spec.group = [...(_lbFx.get(_lbEditing) || _lbSel)][0] || spec.group;
    const r = await fetch('/api/looks/preview-chaser', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec) });
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

function looksLoadPreset(i) {
  if (i === '') return;
  const p = _lbOpts.presets[+i];
  const set = (id, v) => { if (v !== undefined && v !== null) _v(id).value = v; };
  looksPattern(p.pattern || 'chase');
  _v('lb-steps').value = p.steps || '';
  if (p.bpm) { _v('lb-tm').value = 'bpm'; set('lb-bpm', p.bpm); set('lb-note', p.note || '1/4'); }
  else { _v('lb-tm').value = 'ms'; set('lb-ms', p.step_ms || 500); }
  _v('lb-beats').checked = p.tempo === 'beats';
  set('lb-cpos', typeof p.position === 'string' ? p.position : '');
  set('lb-fade', p.fade || 'cut'); set('lb-fpct', p.fade_pct ?? 100);
  set('lb-cmode', p.colour_mode || 'step'); set('lb-kind', p.kind || 'dynamic');
  set('lb-seed', p.seed ?? 1); set('lb-on', p.on_count ?? 1); set('lb-split', p.split || 'halves');
  if ((p.colours || []).length) _lbChCols = p.colours.map(c => typeof c === 'string' ? _lbColour(c) : (_lbColour(c.name) || c)).filter(Boolean);
  const bg = p.background;
  _v('lb-bg').checked = !!bg;
  if (bg) { set('lb-bgc', typeof bg.colour === 'string' ? bg.colour : bg.colour?.name); set('lb-bgl', Math.round((bg.level ?? 0.3) * 100)); }
  _v('lb-pname').value = p.builtin ? '' : p.name;
  _lbRenderChCols();
  _lbChForm();
}

async function looksSavePreset() {
  const name = (_v('lb-pname').value || '').trim();
  if (!name) { setStatus('Type a name for the recipe.', 'warn'); return; }
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
  setStatus(`Recipe '${name}' saved.`, 'ok');
}

async function looksDeletePreset() {
  const i = _v('lb-preset').value;
  if (i === '') return;
  const p = _lbOpts.presets[+i];
  if (p.builtin) { setStatus('Built-in recipes cannot be deleted.', 'warn'); return; }
  const r = await fetch('/api/looks/presets/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: p.name }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error, 'error'); return; }
  _lbOpts.presets = d.presets;
  _v('lb-preset').innerHTML = '<option value="">—</option>' + d.presets.map((q, k) =>
    `<option value="${k}">${q.builtin ? '' : '★ '}${_esc(q.name)}</option>`).join('');
  setStatus(`Recipe '${p.name}' deleted.`, 'ok');
}

// ── the plan sent to the server ─────────────────────────────────────────────
function _lbPlan() {
  const P = { looks: [], levels: [], strobes: [], gobos: [], chasers: [], efx: [], matrices: [] };
  if (!_lbOpts) return P;
  const fx = id => [...(_lbFx.get(id) || [])];
  const level = +(_v('lb-level')?.value || 100) / 100;
  const place = fx('places').length ? _lbPlace : '';
  const aimFor = gid => (place && (_lbFx.get('places') || new Set()).has(gid)) ? { place } : {};
  if (_lbCols.length) for (const g of fx('colour')) P.looks.push({ group: g, colours: _lbCols.map(c => ({ ...c })), level, ...aimFor(g) });
  for (const g of fx('gobo')) {
    const gobos = _lbGobos[g] || [];
    if (gobos.length) P.gobos.push({ group: g, colours: (_lbCols.length ? _lbCols : [LB_WHITE]).map(c => ({ ...c })), gobos, level, ...aimFor(g) });
  }
  for (const g of fx('levels')) P.levels.push({ group: g });
  for (const g of fx('strobe')) P.strobes.push({ group: g });
  if (fx('blinder').length) P.blinder = { groups: fx('blinder') };
  for (const eid of ['rainbow', 'split', 'ambient', 'strobechase', 'pulse']) for (const g of fx(eid)) P.chasers.push({ ..._lbRecipe(eid), group: g });
  P.chasers.push(..._lbOwn);
  for (const g of fx('sweep')) P.efx.push({ group: g, kind: 'sweep' });
  for (const g of fx('fly')) P.efx.push({ group: g, kind: 'fly_out' }, { group: g, kind: 'fly_in' });
  for (const g of fx('circle')) P.efx.push({ group: g, kind: 'circle' }, { group: g, kind: 'eight' });
  for (const g of fx('mchase')) P.matrices.push({ group: g, pattern: 'Chase' });
  for (const g of fx('mwave')) P.matrices.push({ group: g, pattern: 'Waves' });
  for (const g of fx('mmore')) ['Plasma', 'Gradient', 'Stripes'].forEach(pattern => P.matrices.push({ group: g, pattern }));
  P.matrices.push(..._lbBars);
  const vc = document.querySelector('input[name="lb-vc"]:checked')?.value || 'pages';
  return { ...P, vc, vc_page: vc === 'none' ? '' : (_v('lb-vcname')?.value || 'Looks'),
    folders: _v('lb-bygroup')?.checked ? 'group' : '', palettes: !!_v('lb-pal')?.checked,
    nomenclature: _v('lb-nom')?.value || 'plain', folder: _v('lb-folder')?.value || '' };
}

function _lbEmpty(p) {
  return !['looks', 'levels', 'strobes', 'gobos', 'chasers', 'efx', 'matrices'].some(k => p[k].length) && !(p.blinder || {}).groups;
}

// ── will add: counts from a debounced check ─────────────────────────────────
function _lbChanged() {
  _lbRenderStage();
  _lbSync();
  clearTimeout(_lbCheckTimer);
  const el = _v('lb-batch');
  const p = _lbPlan();
  if (_lbEmpty(p)) { _lbLast = null; if (el) el.innerHTML = '<div class="p-desc">Pick a group and tick an effect.</div>'; _lbSync(); return; }
  if (el) el.classList.add('busy');
  _lbCheckTimer = setTimeout(async () => {
    try {
      const r = await fetch('/api/looks/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
      const d = await r.json();
      if (!r.ok) { _lbLast = null; el.innerHTML = `<div class="porter-warn">${_esc(d.error || 'Check failed.')}</div>`; _lbSync(); return; }
      _lbLast = d;
      _lbRenderBatch();
    } catch (e) { /* the server went away */ } finally { el && el.classList.remove('busy'); }
  }, 450);
}

function _lbRenderBatch() {
  const el = _v('lb-batch');
  if (!el || !_lbLast) return;
  const c = _lbLast.created, doc = _lbLast.doctor;
  const rows = [['Looks (every channel set)', c.looks], ['Chasers', c.chasers], ['Movement effects', c.efx || 0],
    ['RGB matrices', c.matrices || 0], ['Buttons', c.buttons]].filter(x => x[1]);
  el.innerHTML = rows.map(([w, n]) => `<div class="lbx-sumrow"><span>${w}</span><b>+${n}</b></div>`).join('') +
    `<div class="lbx-doc ${doc.new_errors.length ? 'bad' : ''}">${doc.new_errors.length || doc.new_warnings.length
      ? `<span>Doctor: new</span> <span>${doc.new_errors.length} error(s), ${doc.new_warnings.length} warning(s)</span>` : '<span>Doctor: nothing new</span>'}</div>` +
    (_lbLast.blocked ? '<p class="porter-warn">⛔ The result has new Doctor errors — it will not be added.</p>' : '') +
    `<details><summary>Changes (${_lbLast.log.length})</summary><div class="rr-log">${_lbLast.log.map(x => `<div>${_esc(x)}</div>`).join('')}</div></details>` +
    (_lbLast.notes.length ? `<details><summary>Notes (${_lbLast.notes.length})</summary><div class="rr-log">${_lbLast.notes.map(x => `<div>${_esc(x)}</div>`).join('')}</div></details>` : '');
  _lbSync();
}

function _lbSync() {
  const s = _v('lb-summary'), b = _v('lb-go'), x = _v('lb-export');
  const c = _lbLast ? _lbLast.created : null;
  const ok = !!c && !_lbLast.blocked;
  if (s) s.innerHTML = _lbOpts ? `<span class="doc-chip">${_lbSel.size} group(s)</span><span class="doc-chip">${[..._lbFx.values()].filter(v => v.size).length} effect(s)</span>` : '';
  if (b) b.disabled = !ok;
  if (x) x.disabled = !ok;
  if (typeof setOutcome === 'function') setOutcome('looks', c
    ? [c.looks ? `+${c.looks} look${c.looks > 1 ? 's' : ''}` : '', c.chasers ? `+${c.chasers} chaser${c.chasers > 1 ? 's' : ''}` : '',
       c.efx ? `+${c.efx} movement effect${c.efx > 1 ? 's' : ''}` : '', c.matrices ? `+${c.matrices} matrix pattern${c.matrices > 1 ? 's' : ''}` : ''].filter(Boolean)
    : 'nothing yet — pick groups and tick effects', '', c ? 'Apply will add' : 'Apply will do');
}

async function looksCheck() { _lbChanged(); }

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
