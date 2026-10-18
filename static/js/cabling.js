/**
 * Cabling (3.6.0).
 *
 * Plans the DMX cables of the show in progress with the kit you own.  Four
 * steps: Kit (tonight's copy of your kit, what the show has that the kit
 * does not), Places (the computer, the splitter, walkways, outlets, fixtures
 * found on the day), Plan (alternatives, then the chains by hand), Check and
 * export (the checks, the load-in order, the pick list, labels, plot).
 * The show is only read; the plan is kept in <show>.cabling.json next to it
 * (/api/cabling/plan) and your kit in your settings (/api/cabling/kit).
 */

let _cb = null;               // /api/cabling/state + the latest evaluation
let _cbStepN = 0;
let _cbAlts = null;
let _cbPick = 'controller';
let _cbCorner = null;         // first corner of a walkway being drawn
let _cbSaveT = null, _cbEvalT = null;
const CB_STEPS = ['Kit', 'Places', 'Plan', 'Check and export'];
const CB_OWNERS = { mine: 'Mine', borrowed: 'Borrowed', venue: 'Venue' };
const CB_CONN = { xlr3: '3-pin', xlr5: '5-pin', rj45: 'RJ45', usb: 'USB', wireless: 'radio', jack35: 'jack' };
const CB_KIND = { interface: 'Interface', splitter: 'Splitter', node: 'Node', wireless_tx: 'Wireless TX',
  wireless_rx: 'Wireless RX', cable: 'Cable', adapter: 'Adapter', terminator: 'Terminator', fixture: 'Fixture' };
const CB_TERM = { none: 'No switch: needs a terminator', switch: 'Has a termination switch',
  auto: 'Terminates itself', unknown: 'Termination unknown' };

const _cbE = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const _cbT = (s, ...v) => (typeof t === 'function' ? t(s, ...v) : s.replace(/\{(\d+)\}/g, (_x, i) => v[+i] ?? ''));
const _cbG = g => (g === 'm' ? '♂' : g === 'f' ? '♀' : '');

function cablingInit() {
  if (!_cb) cablingLoad(); else _cbRender();
}

function invalidateCabling() {
  _cb = null;
  _cbAlts = null;
  if (document.getElementById('scr-cabling')?.classList.contains('active')) cablingLoad();
}

document.addEventListener('sk-lang', () => { if (_cb) _cbRender(); });

async function cablingLoad() {
  try {
    const r = await fetch('/api/cabling/state');
    const d = await r.json();
    _cb = r.ok ? d : null;
  } catch (e) { _cb = null; }
  _cbRender();
}

// ── keeping and checking ─────────────────────────────────────────────────────
function _cbChanged(redraw = true) {
  if (redraw) _cbRender();
  clearTimeout(_cbEvalT);
  _cbEvalT = setTimeout(_cbEvaluate, 200);
  clearTimeout(_cbSaveT);
  _cbSaveT = setTimeout(_cbSave, 600);
}

async function _cbEvaluate() {
  if (!_cb) return;
  try {
    const r = await fetch('/api/cabling/evaluate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan: _cb.plan }),
    });
    const d = await r.json();
    if (!r.ok) return;
    Object.assign(_cb, d);
    _cbRender();
  } catch (e) { /* the last result stays */ }
}

async function _cbSave() {
  if (!_cb) return false;
  try {
    const r = await fetch('/api/cabling/plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan: _cb.plan }),
    });
    const d = await r.json();
    const el = document.getElementById('cb-saved');
    if (el) el.textContent = d.saved ? _cbT('Plan kept in {0}', d.sidecar)
      : (d.error || _cbT('Plan kept until Swiss Knife closes (the show has no folder)'));
    return r.ok;
  } catch (e) { return false; }
}

// ── steps ────────────────────────────────────────────────────────────────────
function cablingStep(delta) { cablingGoStep(_cbStepN + delta); }

function cablingGoStep(i) {
  _cbStepN = Math.max(0, Math.min(CB_STEPS.length - 1, i));
  if (_cbStepN === 2 && !_cbAlts && _cb && !_cb.plan.chains.length) cablingPropose();
  _cbRender();
}

function _cbPosition() {
  if (typeof toolPosition !== 'function') return;
  toolPosition('cabling', {
    steps: CB_STEPS, cur: _cbStepN, go: i => cablingGoStep(i),
    finish: { verb: 'Keep', tip: 'Keeps the plan next to the show and ticks this step', run: async () => _cbSave() },
  });
}

