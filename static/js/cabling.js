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
const CB_TERM = { none: 'No switch: needs a terminator plug', switch: 'Has a termination switch',
  auto: 'Terminates by itself (built in)', unknown: 'Not sure' };
let _cbBase = null;           // /api/cabling/kit: your kit (every show), where it is kept, presets
let _cbKitModeV = 'tonight';  // Kit step: tonight's kit or my kit
let _cbBaseT = null, _cbFxT = null;

const _cbE = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const _cbT = (s, ...v) => (typeof t === 'function' ? t(s, ...v) : s.replace(/\{(\d+)\}/g, (_x, i) => v[+i] ?? ''));
const _cbG = g => (g === 'm' ? '♂' : g === 'f' ? '♀' : '');
const CB_FT = 0.3048;
// lengths are kept in metres; shown in the unit of your kit (My kit › Lengths in)
const _cbUnits = () => (_cbBase && _cbBase.kit && _cbBase.kit.units) || 'm';
function _cbNum(m) {                           // metres → a number in the user's unit
  if (_cbUnits() !== 'ft') return Math.round(m * 100) / 100;
  const ft = m / CB_FT;
  return ft >= 10 || Math.abs(ft - Math.round(ft)) < 0.05 ? Math.round(ft) : Math.round(ft * 10) / 10;
}
const _cbLen = m => `${_cbNum(m)} ${_cbUnits()}`;
const _cbToM = v => Math.round((_cbUnits() === 'ft' ? +v * CB_FT : +v) * 100) / 100;

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
  try { _cbBase = await (await fetch('/api/cabling/kit')).json(); } catch (e) { _cbBase = null; }
  _cbRender();
}

// ── keeping and checking ─────────────────────────────────────────────────────
let _cbEdits = 0, _cbBaseEdits = 0;   // edits since a request left: its answer must not undo them

function _cbChanged(redraw = true) {
  _cbEdits += 1;
  if (redraw) _cbRender();
  clearTimeout(_cbEvalT);
  _cbEvalT = setTimeout(_cbEvaluate, 200);
  clearTimeout(_cbSaveT);
  _cbSaveT = setTimeout(_cbSave, 600);
}

async function _cbEvaluate() {
  if (!_cb) return;
  const sent = _cbEdits;
  try {
    const r = await fetch('/api/cabling/evaluate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan: _cb.plan }),
    });
    const d = await r.json();
    if (!r.ok) return;
    if (sent !== _cbEdits) return;           // changed meanwhile: the next answer is the one to show
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
  _cbUnitLabels();
  if (!_cb) {                                  // no show: only your kit can be edited
    _cbStepN = 0;
    CB_STEPS.forEach((_s, i) => { const el = document.getElementById('cb-step-' + i); if (el) el.hidden = i !== 0; });
    if (next) next.hidden = true;
    _cbKitModeV = 'mine';
    const s = document.getElementById('cb-summary');
    if (s) s.innerHTML = `<span class="doc-chip">${_cbE(_cbT('Open a show to plan its cables; your kit can be edited now.'))}</span>`;
    if (typeof setOutcome === 'function') setOutcome('cabling', '');
    _cbKitView();
    return;
  }
  _cbSummary();
  if (_cbStepN === 0) _cbKitView();
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
    `<span class="doc-chip">${_cbE(_cbT('{0} of cable', _cbLen(tt.cable_m)))}</span>`,
    sm.error ? `<span class="doc-chip doc-error">${_cbE(_cbT('{0} error(s)', sm.error))}</span>` : '',
    sm.warning ? `<span class="doc-chip doc-warning">${_cbE(_cbT('{0} warning(s)', sm.warning))}</span>` : '',
  ].join(' ');
  const chips = _cb.plan.chains.length
    ? [_cbE(_cbT('{0} of cable', _cbLen(tt.cable_m))), _cbE(_cbT('{0} chains', tt.chains)),
       sm.error ? _cbE(_cbT('{0} error(s)', sm.error)) : _cbE(_cbT('no errors'))]
    : [_cbE(_cbT('no chains yet'))];
  setOutcome('cabling', chips, sm.error ? 'warn' : (_cb.plan.chains.length ? 'ok' : ''), 'The plan:');
}

// ── 1 · Kit ──────────────────────────────────────────────────────────────────
function _cbItemText(it) {
  if (it.kind === 'cable') return `${CB_CONN[it.a.conn]} · ${_cbLen(it.length)}${it.kind === 'cable' && it.type === 'net' ? ' · ' + _cbT('network') : ''}${it.type === 'mic' ? ' · ' + _cbT('microphone') : ''}`;
  if (it.kind === 'adapter') return `${CB_CONN[it.a.conn]}${_cbG(it.a.gender)} → ${CB_CONN[it.b.conn]}${_cbG(it.b.gender)}`;
  if (it.kind === 'terminator') return `${CB_CONN[it.plug.conn]}${_cbG(it.plug.gender)} · 120 Ω`;
  const ports = it.ports || [];
  const outs = ports.filter(p => p.role === 'out');
  const by = r => ports.filter(p => p.role === r).map(p => CB_CONN[p.conn] + _cbG(p.gender)).join(', ');
  return [by('in') && `${_cbT('in')} ${by('in')}`, by('thru') && `${_cbT('thru')} ${by('thru')}`,
          outs.length && `${outs.length} × ${_cbT('out')} ${CB_CONN[outs[0].conn]}${_cbG(outs[0].gender)}`].filter(Boolean).join(' · ');
}

