/* =============================================================================
   inputs.js — "Inputs & MIDI" panel of the Trigger Manager (v2.6.0)
   The universes' input patch, re-patching bindings, a MIDI-message simulator.
   ============================================================================= */

'use strict';

let _inS = null;            // /api/inputs/state
let _inOpen = false;
let _inEdit = null;         // universe id being patched
let _inSim = null;          // last simulate result

function toggleInputs() {
  _inOpen = !_inOpen;
  const panel = document.getElementById('trg-inputs-panel');
  const btn = document.getElementById('trg-inputs-btn');
  if (panel) panel.style.display = _inOpen ? 'block' : 'none';
  if (btn) btn.classList.toggle('btn-view-active', _inOpen);
  if (_inOpen) _inLoad();
}

async function _inLoad() {
  const wrap = document.getElementById('trg-inputs-wrap');
  if (!wrap) return;
  const d = await _apiJson('/api/inputs/state');
  if (d.error) { wrap.innerHTML = `<div class="vce-hint">${_te(d.error)}</div>`; return; }
  _inS = d;
  _inRender();
}

async function _inOp(body, refreshTriggers) {
  const r = await fetch('/api/inputs/op', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Failed.', 'error'); return null; }
  _inS = d; _inSim = null;
  _inRender();
  if (d.message) setStatus(d.message + ' Not saved yet.', 'ok');
  if (refreshTriggers && typeof invalidateTriggers === 'function') {
    invalidateTriggers();
    if (typeof ensureTriggersLoaded === 'function') ensureTriggersLoaded();
  }
  return d;
}

const _inV = id => { const e = document.getElementById(id); return e ? e.value : ''; };
const _uLabel = u => `U${+u.id + 1} ${u.name && u.name !== 'Universe ' + (+u.id + 1) ? '· ' + u.name : ''}`;

function _inRender() {
  const wrap = document.getElementById('trg-inputs-wrap');
  const S = _inS; if (!wrap || !S) return;
  const U = S.universes;
  const chip = u => u.status === 'ok' ? '<span class="doc-chip">✓ patched</span>'
    : u.status === 'no_input' ? '<span class="doc-chip" style="color:var(--warning)" title="Bindings listen to this universe, but no input device is patched — in QLC+ the buttons stay silent (the \'saved as None\' case)">⚠ no input</span>'
    : '<span class="vce-hint">—</span>';
  const rows = U.map(u => `<tr>
      <td>${_te(_uLabel(u))}</td>
      <td>${u.input.device ? `${_te(u.input.plugin)} · ${_te(u.input.device)}${u.input.line && u.input.line !== '0' ? ' · line ' + (+u.input.line + 1) : ''}` : '<span class="no-val">—</span>'}</td>
      <td>${_te(u.input.profile) || '<span class="no-val">—</span>'}</td>
      <td>${u.feedback.device ? '✓' : '<span class="no-val">—</span>'}</td>
      <td>${u.bindings}</td><td>${chip(u)}</td>
      <td><button class="btn btn-surface btn-sm" onclick="_inEditUni('${u.id}')">Patch…</button>
          ${u.input.device ? `<button class="btn btn-surface btn-sm" onclick="_inOp({op:'clear_input',universe:'${u.id}'})">Clear</button>` : ''}</td></tr>`).join('');
  const e = U.find(u => u.id === _inEdit);
  const opt = (arr, sel) => arr.map(v => `<option ${v === sel ? 'selected' : ''}>${_te(v)}</option>`).join('');
  const uOpts = (sel) => U.map(u => `<option value="${u.id}" ${u.id === sel ? 'selected' : ''}>${_te(_uLabel(u))}</option>`).join('');
  const patchForm = e ? `
    <div class="st-sec">Patch universe ${+e.id + 1}</div>
    <div class="lb-row">
      <label>Plugin <select id="in-plugin" class="filter-input">${opt(S.plugins, e.input.plugin || 'MIDI')}</select></label>
      <label>Device <input id="in-device" class="filter-input" style="width:260px" value="${_te(e.input.device)}" placeholder="exactly as QLC+ lists it (Inputs/Outputs tab)"></label>
      <label>Line <input id="in-line" type="number" min="1" class="filter-input rr-num" value="${+(e.input.line || 0) + 1}"></label>
    </div>
    <div class="lb-row">
      <label>Profile <input id="in-profile" class="filter-input" list="in-profiles" style="width:260px" value="${_te(e.input.profile)}" placeholder="optional — e.g. Behringer BCF2000"></label>
      <datalist id="in-profiles">${S.profiles.map(p => `<option value="${_te(p)}">`).join('')}</datalist>
      <label class="vce-hint"><input type="checkbox" id="in-fb" ${e.feedback.device ? 'checked' : ''}> feedback to the same device</label>
    </div>
    <div class="lb-row">
      <button class="btn btn-accent btn-sm" onclick="_inPatch()">✓ Patch</button>
      <button class="btn btn-surface btn-sm" onclick="_inRemember()" title="Keep this controller so any show can use it in one click">★ Remember it…</button>
      <button class="btn btn-surface btn-sm" onclick="_inEdit=null;_inRender()">Cancel</button>
    </div>` : '';
  const ctl = S.controllers.length ? `
    <div class="st-sec">My controllers <span class="vce-hint">kept on this computer — when QLC+ saved a show with the input as None, patch it back in one click</span></div>
    <div class="lb-row"><label>Patch <select id="in-ctl" class="filter-input">${S.controllers.map(c => `<option value="${_te(c.name)}">${_te(c.name)} — ${_te(c.device)}</option>`).join('')}</select></label>
      <label>on <select id="in-ctl-u" class="filter-input">${uOpts(e ? e.id : (U.find(u => u.status === 'no_input') || U[0] || {}).id)}</select></label>
      <button class="btn btn-accent btn-sm" onclick="_inApplyCtl()">✓ Patch</button>
      <button class="btn btn-surface btn-sm" onclick="_inForget()">Forget</button></div>` : '';
  const move = U.length ? `
    <div class="st-sec">Re-patch the bindings <span class="vce-hint">move every button that listens to one universe to another — e.g. a new controller on another universe</span></div>
    <div class="lb-row"><label>From <select id="in-mv-a" class="filter-input">${uOpts((U.find(u => u.bindings) || U[0]).id)}</select></label>
      <label>to <select id="in-mv-b" class="filter-input">${uOpts((U[1] || U[0]).id)}</select></label>
      <label>shift channels by <input id="in-mv-shift" type="number" class="filter-input st-n" value="0"></label>
      <button class="btn btn-surface btn-sm" onclick="_inMove()">⇢ Move</button>
      <button class="btn btn-surface btn-sm" onclick="_inSwap()" title="Exchange the bindings of the two universes">⇄ Swap</button></div>` : '';
  const sim = U.length ? `
    <div class="st-sec">MIDI simulator <span class="vce-hint">what would this message trigger? — a MIDI-learn without the controller</span></div>
    <div class="lb-row"><label>Universe <select id="in-s-u" class="filter-input">${uOpts((U.find(u => u.bindings) || U[0]).id)}</select></label>
      <label>Message <select id="in-s-k" class="filter-input">${S.kinds.map(k => `<option value="${k.id}" ${k.id === 'note' ? 'selected' : ''}>${_te(k.label)}</option>`).join('')}</select></label>
      <label>number <input id="in-s-n" type="number" min="0" max="127" class="filter-input st-n" value="60"></label>
      <label>MIDI channel <input id="in-s-m" type="number" min="1" max="16" class="filter-input st-n" placeholder="any" title="Only for OMNI-mode inputs"></label>
      <button class="btn btn-accent btn-sm" onclick="_inSimulate()">▶ Simulate</button></div>
    <div id="in-sim">${_inSimHtml()}</div>` : '';
  const widgets = S.widgets.length ? `
    <details class="vce-sub"><summary>Every binding in the Virtual Console (${S.widgets.reduce((n, w) => n + w.bindings.length, 0)})</summary>
      <table class="custom-table"><thead><tr><th>Widget</th><th>Function</th><th>Universe</th><th>Channel</th><th>Message</th></tr></thead><tbody>
      ${S.widgets.flatMap(w => w.bindings.map(b => `<tr><td>${_te(w.path ? w.path + ' › ' : '')}${_te(w.caption || w.type)}${b.slot ? ' <span class="vce-hint">' + _te(b.slot) + '</span>' : ''}</td>
        <td>${_te(w.function) || '<span class="no-val">—</span>'}</td><td>U${+b.universe + 1}</td><td>${+b.channel + 1}</td><td>${_te(b.text)}</td></tr>`)).join('')}
      </tbody></table>
      <div class="vce-hint">Channels are shown as in QLC+ (1-based); the file stores them one lower.</div></details>` : '';
  wrap.innerHTML = `<h3>Inputs &amp; MIDI <span class="p-desc">${_te(S.source)}</span></h3>
    <table class="custom-table"><thead><tr><th>Universe</th><th>Input</th><th>Profile</th><th>Feedback</th><th>Bindings</th><th></th><th></th></tr></thead><tbody>
    ${rows || '<tr><td colspan="7" class="vce-hint">No universes.</td></tr>'}</tbody></table>
    ${patchForm}${ctl}${move}${sim}${widgets}`;
}

function _inEditUni(id) { _inEdit = id; _inRender(); }

function _inPatch() {
  _inOp({ op: 'set_input', universe: _inEdit, plugin: _inV('in-plugin'), device: _inV('in-device'),
          line: Math.max(0, (+_inV('in-line') || 1) - 1), profile: _inV('in-profile'),
          feedback: document.getElementById('in-fb').checked }).then(d => { if (d) { _inEdit = null; _inRender(); } });
}

function _inRemember() {
  const name = prompt('Name this controller (e.g. "BCF2000 on stage"):', _inV('in-profile') || _inV('in-device'));
  if (!name) return;
  _inOp({ op: 'remember', name, plugin: _inV('in-plugin'), device: _inV('in-device'),
          line: Math.max(0, (+_inV('in-line') || 1) - 1), profile: _inV('in-profile'),
          feedback: document.getElementById('in-fb').checked });
}

function _inApplyCtl() { _inOp({ op: 'apply_controller', name: _inV('in-ctl'), universe: _inV('in-ctl-u') }); }
function _inForget() { if (confirm('Forget this controller?')) _inOp({ op: 'forget', name: _inV('in-ctl') }); }

function _inMove() {
  _inOp({ op: 'move', src: _inV('in-mv-a'), dst: _inV('in-mv-b'), shift: +_inV('in-mv-shift') || 0 }, true);
}
function _inSwap() { _inOp({ op: 'swap', a: _inV('in-mv-a'), b: _inV('in-mv-b') }, true); }

async function _inSimulate() {
  const r = await fetch('/api/inputs/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ universe: _inV('in-s-u'), kind: _inV('in-s-k'), number: +_inV('in-s-n') || 0,
                           midi_channel: _inV('in-s-m') || null }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Failed.', 'error'); return; }
  _inSim = d;
  const el = document.getElementById('in-sim'); if (el) el.innerHTML = _inSimHtml();
}

function _inSimHtml() {
  const d = _inSim; if (!d) return '';
  const row = h => `<tr><td>${_te(h.path ? h.path + ' › ' : '')}${_te(h.caption || h.type)}${h.slot ? ' <span class="vce-hint">' + _te(h.slot) + '</span>' : ''}</td><td>${_te(h.function) || '<span class="no-val">—</span>'}</td><td>${_te(h.text)}</td></tr>`;
  return `<div class="vce-hint">${_te(d.decoded.text)} → stored channel ${d.channel}, shown as ${d.channel + 1} in QLC+</div>
    ${d.hits.length ? `<table class="custom-table"><thead><tr><th>Fires</th><th>Function</th><th>Binding</th></tr></thead><tbody>${d.hits.map(row).join('')}</tbody></table>` : ''}
    ${d.near.length ? `<div class="vce-hint">Near misses (same number, other MIDI channel):</div><table class="custom-table"><tbody>${d.near.map(row).join('')}</tbody></table>` : ''}
    ${d.notes.map(n => `<div class="porter-warn">${_te(n)}</div>`).join('')}`;
}

function invalidateInputs() { if (typeof invalidateTriggers === 'function') invalidateTriggers(); _inS = null; _inSim = null; _inEdit = null; if (_inOpen) _inLoad(); }