function _cbRender() {
  CB_STEPS.forEach((_s, i) => { const el = document.getElementById('cb-step-' + i); if (el) el.hidden = i !== _cbStepN; });
  const back = document.getElementById('cb-back'), next = document.getElementById('cb-next');
  if (back) back.disabled = _cbStepN === 0;
  if (next) {
    next.hidden = _cbStepN === CB_STEPS.length - 1;
    if (_cbStepN < CB_STEPS.length - 1)
      next.textContent = typeof stepNextLabel === 'function' ? stepNextLabel(CB_STEPS[_cbStepN + 1]) : 'Next ›';
  }
  _cbPosition();
  if (!_cb) {
    const k = document.getElementById('cb-kit');
    if (k) k.innerHTML = `<div class="porter-placeholder">${_cbE(_cbT('Open a workspace with fixtures to plan its cables.'))}</div>`;
    if (typeof setOutcome === 'function') setOutcome('cabling', '');
    return;
  }
  _cbSummary();
  if (_cbStepN === 0) _cbKit();
  if (_cbStepN === 1) _cbPlaces();
  if (_cbStepN === 2) _cbPlan();
  if (_cbStepN === 3) _cbCheck();
}

function _cbSummary() {
  const ev = _cb.evaluation, tt = ev.totals, sm = ev.summary;
  const s = document.getElementById('cb-summary');
  if (s) s.innerHTML = [
    `<span class="doc-chip">${_cbE(_cbT('{0} fixtures', _cb.rig.fixtures.length + (_cb.plan.extras || []).length))}</span>`,
    `<span class="doc-chip">${_cbE(_cbT('{0} chains', tt.chains))}</span>`,
    `<span class="doc-chip">${_cbE(_cbT('{0} m of cable', tt.cable_m))}</span>`,
    sm.error ? `<span class="doc-chip doc-error">${_cbE(_cbT('{0} error(s)', sm.error))}</span>` : '',
    sm.warning ? `<span class="doc-chip doc-warning">${_cbE(_cbT('{0} warning(s)', sm.warning))}</span>` : '',
  ].join(' ');
  const chips = _cb.plan.chains.length
    ? [_cbE(_cbT('{0} m of cable', tt.cable_m)), _cbE(_cbT('{0} chains', tt.chains)),
       sm.error ? _cbE(_cbT('{0} error(s)', sm.error)) : _cbE(_cbT('no errors'))]
    : [_cbE(_cbT('no chains yet'))];
  setOutcome('cabling', chips, sm.error ? 'warn' : (_cb.plan.chains.length ? 'ok' : ''), 'The plan:');
}

// ── 1 · Kit ──────────────────────────────────────────────────────────────────
function _cbItemText(it) {
  if (it.kind === 'cable') return `${CB_CONN[it.a.conn]} · ${it.length} m${it.type === 'mic' ? ' · ' + _cbT('microphone') : ''}`;
  if (it.kind === 'adapter') return `${CB_CONN[it.a.conn]}${_cbG(it.a.gender)} → ${CB_CONN[it.b.conn]}${_cbG(it.b.gender)}`;
  if (it.kind === 'terminator') return `${CB_CONN[it.plug.conn]}${_cbG(it.plug.gender)} · 120 Ω`;
  const ports = it.ports || [];
  const outs = ports.filter(p => p.role === 'out');
  const by = r => ports.filter(p => p.role === r).map(p => CB_CONN[p.conn] + _cbG(p.gender)).join(', ');
  return [by('in') && `${_cbT('in')} ${by('in')}`, by('thru') && `${_cbT('thru')} ${by('thru')}`,
          outs.length && `${outs.length} × ${_cbT('out')} ${CB_CONN[outs[0].conn]}${_cbG(outs[0].gender)}`].filter(Boolean).join(' · ');
}