function _cbTable(inv, w) {
  const order = Object.keys(CB_KIND);
  const rows = inv.map((it, i) => ({ it, i })).sort((a, b) => order.indexOf(a.it.kind) - order.indexOf(b.it.kind)
    || (a.it.length || 0) - (b.it.length || 0) || a.it.name.localeCompare(b.it.name));
  const mine = w === 'm';
  return `<table class="cb-table"><thead><tr><th>${_cbE(_cbT('Item'))}</th><th>${_cbE(_cbT('Sockets'))}</th>
    <th>${_cbE(_cbT('Count'))}</th>${mine ? '' : `<th>${_cbE(_cbT('Whose'))}</th>`}<th></th></tr></thead><tbody>` + rows.map(({ it, i }) => `
    <tr class="${it.count < 1 ? 'cb-zero' : ''}">
      <td><span class="cb-kind">${_cbE(_cbT(CB_KIND[it.kind]))}</span> <span data-i18n="off">${_cbE(it.name)}</span>
        ${['splitter', 'node', 'fixture'].includes(it.kind) ? `<select class="field-input cb-term" title="${_cbE(_cbT('How the end of a DMX line is terminated at this device (see Termination below)'))}" onchange="cablingItem(${i}, 'termination', this.value, '${w}')">${Object.entries(CB_TERM).map(([k, v]) =>
          `<option value="${k}"${(it.termination || 'unknown') === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}</select>` : ''}</td>
      <td class="cb-dim">${_cbE(_cbItemText(it))}${it.kind === 'fixture' && it.power ? ' · ' + _cbE(it.power) : ''}</td>
      <td class="cb-count"><button class="btn btn-surface btn-sm" onclick="cablingItem(${i}, 'count', ${it.count - 1}, '${w}')" aria-label="${_cbE(_cbT('One less'))}">−</button>
        <span>${it.count}</span><button class="btn btn-surface btn-sm" onclick="cablingItem(${i}, 'count', ${it.count + 1}, '${w}')" aria-label="${_cbE(_cbT('One more'))}">+</button></td>
      ${mine ? '' : `<td><select class="field-input cb-narrow" onchange="cablingItem(${i}, 'owner', this.value)">${Object.entries(CB_OWNERS).map(([k, v]) =>
          `<option value="${k}"${(it.owner || 'mine') === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}</select></td>`}
      <td><button class="btn btn-surface btn-sm" onclick="cablingItemRemove(${i}, '${w}')" title="${_cbE(_cbT(mine ? 'Remove from my kit' : 'Remove from tonight'))}">✕</button></td>
    </tr>`).join('') + '</tbody></table>';
}

function _cbPresetOptions(sel, presets) {
  if (sel && !sel.options.length) {
    sel.innerHTML = (presets || []).filter(p => p.item.kind !== 'cable').map(p =>
      `<option value="${_cbE(p.id)}">${_cbE(_cbT(CB_KIND[p.item.kind]))}: ${_cbE(p.item.name)}</option>`).join('');
  }
}

function cablingKitMode(m) {
  if (m === 'tonight' && !_cb) { setStatus(_cbT('Open a show first: tonight\'s kit belongs to a show.'), 'warn'); return; }
  _cbKitModeV = m;
  _cbKitView();
}

function _cbKitView() {
  document.querySelectorAll('#cb-kit-mode button').forEach(bt => bt.classList.toggle('on', bt.dataset.v === _cbKitModeV));
  const t = document.getElementById('cb-kit-tonight'), m = document.getElementById('cb-kit-mine');
  if (t) t.hidden = _cbKitModeV !== 'tonight';
  if (m) m.hidden = _cbKitModeV !== 'mine';
  if (_cbKitModeV === 'mine') _cbMyKit(); else _cbKit();
}

function _cbKit() {
  const inv = _cb.plan.tonight.items;
  const el = document.getElementById('cb-kit');
  el.innerHTML = _cbSyncHtml() + (inv.length ? _cbTable(inv, 't')
    : `<div class="porter-placeholder">${_cbE(_cbT('Tonight\'s kit is empty. Add your interface, splitter, cables, adapters and terminators below, then keep it as your kit.'))}</div>`);
  _cbPresetOptions(document.getElementById('cb-preset'), _cb.presets);
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
      <select class="field-input cb-narrow" onchange="cablingOwner('${x.id}', this.value)" title="${_cbE(_cbT('Matched with your kit by manufacturer and model; choose to say otherwise'))}">
        <option value=""${!_cb.plan.owners[x.id] ? ' selected' : ''}>${_cbE(x.item_id && !_cb.plan.owners[x.id] ? _cbT('{0} (in my kit)', _cbT(CB_OWNERS[x.owner] || 'Mine')) : _cbT('Not in my kit'))}</option>
        ${Object.entries(CB_OWNERS).map(([k, v]) => `<option value="${k}"${_cb.plan.owners[x.id] === k ? ' selected' : ''}>${_cbE(_cbT(v))}</option>`).join('')}
      </select></div>`).join('');
}

function cablingItem(i, key, value, w) {
  const it = (w === 'm' ? _cbBase.kit.items : _cb.plan.tonight.items)[i];
  if (!it) return;
  if (key === 'count') value = Math.max(0, Math.min(999, value));
  it[key] = value;
  if (w === 'm') _cbBaseChanged(); else _cbChanged();
}

function cablingItemRemove(i, w) {
  if (w === 'm') { _cbBase.kit.items.splice(i, 1); _cbBaseChanged(); return; }
  const it = _cb.plan.tonight.items[i];
  if (!it) return;
  _cb.plan.tonight.items.splice(i, 1);
  _cb.plan.chains = _cb.plan.chains.filter(c => c.source.item !== it.id)
    .map(c => ({ ...c, devices: c.devices.filter(d => d.item !== it.id), cables: [] }));
  delete _cb.plan.places[it.id];
  _cbChanged();
}

function _cbNewId(kind, w) {
  const used = new Set((w === 'm' ? _cbBase.kit.items : _cb.plan.tonight.items).map(x => x.id));
  let n = 1;
  while (used.has(kind + n)) n += 1;
  return kind + n;
}

// what makes two kit items the same thing: kind, name and every socket with its gender
function _cbSpec(it) {
  const end = e => e ? `${e.conn}${e.gender || ''}` : '';
  const ports = (it.ports || []).map(p => `${p.role}:${end(p)}`).join(',');
  return [it.kind, it.name, end(it.a), end(it.b), end(it.plug), it.length || '', it.type || '', ports].join('|');
}

function _cbAddItem(item, w, n = 1) {
  const items = w === 'm' ? _cbBase.kit.items : _cb.plan.tonight.items;
  const key = _cbSpec(item);
  const same = items.find(x => _cbSpec(x) === key);
  if (same) same.count += n;
  else {
    const it = { ...JSON.parse(JSON.stringify(item)), id: _cbNewId(item.kind, w), count: n };
    if (w !== 'm') it.owner = 'mine'; else delete it.owner;
    items.push(it);
  }
  if (w === 'm') {
    _cbBaseChanged();
    if (_cb && !same) _cbAddItem(item, 't', n);   // tonight gets it as well
  } else _cbChanged();
}

function cablingAddPreset(w) {
  const id = document.getElementById(w === 'm' ? 'cb-preset-m' : 'cb-preset').value;
  const p = ((w === 'm' ? _cbBase : _cb).presets || []).find(x => x.id === id);
  if (p) _cbAddItem(p.item, w);
}

function cablingAddCable(w) {
  const g = id => document.getElementById(id + (w === 'm' ? '-m' : ''));
  const conn = g('cb-cab-conn').value;
  const typed = parseFloat(g('cb-cab-len').value);
  const length = _cbToM(typed);
  const n = parseInt(g('cb-cab-n').value, 10) || 1;
  const type = g('cb-cab-type').value;
  if (!(length >= 0.1 && length <= 500)) { setStatus(_cbT('A cable is 0.1 to 500 m (1 to 1600 ft) long.'), 'warn'); return; }
  const len = `${Math.round(typed * 100) / 100} ${_cbUnits()}`;
  if (conn === 'rj45') {                       // a network patch lead: the same plug at both ends
    _cbAddItem({ kind: 'cable', name: `Network cable (RJ45) ${len}`, a: { conn, gender: 'm' }, b: { conn, gender: 'm' },
      length, type: 'net' }, w, n);
    return;
  }
  const name = `${CB_CONN[conn]} ${type === 'mic' ? 'mic' : 'DMX'} cable ${len}`;
  _cbAddItem({ kind: 'cable', name, a: { conn, gender: 'm' }, b: { conn, gender: 'f' }, length, type }, w, n);
}

// ── my kit (every show) ──────────────────────────────────────────────────────
function _cbMyKit() {
  const el = document.getElementById('cb-mykit');
  if (!el) return;
  if (!_cbBase || !_cbBase.kit) { el.innerHTML = `<div class="porter-placeholder">${_cbE(_cbT('Your kit could not be read.'))}</div>`; return; }
  const inv = _cbBase.kit.items;
  el.innerHTML = inv.length ? _cbTable(inv, 'm')
    : `<div class="porter-placeholder">${_cbE(_cbT('Your kit is empty. Add what you own: the interface, splitters, cables, adapters, terminators and your fixtures.'))}</div>`;
  document.getElementById('cb-kit-path').textContent = _cbT('Kept in {0}, saved as you change it. Share it as a file through the Library (Cabling kit).', _cbBase.path || '');
  _cbPresetOptions(document.getElementById('cb-preset-m'), _cbBase.presets);
  const us = document.getElementById('cb-units');
  if (us) us.value = _cbUnits();
  const res = document.getElementById('cb-fx-res');
  if (res && !res.innerHTML && _cbBase.library === false)
    res.innerHTML = `<div class="cb-dim">${_cbE(_cbT('QLC+\'s fixture library was not found on this computer: use GitHub or By hand.'))}</div>`;
  const sh = document.getElementById('cb-fx-show');
  if (sh) {
    const groups = _cbShowModels();
    sh.innerHTML = !_cb ? `<div class="cb-dim">${_cbE(_cbT('Open a show to take its fixtures.'))}</div>`
      : groups.map((g, k) => `<div class="cb-row"><span data-i18n="off">${g.n} × ${_cbE(g.manufacturer)} ${_cbE(g.model)}</span>
          <button class="btn btn-surface btn-sm" onclick="cablingShowAdd(${k})">+ ${_cbE(_cbT('Add'))}</button></div>`).join('')
        || `<div class="cb-dim">${_cbE(_cbT('The show has no fixtures.'))}</div>`;
  }
  const gh = document.getElementById('cb-gh-mfg');
  if (gh && gh.options.length === 1 && gh.options[0].value === '')
    gh.innerHTML = `<option value="">${_cbE(_cbT('Manufacturer…'))}</option><option value="__load">${_cbE(_cbT('Load the list from github.com…'))}</option>`;
}

function _cbBaseChanged() {
  _cbBaseEdits += 1;
  _cbMyKit();
  clearTimeout(_cbBaseT);
  _cbBaseT = setTimeout(_cbBaseSave, 500);
}

async function _cbBaseSave() {
  const sent = _cbBaseEdits;
  const units = _cbUnits();
  const r = await fetch('/api/cabling/kit', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kit: { items: _cbBase.kit.items, units } }) });
  const d = await r.json();
  if (!r.ok) {
    setStatus((d.error ? _cbT(d.error) : _cbT('Could not keep your kit.'))
      + (d.dropped ? ' ' + d.dropped.map(x => x.reason).join(' ') : ''), 'error');
    return;
  }
  _cbBase.path = d.path;
  if (sent !== _cbBaseEdits) return;        // changed meanwhile: another save follows
  _cbBase.kit = d.kit;
  if (_cb) { _cb.base = d.kit; _cbEvaluate(); }   // the checks speak in the kit's unit
  _cbMyKit();
}

async function cablingKitExport() {
  try {
    const r = await fetch('/api/cabling/kit/export');
    if (!r.ok) { const d = await r.json().catch(() => ({})); setStatus(_cbT(d.error || 'Export failed.'), 'warn'); return; }
    const saved = await saveFileWithPicker(await r.blob(), r.headers.get('X-Suggested-Filename') || 'cabling_kit.qsklib.json',
      null, _cbT('Save your kit'));
    if (saved) setStatus(_cbT('Saved: {0}', saved), 'ok');
  } catch (e) { setStatus(_cbT('Export failed.'), 'error'); }
}

let _cbImportText = '';
async function cablingKitImport(input) {
  const f = input.files && input.files[0];
  input.value = '';
  if (!f) return;
  _cbImportText = await f.text();
  const d = await _apiJson('/api/cabling/kit/import', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: _cbImportText }) });
  const box = document.getElementById('cb-kit-import');
  if (d.error) { setStatus(_cbT(d.error), 'error'); box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = `<div><b data-i18n="off">${_cbE(f.name)}</b>: ${_cbE(_cbT('{0} item(s), {1} you do not have', d.items, d.new))}${d.names.length
      ? ` <span class="cb-dim" data-i18n="off">(${_cbE(d.names.join(', '))})</span>` : ''}</div>
    <div class="cb-actions">
      <button class="btn btn-accent btn-sm" onclick="cablingKitImportGo('add')"${d.new ? '' : ' disabled'}>${_cbE(_cbT('Add what I do not have'))}</button>
      <button class="btn btn-surface btn-sm" onclick="cablingKitImportGo('replace')">${_cbE(_cbT('Replace my kit'))}</button>
      <button class="btn btn-surface btn-sm" onclick="document.getElementById('cb-kit-import').hidden = true">${_cbE(_cbT('Cancel'))}</button></div>`;
}

async function cablingKitImportGo(mode) {
  if (mode === 'replace' && !confirm(_cbT('Your kit becomes the one in the file. Go on?'))) return;
  const d = await _apiJson('/api/cabling/kit/import', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: _cbImportText, mode }) });
  if (d.error) { setStatus(_cbT(d.error), 'error'); return; }
  document.getElementById('cb-kit-import').hidden = true;
  _cbBase.kit = d.kit;
  _cbBase.path = d.path;
  if (_cb) _cb.base = d.kit;
  _cbUnitLabels();
  _cbRender();
  setStatus(mode === 'add' ? _cbT('{0} item(s) added to your kit.', d.added) : _cbT('Your kit is now the one in the file.'), 'ok');
}

function cablingOwnKind() {
  const k = document.getElementById('cb-own-kind').value;
  const set = (id, v) => { document.getElementById(id).value = v; };
  if (k === 'interface') { set('cb-own-in', 'usb'); set('cb-own-out', 'xlr5'); set('cb-own-n', 1); }
  if (k === 'splitter') { set('cb-own-in', 'xlr3'); set('cb-own-out', 'xlr3'); set('cb-own-n', 4); }
  if (k === 'node') { set('cb-own-in', 'rj45'); set('cb-own-out', 'xlr3'); set('cb-own-n', 2); }
  if (k === 'wireless_tx') { set('cb-own-in', 'xlr3'); set('cb-own-out', 'wireless'); set('cb-own-n', 1); }
  if (k === 'wireless_rx') { set('cb-own-in', 'wireless'); set('cb-own-out', 'xlr3'); set('cb-own-n', 1); }
  document.getElementById('cb-own-thru').checked = k === 'splitter';
}

function cablingOwnAdd() {
  const g = id => document.getElementById(id).value;
  const kind = g('cb-own-kind'), name = g('cb-own-name').trim();
  if (!name) { setStatus(_cbT('Give the device a name.'), 'warn'); return; }
  const inC = g('cb-own-in'), outV = g('cb-own-out'), n = Math.max(1, Math.min(16, parseInt(g('cb-own-n'), 10) || 1));
  const outC = outV === 'xlr3m' ? 'xlr3' : outV, outG = outV === 'xlr3m' ? 'm' : (outV === 'wireless' ? '' : 'f');
  const gl = c => (c === 'usb' || c === 'wireless' ? '' : (c === 'rj45' ? 'f' : 'm'));
  const ports = [{ role: 'in', conn: inC, gender: gl(inC), name: inC === 'usb' ? 'USB' : inC === 'rj45' ? 'NET' : inC === 'wireless' ? 'RF' : 'DMX IN' }];
  if (document.getElementById('cb-own-thru').checked && inC.startsWith('xlr')) ports.push({ role: 'thru', conn: inC, gender: 'f', name: 'DMX THRU' });
  for (let i = 1; i <= n; i += 1)
    ports.push({ role: 'out', conn: outC, gender: outG, name: outC === 'wireless' ? 'RF' : (n > 1 ? `DMX OUT ${i}` : 'DMX OUT'),
      isolated: kind === 'splitter' || kind === 'node' });
  const item = { kind, name, ports, termination: g('cb-own-term') };
  if (kind === 'node') item.plugin = 'ArtNet';
  if (kind === 'wireless_tx') item.range_m = _cbToM(g('cb-own-range')) || 100;
  _cbAddItem(item, 'm');
  setStatus(_cbT('{0} added to your kit.', name), 'ok');
}

function cablingUnits(u) {
  if (!_cbBase || !_cbBase.kit) return;
  _cbBase.kit.units = u === 'ft' ? 'ft' : 'm';
  _cbUnitLabels();
  _cbBaseChanged();
  _cbRender();
}

function _cbUnitLabels() {
  document.querySelectorAll('#scr-cabling .cb-u').forEach(e => { e.textContent = _cbUnits(); });
  const len = document.getElementById('cb-cab-len'), lenm = document.getElementById('cb-cab-len-m');
  [len, lenm].forEach(e => { if (e) e.step = _cbUnits() === 'ft' ? '1' : '0.5'; });
}

// items of My kit that tonight's kit does not have (added to My kit after tonight was copied)
function _cbNotTonight() {
  if (!_cb || !_cbBase || !_cbBase.kit) return [];
  const have = new Set(_cb.plan.tonight.items.map(_cbSpec));
  return _cbBase.kit.items.filter(x => x.count > 0 && !have.has(_cbSpec(x)));
}

function _cbSyncHtml() {
  const miss = _cbNotTonight();
  if (!miss.length) return '';
  return `<div class="cb-card cb-sync" onclick="cablingSyncTonight()" title="${_cbE(_cbT('Tonight\'s kit is a copy of My kit made earlier'))}">
    <div><b>${_cbE(_cbT('{0} item(s) of My kit are not in tonight\'s kit:', miss.length))}</b>
    <span data-i18n="off">${_cbE(miss.map(x => `${x.count} × ${x.name}`).join(', '))}</span></div>
    <div><button class="btn btn-accent btn-sm">${_cbE(_cbT('Add them to tonight'))}</button></div></div>`;
}

function cablingSyncTonight() {
  _cbNotTonight().forEach(x => _cbAddItem(x, 't', x.count));
  setStatus(_cbT('Tonight\'s kit now has everything in My kit.'), 'ok');
}

function _cbShowModels() {
  if (!_cb) return [];
  const by = {};
  _cb.rig.fixtures.forEach(f => {
    const k = (f.manufacturer + '|' + f.model).toLowerCase();
    (by[k] = by[k] || { manufacturer: f.manufacturer, model: f.model, conns: f.conns, known: f.connector_known, n: 0 }).n += 1;
  });
  return Object.values(by).sort((a, b) => (a.manufacturer + a.model).localeCompare(b.manufacturer + b.model));
}

function _cbFixtureItem(mf, md, conns, source) {
  const ports = conns.map(c => ({ role: 'in', conn: c, gender: 'm', name: 'DMX IN' }))
    .concat(conns.map(c => ({ role: 'thru', conn: c, gender: 'f', name: 'DMX THRU' })));
  return { kind: 'fixture', name: `${mf} ${md}`.trim(), manufacturer: mf, model: md, ports, termination: 'unknown',
    sources: { connector: source } };
}

function cablingShowAdd(k) {
  const g = _cbShowModels()[k];
  if (g) _cbAddItem(_cbFixtureItem(g.manufacturer, g.model, g.conns, g.known ? 'QLC+ definition' : 'guess'), 'm', g.n);
}

function cablingFxSearch(q) {
  clearTimeout(_cbFxT);
  _cbFxT = setTimeout(async () => {
    const res = document.getElementById('cb-fx-res');
    if (!q.trim()) { res.innerHTML = ''; return; }
    const d = await _apiJson('/api/cabling/fixtures?q=' + encodeURIComponent(q));
    const list = d.results || [];
    res.innerHTML = list.length ? list.map(x => `<div class="cb-row"><span data-i18n="off">${_cbE(x.manufacturer)} ${_cbE(x.model)}</span>
        <button class="btn btn-surface btn-sm" data-mf="${_cbE(x.manufacturer)}" data-md="${_cbE(x.model)}" onclick="cablingFxAdd(this.dataset.mf, this.dataset.md)">+ ${_cbE(_cbT('Add'))}</button></div>`).join('')
      : `<div class="cb-dim">${_cbE(d.library === false ? _cbT('QLC+\'s fixture library was not found on this computer: use GitHub or By hand.') : _cbT('Nothing found.'))}</div>`;
  }, 250);
}

async function cablingFxAdd(mf, md) {
  const d = await _apiJson('/api/cabling/fixture-item', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manufacturer: mf, model: md }) });
  if (d.error) { setStatus(_cbT(d.error), 'error'); return; }
  _cbAddItem(d.item, 'm');
  setStatus(_cbT('{0} added to your kit.', d.item.name), 'ok');
}

async function cablingGhFixtures(mfg) {
  const sel = document.getElementById('cb-gh-fx');
  if (mfg === '__load') {
    document.getElementById('cb-gh-mfg').value = '';
    if (!confirm(_cbT('This reads the list of fixtures from the QLC+ project on github.com (the internet). Go on?'))) return;
    const d = await _apiJson('/api/quickstart/gh/manufacturers');
    if (d.error) { setStatus(_cbT(d.error), 'error'); return; }
    document.getElementById('cb-gh-mfg').innerHTML = `<option value="">${_cbE(_cbT('Manufacturer…'))}</option>`
      + d.manufacturers.map(m => `<option value="${_cbE(m)}">${_cbE(m)}</option>`).join('');
    return;
  }
  if (!mfg) { sel.innerHTML = ''; return; }
  const d = await _apiJson('/api/quickstart/gh/fixtures?manufacturer=' + encodeURIComponent(mfg));
  if (d.error) { setStatus(_cbT(d.error), 'error'); return; }
  sel.innerHTML = d.fixtures.map(f => `<option value="${_cbE(f.name)}">${_cbE(f.display)}</option>`).join('');
}

async function cablingGhAdd() {
  const mfg = document.getElementById('cb-gh-mfg').value, fn = document.getElementById('cb-gh-fx').value;
  if (!mfg || mfg === '__load' || !fn) { setStatus(_cbT('Choose a manufacturer and a fixture first.'), 'warn'); return; }
  const d = await _apiJson('/api/cabling/fixture-item', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gh_manufacturer: mfg, filename: fn }) });
  if (d.error) { setStatus(_cbT(d.error), 'error'); return; }
  _cbAddItem(d.item, 'm');
  setStatus(_cbT('{0} added to your kit.', d.item.name), 'ok');
}

function cablingHandAdd() {
  const mf = document.getElementById('cb-hand-mf').value.trim(), md = document.getElementById('cb-hand-md').value.trim();
  if (!md) { setStatus(_cbT('A fixture needs its model.'), 'warn'); return; }
  const conns = document.getElementById('cb-hand-conn').value.split(',');
  const n = Math.max(1, parseInt(document.getElementById('cb-hand-n').value, 10) || 1);
  _cbAddItem(_cbFixtureItem(mf, md, conns, 'you'), 'm', n);
}

function cablingAskClaudeModel() {
  _cbAskClaude({ manufacturer: document.getElementById('cb-hand-mf').value.trim(),
    model: document.getElementById('cb-hand-md').value.trim() });
}

async function cablingSaveBase() {
  const items = _cb.plan.tonight.items.filter(x => x.owner !== 'venue' && x.count > 0)
    .map(x => { const c = { ...x }; delete c.owner; return c; });
  const r = await fetch('/api/cabling/kit', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kit: { items, units: _cbUnits() } }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || _cbT('Could not keep your kit.'), 'error'); return; }
  _cb.base = d.kit;
  if (_cbBase) { _cbBase.kit = d.kit; _cbBase.path = d.path; }
  setStatus(_cbT('Kept as your kit, for every show: {0} items in {1}. See and change it in My kit.', d.kit.items.length, d.path), 'ok');
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
    _cb.plan.tonight.items.push({ ..._cbFixtureItem(g.manufacturer, g.model, fx.conns, fx.connector_known ? 'QLC+ definition' : 'guess'),
      id: _cbNewId('fixture'), count: g.ids.length, owner: 'mine' });
  } else {
    g.ids.forEach(id => { _cb.plan.owners[id] = owner; });
  }
  _cb.found.splice(k, 1);
  _cbChanged();
}

function cablingAskClaude(k) { _cbAskClaude((_cb.found || [])[k] || {}); }

async function _cbAskClaude(g) {
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

const _cbStageNow = () => _cb.plan.stage || _cb.rig.stage;

function _cbStageBox() {
  const st = _cbStageNow(), ctl = _cb.evaluation.controller;
  const x0 = Math.min(-2000, ctl.x - 800), x1 = Math.max(st.w + 2000, ctl.x + 800);
  const z0 = Math.min(-1000, ctl.z - 800), z1 = Math.max(st.d + 1500, ctl.z + 800);
  return { x0, z0, x1, z1 };
}

function _cbStageSvg(clickable) {
  const st = _cbStageNow(), b = _cbStageBox(), p = _cb.plan, ev = _cb.evaluation;
  const parts = [`<svg viewBox="${b.x0} ${b.z0} ${b.x1 - b.x0} ${b.z1 - b.z0}" class="cb-svg" role="img" aria-label="${_cbE(_cbT('The stage from above'))}"
    ${clickable ? 'onclick="cablingStageClick(event)"' : ''}>`];
  parts.push(`<rect x="0" y="0" width="${st.w}" height="${st.d}" class="cb-s-stage"/>`);
  parts.push(`<text x="${st.w / 2}" y="${st.d + 700}" class="cb-s-lbl" text-anchor="middle">${_cbE(_cbT('AUDIENCE'))}</text>`);
  _cb.rig.keep_out.forEach(k => parts.push(`<rect x="${k.x0}" y="${k.z0}" width="${k.x1 - k.x0}" height="${k.z1 - k.z0}" class="cb-s-keep"><title>${_cbE(_cbT('Band floor: {0} plus 50 cm', k.label || ''))}</title></rect>`));
  _cb.rig.keep_out.forEach(k => { if (k.label) parts.push(`<text x="${k.x0 + 80}" y="${k.z0 + 180}" class="cb-s-klbl">${_cbE(k.label.slice(0, 24))}</text>`); });
  (p.walkways || []).forEach(w => parts.push(`<rect x="${w.x0}" y="${w.z0}" width="${w.x1 - w.x0}" height="${w.z1 - w.z0}" class="cb-s-walk${w.ramp ? ' ramp' : ''}"/>`));
  (ev.trusses || []).forEach(tr => parts.push(`<line x1="${tr.x0 - 200}" y1="${tr.z}" x2="${tr.x1 + 200}" y2="${tr.z}" class="cb-s-truss"/>`));
  ev.fixtures.forEach(f => {
    if (!f.place) return;
    parts.push(`<circle cx="${f.place.x}" cy="${f.place.z}" r="150" class="cb-s-fx${f.owner === 'venue' ? ' venue' : ''}${f.patched === false ? ' extra' : ''}"><title>${_cbE(f.name)}</title></circle>`);
    parts.push(`<text x="${f.place.x}" y="${f.place.z + 330}" text-anchor="middle" class="cb-s-name">${_cbE(f.name.slice(0, 22))}</text>`);
  });
  (p.outlets || []).forEach(o => parts.push(`<rect x="${o.x - 120}" y="${o.z - 120}" width="240" height="240" class="cb-s-outlet"><title>${_cbE(_cbT('Power outlet'))}</title></rect>`));
  Object.entries(p.places || {}).forEach(([id, q]) => {
    if (id === 'controller') return;
    const it = p.tonight.items.find(x => x.id === id);
    parts.push(`<rect x="${q.x - 180}" y="${q.z - 110}" width="360" height="220" class="cb-s-split"><title>${_cbE(it ? it.name : id)}</title></rect>`);
    parts.push(`<text x="${q.x}" y="${q.z + 320}" text-anchor="middle" class="cb-s-sname">${_cbE(it ? it.name.split(' ')[0] : id)}</text>`);
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
  const st = _cbStageNow(), sh = _cb.rig.stage;
  set('cb-stage-w', _cbNum(st.w / 1000)); set('cb-stage-d', _cbNum(st.d / 1000));
  const shw = document.getElementById('cb-stage-show');
  if (shw) shw.textContent = _cb.plan.stage ? _cbT('The show: {0} × {1}', _cbLen(sh.w / 1000), _cbLen(sh.d / 1000))
    : _cbT('The size in the show');
  const pi = document.getElementById('cb-place-item');
  if (pi) {
    const devs = p0 => p0.tonight.items.filter(i => ['splitter', 'node', 'wireless_tx', 'wireless_rx'].includes(i.kind) && i.count > 0);
    const keep = pi.value;
    pi.innerHTML = devs(_cb.plan).map(i => `<option value="${_cbE(i.id)}">${_cbE(i.name)}</option>`).join('')
      || `<option value="">${_cbE(_cbT('no device in tonight\'s kit'))}</option>`;
    if (keep && [...pi.options].some(o => o.value === keep)) pi.value = keep;
  }
  set('cb-side-sel', c.side); set('cb-computer', c.computer || 'laptop'); set('cb-foh-d', _cbNum(c.distance_m)); set('cb-foh-route', c.route); set('cb-slack', _cbNum(_cb.plan.slack_m));
  const p = _cb.plan, items = Object.fromEntries(p.tonight.items.map(x => [x.id, x]));
  const rows = [];
  Object.entries(p.places || {}).forEach(([id, q]) => rows.push(`<div class="cb-row"><span>${_cbE(id === 'controller' ? _cbT('Computer') : (items[id] || {}).name || id)}</span>
    <span class="cb-dim">${_cbLen(q.x / 1000)} / ${_cbLen(q.z / 1000)}</span><button class="btn btn-surface btn-sm" onclick="cablingClearPlace('${id}')">✕</button></div>`));
  (p.walkways || []).forEach((w, i) => rows.push(`<div class="cb-row"><span>${_cbE(_cbT('Walkway'))} ${i + 1}</span>
    <label class="cb-check"><input type="checkbox" ${w.ramp ? 'checked' : ''} onchange="cablingWalk(${i}, 'ramp', this.checked)"> ${_cbE(_cbT('cable ramp'))}</label>
    <button class="btn btn-surface btn-sm" onclick="cablingWalk(${i}, 'remove')">✕</button></div>`));
  (p.outlets || []).forEach((o, i) => rows.push(`<div class="cb-row"><span>${_cbE(_cbT('Outlet'))} ${i + 1}</span>
    <span class="cb-dim">${_cbLen(o.x / 1000)} / ${_cbLen(o.z / 1000)}</span><button class="btn btn-surface btn-sm" onclick="cablingOutlet(${i})">✕</button></div>`));
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
    const want = (document.getElementById('cb-place-item') || {}).value;
    const sp = p.tonight.items.find(i => i.id === want && i.count > 0)
      || p.tonight.items.find(i => i.kind === 'splitter' && i.count > 0) || p.tonight.items.find(i => i.kind === 'node' && i.count > 0);
    if (!sp) { setStatus(_cbT('Tonight\'s kit has no splitter, node or wireless unit to place.'), 'warn'); return; }
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

function cablingStage(reset) {
  const sh = _cb.rig.stage, now = _cbStageNow();
  // a value left as shown keeps its exact size (the shown one is rounded to the unit)
  const val = (id, mm) => { const v = document.getElementById(id).value;
    return +v === _cbNum(mm / 1000) ? mm : _cbToM(v) * 1000; };
  const w = val('cb-stage-w', now.w), d = val('cb-stage-d', now.d);
  if (reset || (Math.round(w) === sh.w && Math.round(d) === sh.d)) delete _cb.plan.stage;
  else if (w >= 1000 && d >= 1000) _cb.plan.stage = { w: Math.round(w), d: Math.round(d) };
  else { setStatus(_cbT('A stage is at least 1 m by 1 m.'), 'warn'); return; }
  _cbAlts = null;
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
      <div class="cb-alt-n"><span>${_cbE(_cbT('Cable'))}</span><b>${_cbLen(a.cable_m)}</b><span>${_cbE(_cbT('Longest hop'))}</span><b>${_cbLen(a.longest_m)}</b>
        <span>${_cbE(_cbT('Crossings'))}</span><b>${a.crossings}</b><span>${_cbE(_cbT('Adapters'))}</span><b>${a.adapters}</b></div>
      <div class="${a.missing.length ? 'cb-bad' : 'cb-good'}">${a.missing.length
        ? _cbE(_cbT('Missing: {0}', a.missing.map(m => `${m.count} × ${m.what}`).join(', '))) : _cbE(_cbT('Nothing missing'))}</div>
    </button>`).join('') : `<div class="porter-placeholder">${_cbE(_cbT('No alternative: the show has no fixtures.'))}</div>`;
  document.getElementById('cb-plot').innerHTML = _cb.plan.chains.length ? (_cb.svg || '')
    : `<div class="porter-placeholder">${_cbE(_cbT('No chains yet: ✨ Propose, or start a chain by hand.'))}</div>`;
  const tt = _cb.evaluation.totals;
  document.getElementById('cb-plan-totals').textContent = _cb.plan.chains.length
    ? _cbT('{0} of cable · longest hop {1} · {2} adapter(s)', _cbLen(tt.cable_m), _cbLen(tt.longest_m), tt.adapters) : '';
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
      const cab = (l.cables || []).map(x => _cbLen(x.length)).join(' + ') || (l.missing_m ? _cbT('{0} to buy', _cbLen(l.missing_m)) : '');
      return `<div class="cb-link"><span class="cb-n">${i + 1}</span><span class="cb-to" data-i18n="off">${_cbE(nm)}</span>
        <span class="cb-dim">${_cbE(cab)}</span>
        <button class="btn btn-surface btn-sm" onclick="cablingDev(${n}, ${i}, -1)" ${i === 0 ? 'disabled' : ''} title="${_cbE(_cbT('Earlier'))}">↑</button>
        <button class="btn btn-surface btn-sm" onclick="cablingDev(${n}, ${i}, 1)" ${i === c.devices.length - 1 ? 'disabled' : ''} title="${_cbE(_cbT('Later'))}">↓</button>
        <select class="field-input cb-move" onchange="cablingMove(${n}, ${i}, this.value)"><option value="">${_cbE(_cbT('move…'))}</option>${opts(n)}<option value="x">${_cbE(_cbT('off the chain'))}</option></select></div>`;
    }).join('');
    const iss = (w.issues || []).filter(x => x.severity !== 'info').map(x => `<div class="cb-iss sev-${x.severity}"><b>${x.code}</b> ${_cbE(x.text)}</div>`).join('');
    return `<div class="cb-chain" style="border-left-color:${_cbE(col)}">
      <div class="cb-chain-h"><b data-i18n="off">${n + 1}. ${_cbE(c.label || w.name)}</b><span class="cb-dim">${w.total_m != null ? _cbLen(w.total_m) : ''}</span>
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
  document.getElementById('cb-checks').innerHTML = _cbSyncHtml() + (all.length ? all.map(i => `<div class="cb-check-row sev-${i.severity}">
      <span class="cb-code">${i.code}</span><div><div>${_cbE(i.text)}</div>${i.fix ? `<div class="cb-dim">${_cbE(i.fix)}</div>` : ''}</div></div>`).join('')
    : `<div class="cb-card cb-good">${_cbE(_cbT('Nothing to fix.'))}</div>`);
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