function _cbKit() {
  const inv = _cb.plan.tonight.items;
  const el = document.getElementById('cb-kit');
  const order = Object.keys(CB_KIND);
  const rows = inv.map((it, i) => ({ it, i })).sort((a, b) => order.indexOf(a.it.kind) - order.indexOf(b.it.kind)
    || (a.it.length || 0) - (b.it.length || 0) || a.it.name.localeCompare(b.it.name));
  el.innerHTML = inv.length ? `<table class="cb-table"><thead><tr><th>${_cbE(_cbT('Item'))}</th><th>${_cbE(_cbT('Sockets'))}</th>
    <th>${_cbE(_cbT('Count'))}</th><th>${_cbE(_cbT('Whose'))}</th><th></th></tr></thead><tbody>` + rows.map(({ it, i }) => `
    <tr class="${it.count < 1 ? 'cb-zero' : ''}">
      <td><span class="cb-kind">${_cbE(_cbT(CB_KIND[it.kind]))}</span> <span data-i18n="off">${_cbE(it.name)}</span>
        ${['splitter', 'node', 'fixture'].includes(it.kind) ? `<select class="field-input cb-term" onchange="cablingItem(${i}, 'termination', this.value)">${Object.entries(CB_TERM).map(([k, v]) =>
          `<option value="${k}"${(it.termination || 'unknown') === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}</select>` : ''}</td>
      <td class="cb-dim">${_cbE(_cbItemText(it))}</td>
      <td class="cb-count"><button class="btn btn-surface btn-sm" onclick="cablingItem(${i}, 'count', ${it.count - 1})" aria-label="${_cbE(_cbT('One less'))}">−</button>
        <span>${it.count}</span><button class="btn btn-surface btn-sm" onclick="cablingItem(${i}, 'count', ${it.count + 1})" aria-label="${_cbE(_cbT('One more'))}">+</button></td>
      <td><select class="field-input cb-narrow" onchange="cablingItem(${i}, 'owner', this.value)">${Object.entries(CB_OWNERS).map(([k, v]) =>
          `<option value="${k}"${(it.owner || 'mine') === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}</select></td>
      <td><button class="btn btn-surface btn-sm" onclick="cablingItemRemove(${i})" title="${_cbE(_cbT('Remove from tonight'))}">✕</button></td>
    </tr>`).join('') + '</tbody></table>'
    : `<div class="porter-placeholder">${_cbE(_cbT('Tonight\'s kit is empty. Add your interface, splitter, cables, adapters and terminators below, then keep it as your kit.'))}</div>`;
  const sel = document.getElementById('cb-preset');
  if (sel && !sel.options.length) {
    sel.innerHTML = (_cb.presets || []).filter(p => p.item.kind !== 'cable').map(p =>
      `<option value="${_cbE(p.id)}">${_cbE(_cbT(CB_KIND[p.item.kind]))}: ${_cbE(p.item.name)}</option>`).join('');
  }
  // found in the show
  const f = document.getElementById('cb-found');
  f.innerHTML = (_cb.found || []).length ? _cb.found.map((g, k) => `<div class="cb-card cb-found">
      <div class="cb-found-h"><b data-i18n="off">${g.ids.length} × ${_cbE(g.manufacturer)} ${_cbE(g.model)}</b></div>
      <div class="cb-dim" data-i18n="off">${_cbE(g.names.join(', '))}</div>
      <div class="cb-dim">${_cbE(g.reason === 'count' ? _cbT('More than your kit has of this model.') : _cbT('Not in your kit.'))}</div>
      <div class="cb-actions">
        <button class="btn btn-surface btn-sm" onclick="cablingFound(${k}, 'venue')">${_cbE(_cbT('Venue'))}</button>
        <button class="btn btn-surface btn-sm" onclick="cablingFound(${k}, 'borrowed')">${_cbE(_cbT('Borrowed'))}</button>
        <button class="btn btn-surface btn-sm" onclick="cablingFound(${k}, 'mine')">${_cbE(_cbT('Add to my kit'))}</button>
        <button class="btn btn-surface btn-sm" onclick="cablingAskClaude(${k})">${_cbE(_cbT('Ask Claude…'))}</button>
      </div></div>`).join('')
    : `<div class="cb-card cb-dim">${_cbE(_cbT('Every fixture of the show is in tonight\'s kit or has an owner.'))}</div>`;
  // owners
  const counts = { mine: 0, borrowed: 0, venue: 0, none: 0 };
  _cb.evaluation.fixtures.forEach(x => { counts[x.owner || 'none'] += 1; });
  document.getElementById('cb-owners').innerHTML = `<div class="cb-dim">${_cbE(_cbT('Mine {0} · borrowed {1} · venue {2} · not in the kit {3}',
    counts.mine, counts.borrowed, counts.venue, counts.none))}</div>` + _cb.evaluation.fixtures.map(x => `
    <div class="cb-row cb-fx"><span data-i18n="off" title="${_cbE(x.manufacturer + ' ' + x.model)}">${_cbE(x.name)}</span>
      <select class="field-input cb-narrow" onchange="cablingOwner('${x.id}', this.value)">
        <option value=""${!_cb.plan.owners[x.id] ? ' selected' : ''}>${_cbE(_cbT('From the kit'))}</option>
        ${Object.entries(CB_OWNERS).map(([k, v]) => `<option value="${k}"${_cb.plan.owners[x.id] === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}
      </select></div>`).join('');
}

function cablingItem(i, key, value) {
  const it = _cb.plan.tonight.items[i];
  if (!it) return;
  if (key === 'count') value = Math.max(0, Math.min(999, value));
  it[key] = value;
  _cbChanged();
}

function cablingItemRemove(i) {
  const it = _cb.plan.tonight.items[i];
  if (!it) return;
  _cb.plan.tonight.items.splice(i, 1);
  _cb.plan.chains = _cb.plan.chains.filter(c => c.source.item !== it.id)
    .map(c => ({ ...c, devices: c.devices.filter(d => d.item !== it.id), cables: [] }));
  delete _cb.plan.places[it.id];
  _cbChanged();
}

function _cbNewId(kind) {
  const used = new Set(_cb.plan.tonight.items.map(x => x.id));
  let n = 1;
  while (used.has(kind + n)) n += 1;
  return kind + n;
}

function cablingAddPreset() {
  const id = document.getElementById('cb-preset').value;
  const p = (_cb.presets || []).find(x => x.id === id);
  if (!p) return;
  const same = _cb.plan.tonight.items.find(x => x.name === p.item.name && x.kind === p.item.kind);
  if (same) same.count += 1;
  else _cb.plan.tonight.items.push({ ...JSON.parse(JSON.stringify(p.item)), id: _cbNewId(p.item.kind), owner: 'mine' });
  _cbChanged();
}

function cablingAddCable() {
  const conn = document.getElementById('cb-cab-conn').value;
  const length = Math.round(parseFloat(document.getElementById('cb-cab-len').value) * 100) / 100;
  const n = parseInt(document.getElementById('cb-cab-n').value, 10) || 1;
  const type = document.getElementById('cb-cab-type').value;
  if (!(length >= 0.1 && length <= 500)) { setStatus(_cbT('A cable is 0.1 to 500 m long.'), 'warn'); return; }
  const name = `${CB_CONN[conn]} ${type === 'mic' ? 'mic' : 'DMX'} cable ${length} m`;
  const same = _cb.plan.tonight.items.find(x => x.kind === 'cable' && x.a.conn === conn && x.length === length && (x.type || 'dmx') === type);
  if (same) same.count += n;
  else _cb.plan.tonight.items.push({ kind: 'cable', id: _cbNewId('cable'), name, a: { conn, gender: 'm' }, b: { conn, gender: 'f' },
    length, type, count: n, owner: 'mine' });
  _cbChanged();
}

async function cablingSaveBase() {
  const items = _cb.plan.tonight.items.filter(x => x.owner !== 'venue' && x.count > 0)
    .map(x => { const c = { ...x }; delete c.owner; return c; });
  const r = await fetch('/api/cabling/kit', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kit: { items } }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || _cbT('Could not keep your kit.'), 'error'); return; }
  _cb.base = d.kit;
  setStatus(_cbT('Your kit has {0} items now, for every show.', d.kit.items.length), 'ok');
}

function cablingFromBase() {
  if (!_cb.base || !_cb.base.items.length) { setStatus(_cbT('Your kit is empty: keep tonight\'s kit as your kit first.'), 'warn'); return; }
  if (!confirm(_cbT('Tonight\'s kit becomes a copy of your kit again; the chains are cleared. Go on?'))) return;
  _cb.plan.tonight = { version: 1, items: _cb.base.items.map(x => ({ ...x, owner: 'mine' })) };
  _cb.plan.chains = [];
  _cbAlts = null;
  _cbChanged();
}

function cablingOwner(fid, owner) {
  if (owner) _cb.plan.owners[fid] = owner; else delete _cb.plan.owners[fid];
  _cbChanged();
}

function cablingFound(k, owner) {
  const g = (_cb.found || [])[k];
  if (!g) return;
  if (owner === 'mine') {
    const fx = _cb.rig.fixtures.find(x => x.id === g.ids[0]) || { conns: ['xlr3'] };
    const ports = fx.conns.map(c => ({ role: 'in', conn: c, gender: 'm', name: 'DMX IN' }))
      .concat(fx.conns.map(c => ({ role: 'thru', conn: c, gender: 'f', name: 'DMX THRU' })));
    _cb.plan.tonight.items.push({ kind: 'fixture', id: _cbNewId('fixture'), name: `${g.manufacturer} ${g.model}`.trim(),
      manufacturer: g.manufacturer, model: g.model, ports, termination: 'unknown', count: g.ids.length, owner: 'mine' });
  } else {
    g.ids.forEach(id => { _cb.plan.owners[id] = owner; });
  }
  _cb.found.splice(k, 1);
  _cbChanged();
}

async function cablingAskClaude(k) {
  const g = (_cb.found || [])[k] || {};
  const card = document.getElementById('cb-claude-card');
  if (!card) return;
  card.hidden = false;
  const st = document.getElementById('cb-claude-status');
  try {
    const s = await (await fetch('/api/mcp/status')).json();
    st.textContent = (s.last_start || s.extension || s.config) ? ''
      : _cbT('Not connected yet: use 🔌 Connect to Claude in the left menu first.');
  } catch { st.textContent = ''; }
  const r = await _apiJson('/api/mcp/fixture-request', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manufacturer: g.manufacturer || '', model: g.model || '' }),
  });
  document.getElementById('cb-claude-text').textContent = r.error ? r.error : r.text;
}

// ── 2 · Places ───────────────────────────────────────────────────────────────
function cablingPlaceMode(m) { _cbPick = m; _cbCorner = null; _cbPlaces(); }

function _cbStageBox() {
  const st = _cb.rig.stage, ctl = _cb.evaluation.controller;
  const x0 = Math.min(-2000, ctl.x - 800), x1 = Math.max(st.w + 2000, ctl.x + 800);
  const z0 = Math.min(-1000, ctl.z - 800), z1 = Math.max(st.d + 1500, ctl.z + 800);
  return { x0, z0, x1, z1 };
}

function _cbStageSvg(clickable) {
  const st = _cb.rig.stage, b = _cbStageBox(), p = _cb.plan, ev = _cb.evaluation;
  const parts = [`<svg viewBox="${b.x0} ${b.z0} ${b.x1 - b.x0} ${b.z1 - b.z0}" class="cb-svg" role="img" aria-label="${_cbE(_cbT('The stage from above'))}"
    ${clickable ? 'onclick="cablingStageClick(event)"' : ''}>`];
  parts.push(`<rect x="0" y="0" width="${st.w}" height="${st.d}" class="cb-s-stage"/>`);
  parts.push(`<text x="${st.w / 2}" y="${st.d + 700}" class="cb-s-lbl" text-anchor="middle">${_cbE(_cbT('AUDIENCE'))}</text>`);
  _cb.rig.keep_out.forEach(k => parts.push(`<rect x="${k.x0}" y="${k.z0}" width="${k.x1 - k.x0}" height="${k.z1 - k.z0}" class="cb-s-keep"/>`));
  (p.walkways || []).forEach(w => parts.push(`<rect x="${w.x0}" y="${w.z0}" width="${w.x1 - w.x0}" height="${w.z1 - w.z0}" class="cb-s-walk${w.ramp ? ' ramp' : ''}"/>`));
  (ev.trusses || []).forEach(tr => parts.push(`<line x1="${tr.x0 - 200}" y1="${tr.z}" x2="${tr.x1 + 200}" y2="${tr.z}" class="cb-s-truss"/>`));
  ev.fixtures.forEach(f => {
    if (!f.place) return;
    parts.push(`<circle cx="${f.place.x}" cy="${f.place.z}" r="150" class="cb-s-fx${f.owner === 'venue' ? ' venue' : ''}${f.patched === false ? ' extra' : ''}"><title>${_cbE(f.name)}</title></circle>`);
  });
  (p.outlets || []).forEach(o => parts.push(`<rect x="${o.x - 120}" y="${o.z - 120}" width="240" height="240" class="cb-s-outlet"><title>${_cbE(_cbT('Power outlet'))}</title></rect>`));
  Object.entries(p.places || {}).forEach(([id, q]) => {
    if (id === 'controller') return;
    const it = p.tonight.items.find(x => x.id === id);
    parts.push(`<rect x="${q.x - 250}" y="${q.z - 150}" width="500" height="300" class="cb-s-split"><title>${_cbE(it ? it.name : id)}</title></rect>`);
  });
  const c = ev.controller;
  parts.push(`<rect x="${c.x - 300}" y="${c.z - 200}" width="600" height="400" class="cb-s-ctl"><title>${_cbE(_cbT('Computer'))}</title></rect>`);
  if (_cbCorner) parts.push(`<circle cx="${_cbCorner.x}" cy="${_cbCorner.z}" r="90" class="cb-s-corner"/>`);
  parts.push('</svg>');
  return parts.join('');
}

function _cbPlaces() {
  document.querySelectorAll('#cb-place-mode button').forEach(bt => bt.classList.toggle('on', bt.dataset.v === _cbPick));
  document.getElementById('cb-places').innerHTML = _cbStageSvg(true);
  const c = _cb.plan.controller;
  document.querySelectorAll('input[name="cb-ctl"]').forEach(r => { r.checked = r.value === c.mode; });
  const set = (id, v) => { const e = document.getElementById(id); if (e && document.activeElement !== e) e.value = v; };
  set('cb-side-sel', c.side); set('cb-foh-d', c.distance_m); set('cb-foh-route', c.route); set('cb-slack', _cb.plan.slack_m);
  const p = _cb.plan, items = Object.fromEntries(p.tonight.items.map(x => [x.id, x]));
  const rows = [];
  Object.entries(p.places || {}).forEach(([id, q]) => rows.push(`<div class="cb-row"><span>${_cbE(id === 'controller' ? _cbT('Computer') : (items[id] || {}).name || id)}</span>
    <span class="cb-dim">${(q.x / 1000).toFixed(1)} / ${(q.z / 1000).toFixed(1)} m</span><button class="btn btn-surface btn-sm" onclick="cablingClearPlace('${id}')">✕</button></div>`));
  (p.walkways || []).forEach((w, i) => rows.push(`<div class="cb-row"><span>${_cbE(_cbT('Walkway'))} ${i + 1}</span>
    <label class="cb-check"><input type="checkbox" ${w.ramp ? 'checked' : ''} onchange="cablingWalk(${i}, 'ramp', this.checked)"> ${_cbE(_cbT('cable ramp'))}</label>
    <button class="btn btn-surface btn-sm" onclick="cablingWalk(${i}, 'remove')">✕</button></div>`));
  (p.outlets || []).forEach((o, i) => rows.push(`<div class="cb-row"><span>${_cbE(_cbT('Outlet'))} ${i + 1}</span>
    <span class="cb-dim">${(o.x / 1000).toFixed(1)} / ${(o.z / 1000).toFixed(1)} m</span><button class="btn btn-surface btn-sm" onclick="cablingOutlet(${i})">✕</button></div>`));
  (p.extras || []).forEach((x, i) => rows.push(`<div class="cb-row"><span data-i18n="off">${_cbE(x.name)}</span>
    <button class="btn btn-surface btn-sm" onclick="go('fixtures')" title="${_cbE(_cbT('Patch it in Fixtures (the show in progress)'))}">${_cbE(_cbT('Patch it…'))}</button>
    <button class="btn btn-surface btn-sm" onclick="cablingExtra(${i})">✕</button></div>`));
  document.getElementById('cb-floor-list').innerHTML = rows.join('')
    || `<div class="cb-dim">${_cbE(_cbT('Nothing placed by hand yet: the computer stands where the setting says, the splitter is placed by the plan.'))}</div>`;
}

function cablingStageClick(ev) {
  const svg = ev.currentTarget;
  const pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  const q = pt.matrixTransform(svg.getScreenCTM().inverse());
  const x = Math.round(q.x / 50) * 50, z = Math.round(q.y / 50) * 50;
  const p = _cb.plan;
  if (_cbPick === 'controller') p.places.controller = { x, z };
  else if (_cbPick === 'splitter') {
    const sp = p.tonight.items.find(i => i.kind === 'splitter' && i.count > 0) || p.tonight.items.find(i => i.kind === 'node' && i.count > 0);
    if (!sp) { setStatus(_cbT('Tonight\'s kit has no splitter or node to place.'), 'warn'); return; }
    p.places[sp.id] = { x, z, h: 0 };
  } else if (_cbPick === 'outlet') p.outlets.push({ x, z });
  else if (_cbPick === 'walkway') {
    if (!_cbCorner) { _cbCorner = { x, z }; _cbPlaces(); return; }
    p.walkways.push({ x0: _cbCorner.x, z0: _cbCorner.z, x1: x, z1: z, ramp: false, label: '' });
    _cbCorner = null;
  } else if (_cbPick === 'extra') {
    const name = prompt(_cbT('Name of the fixture found here:'), '');
    if (!name) return;
    const model = prompt(_cbT('Manufacturer and model (for the kit; may stay empty):'), '') || '';
    p.extras.push({ id: '', name: name.trim(), manufacturer: '', model: model.trim(), x, z, h: 0, universe: '0', connector: '' });
  }
  _cbChanged();
}

function cablingClearPlace(id) { delete _cb.plan.places[id]; _cbChanged(); }
function cablingWalk(i, key, v) {
  if (key === 'remove') _cb.plan.walkways.splice(i, 1); else _cb.plan.walkways[i][key] = v;
  _cbChanged();
}
function cablingOutlet(i) { _cb.plan.outlets.splice(i, 1); _cbChanged(); }
function cablingExtra(i) {
  const id = _cb.plan.extras[i] && _cb.plan.extras[i].id;
  _cb.plan.extras.splice(i, 1);
  _cb.plan.chains.forEach(c => { c.devices = c.devices.filter(d => d.fixture !== id); c.cables = []; });
  _cbChanged();
}
function cablingCtl(key, value) { _cb.plan.controller[key] = value; _cbAlts = null; _cbChanged(); }
function cablingSet(key, value) { _cb.plan[key] = value; _cbChanged(); }

// ── 3 · Plan ─────────────────────────────────────────────────────────────────
async function cablingPropose() {
  if (!_cb) return;
  const el = document.getElementById('cb-alts');
  if (el) el.innerHTML = `<div class="porter-placeholder">${_cbE(_cbT('Working out the alternatives…'))}</div>`;
  try {
    const r = await fetch('/api/cabling/auto', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: _cb.plan }) });
    const d = await r.json();
    if (!r.ok) { setStatus(d.error || _cbT('No alternatives.'), 'warn'); _cbAlts = []; _cbRender(); return; }
    _cbAlts = d.alternatives;
    if (_cbAlts.length && !_cb.plan.chains.length) cablingPickAlt(0);
    else _cbRender();
  } catch (e) { setStatus(_cbT('No alternatives.'), 'error'); }
}

function cablingPickAlt(k) {
  const a = (_cbAlts || [])[k];
  if (!a) return;
  _cb.plan = JSON.parse(JSON.stringify(a.plan));
  Object.assign(_cb, { evaluation: a.evaluation, svg: a.svg });
  _cbAlts.forEach((x, i) => { x.chosen = i === k; });
  _cbChanged();
}

function _cbPlan() {
  const al = document.getElementById('cb-alts');
  if (_cbAlts) al.innerHTML = _cbAlts.length ? _cbAlts.map((a, k) => `
    <button class="cb-alt${a.chosen ? ' on' : ''}" onclick="cablingPickAlt(${k})">
      <div class="cb-alt-h"><b>${a.key}</b> ${_cbE(_cbT(a.name))}${a.best ? ` <span class="cb-best">${_cbE(_cbT('SUGGESTED'))}</span>` : ''}</div>
      <div class="cb-dim">${_cbE(_cbT(a.note || ''))}</div>
      <div class="cb-alt-n"><span>${_cbE(_cbT('Cable'))}</span><b>${a.cable_m} m</b><span>${_cbE(_cbT('Longest hop'))}</span><b>${a.longest_m} m</b>
        <span>${_cbE(_cbT('Crossings'))}</span><b>${a.crossings}</b><span>${_cbE(_cbT('Adapters'))}</span><b>${a.adapters}</b></div>
      <div class="${a.missing.length ? 'cb-bad' : 'cb-good'}">${a.missing.length
        ? _cbE(_cbT('Missing: {0}', a.missing.map(m => `${m.count} × ${m.what}`).join(', '))) : _cbE(_cbT('Nothing missing'))}</div>
    </button>`).join('') : `<div class="porter-placeholder">${_cbE(_cbT('No alternative: the show has no fixtures.'))}</div>`;
  document.getElementById('cb-plot').innerHTML = _cb.plan.chains.length ? (_cb.svg || '')
    : `<div class="porter-placeholder">${_cbE(_cbT('No chains yet: ✨ Propose, or start a chain by hand.'))}</div>`;
  const tt = _cb.evaluation.totals;
  document.getElementById('cb-plan-totals').textContent = _cb.plan.chains.length
    ? _cbT('{0} m of cable · longest hop {1} m · {2} adapter(s)', tt.cable_m, tt.longest_m, tt.adapters) : '';
  const ev = _cb.evaluation, p = _cb.plan;
  const byN = Object.fromEntries(ev.chains.map(w => [w.n, w]));
  const names = Object.fromEntries(ev.fixtures.map(f => [f.id, f.name]));
  const items = Object.fromEntries(p.tonight.items.map(x => [x.id, x]));
  const opts = n => p.chains.map((c, m) => m === n ? '' : `<option value="${m}">${_cbE(_cbT('to chain {0}', m + 1))}</option>`).join('');
  const html = p.chains.map((c, n) => {
    const w = byN[n] || { links: [], issues: [], name: '?' };
    const col = w.colour || 'var(--accent)';
    const rows = c.devices.map((d, i) => {
      const l = w.links[i] || {};
      const nm = d.fixture != null ? (names[d.fixture] || d.fixture) : ((items[d.item] || {}).name || d.item);
      const cab = (l.cables || []).map(x => `${x.length} m`).join(' + ') || (l.missing_m ? _cbT('missing {0} m', l.missing_m) : '');
      return `<div class="cb-link"><span class="cb-n">${i + 1}</span><span class="cb-to" data-i18n="off">${_cbE(nm)}</span>
        <span class="cb-dim">${_cbE(cab)}</span>
        <button class="btn btn-surface btn-sm" onclick="cablingDev(${n}, ${i}, -1)" ${i === 0 ? 'disabled' : ''} title="${_cbE(_cbT('Earlier'))}">↑</button>
        <button class="btn btn-surface btn-sm" onclick="cablingDev(${n}, ${i}, 1)" ${i === c.devices.length - 1 ? 'disabled' : ''} title="${_cbE(_cbT('Later'))}">↓</button>
        <select class="field-input cb-move" onchange="cablingMove(${n}, ${i}, this.value)"><option value="">${_cbE(_cbT('move…'))}</option>${opts(n)}<option value="x">${_cbE(_cbT('off the chain'))}</option></select></div>`;
    }).join('');
    const iss = (w.issues || []).filter(x => x.severity !== 'info').map(x => `<div class="cb-iss sev-${x.severity}"><b>${x.code}</b> ${_cbE(x.text)}</div>`).join('');
    return `<div class="cb-chain" style="border-left-color:${_cbE(col)}">
      <div class="cb-chain-h"><b data-i18n="off">${n + 1}. ${_cbE(c.label || w.name)}</b><span class="cb-dim">${w.total_m != null ? w.total_m + ' m' : ''}</span>
        <button class="btn btn-surface btn-sm" onclick="cablingChainRemove(${n})" title="${_cbE(_cbT('Remove the chain'))}">✕</button></div>${rows}${iss}</div>`;
  }).join('');
  const on = new Set(p.chains.flatMap(c => c.devices.filter(d => d.fixture != null).map(d => String(d.fixture))));
  const off = ev.fixtures.filter(f => !on.has(String(f.id)));
  const offHtml = off.length && p.chains.length ? `<div class="cb-card"><div class="cb-dim">${_cbE(_cbT('Not on a chain'))}</div>` + off.map(f => `
    <div class="cb-row"><span data-i18n="off">${_cbE(f.name)}</span><select class="field-input cb-move" onchange="cablingAddTo('${f.id}', this.value)">
      <option value="">${_cbE(_cbT('add…'))}</option>${p.chains.map((c, m) => `<option value="${m}">${_cbE(_cbT('to chain {0}', m + 1))}</option>`).join('')}</select></div>`).join('') + '</div>' : '';
  document.getElementById('cb-chains').innerHTML = (html || `<div class="porter-placeholder">${_cbE(_cbT('No chains yet.'))}</div>`) + offHtml;
  const src = document.getElementById('cb-new-src');
  src.innerHTML = p.tonight.items.filter(x => ['interface', 'splitter', 'node', 'wireless_rx'].includes(x.kind)).flatMap(x => {
    const ports = (x.ports || []).filter(q => q.role === 'out' || q.role === 'thru');
    return ports.map((q, k) => q.role === 'out'
      ? `<option value="${_cbE(x.id)}|${k}" data-i18n="off">${_cbE(x.name)} · ${_cbE(q.name || 'out ' + (k + 1))}</option>` : '');
  }).join('');
}

function cablingDev(n, i, delta) {
  const L = _cb.plan.chains[n].devices, j = i + delta;
  if (j < 0 || j >= L.length) return;
  [L[i], L[j]] = [L[j], L[i]];
  _cb.plan.chains[n].cables = [];
  _cbChanged();
}

function cablingMove(n, i, to) {
  if (to === '') return;
  const d = _cb.plan.chains[n].devices.splice(i, 1)[0];
  _cb.plan.chains[n].cables = [];
  if (to !== 'x') { _cb.plan.chains[+to].devices.push(d); _cb.plan.chains[+to].cables = []; }
  _cbChanged();
}

function cablingAddTo(fid, to) {
  if (to === '') return;
  _cb.plan.chains[+to].devices.push({ fixture: String(fid) });
  _cbChanged();
}

function cablingChainRemove(n) { _cb.plan.chains.splice(n, 1); _cbChanged(); }

function cablingNewChain() {
  const v = document.getElementById('cb-new-src').value;
  if (!v) return;
  const [item, port] = v.split('|');
  _cb.plan.chains.push({ source: { item, port: +port }, devices: [], cables: [], label: '' });
  _cbChanged();
}

// ── 4 · Check and export ────────────────────────────────────────────────────
function _cbCheck() {
  const ev = _cb.evaluation;
  const all = ev.chains.flatMap(w => w.issues.map(i => ({ ...i, chain: w.name }))).concat(ev.issues);
  const rank = { error: 0, warning: 1, info: 2 };
  all.sort((a, b) => rank[a.severity] - rank[b.severity] || a.code.localeCompare(b.code));
  document.getElementById('cb-checks').innerHTML = all.length ? all.map(i => `<div class="cb-check-row sev-${i.severity}">
      <span class="cb-code">${i.code}</span><div><div>${_cbE(i.text)}</div>${i.fix ? `<div class="cb-dim">${_cbE(i.fix)}</div>` : ''}</div></div>`).join('')
    : `<div class="cb-card cb-good">${_cbE(_cbT('Nothing to fix.'))}</div>`;
  document.getElementById('cb-loadin').innerHTML = (_cb.load_in || []).map(s => `<li data-i18n="off">${_cbE(s)}</li>`).join('');
  const pk = _cb.pick || { bag: [], spares: [], buy: [] };
  const sec = (title, rows) => rows.length ? `<div class="cb-dim">${_cbE(_cbT(title))}</div><ul class="cb-pick">${rows.map(r =>
    `<li data-i18n="off">${r.count} × ${_cbE(r.what)}</li>`).join('')}</ul>` : '';
  document.getElementById('cb-pick').innerHTML = (sec('In the bag', pk.bag) + sec('Spares', pk.spares) + sec('To buy', pk.buy))
    || `<div class="cb-dim">${_cbE(_cbT('Make a plan first.'))}</div>`;
}

async function cablingExport(what) {
  if (!_cb || !_cb.plan.chains.length) { setStatus(_cbT('Make a plan first.'), 'warn'); return; }
  try {
    const r = await fetch('/api/cabling/export', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: _cb.plan, what }) });
    if (!r.ok) { const d = await r.json().catch(() => ({})); setStatus(d.error || _cbT('Export failed.'), 'error'); return; }
    const blob = await r.blob();
    const name = r.headers.get('X-Suggested-Filename') || 'cabling';
    const saved = await saveFileWithPicker(blob, name, null, _cbT('Save the file'));
    if (saved) { setStatus(_cbT('Saved: {0}', saved), 'ok'); _cbSave(); }
  } catch (e) { setStatus(_cbT('Export failed.'), 'error'); }
}
