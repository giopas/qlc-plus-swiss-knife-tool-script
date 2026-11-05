/* =============================================================================
   brightness.js — Per-fixture brightness scaling tab
   =============================================================================
   Lets the user scale the Master Dimmer channel of each fixture (or fixture
   group) across every Scene in the loaded workspace, then download a new QXW.
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _brtFixtures   = [];   // [{id,name,manufacturer,model,mode,dimmer_offset,...}]
let _brtLoaded     = false;
let _brtScales     = {};   // fixture_id → scale (0.0–2.0, default 1.0)
let _brtManual     = {};   // fixture_id → dimmer_offset (for QXF-not-found fixtures)
let _brtLinked     = {};   // model_key  → bool (true = sliders move together)
let _brtPreviewTm  = null; // debounce timer for preview
let _brtBaseline   = {};   // fixture_id → {peak, mean, scene_count, room_pct, at_full} (from current scene values)
let _brtLevelVal   = {};   // 3.12.0: the level typed in each card's box (kept across redraws)
let _brtCaps       = {};   // 3.12.0: fixture_id → limit in % of full (no value goes above it)
let _brtHistory    = null; // 3.11.0: /api/brightness/history (changes made before, from the recipes)
let _brtGroupsList = [];   // 3.11.0: the show's fixture groups [{id, name, fixtures}]
let _brtView       = (() => { try { return localStorage.getItem('sk.brt.view') || 'type'; } catch (e) { return 'type'; } })();

// ── Public API (called from app.js) ──────────────────────────────────────────

function invalidateBrightness() {
  _brtLoaded   = false;
  _brtFixtures = [];
  _brtScales   = {};
  _brtManual   = {};
  _brtLinked   = {};
  _brtBaseline = {};
  _brtCaps     = {};
  _brtHistory  = null;
  _brtGroupsList = [];
  const wrap = document.getElementById('brt-fixture-wrap');
  if (wrap) wrap.innerHTML = '<div class="brt-placeholder"><a class="open-ws-link"><svg class="ic" aria-hidden="true"><use href="/static/icons.svg#folder"/></svg> Open a workspace</a> to adjust brightness.</div>';
  _brtSetPreview(null);
}

async function ensureBrightnessLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_brtLoaded) return;
  _brtLoaded = true;
  await _brtLoadFixtures();
}

// ── Data ─────────────────────────────────────────────────────────────────────

async function _brtLoadFixtures() {
  const [data, baselineData, hist, grps] = await Promise.all([
    _apiJson('/api/brightness/fixtures'),
    _apiJson('/api/brightness/baseline'),
    _apiJson('/api/brightness/history'),
    _apiJson('/api/brightness/groups'),
  ]);
  _brtHistory = hist && !hist.error ? hist : null;
  _brtGroupsList = Array.isArray(grps) ? grps : [];
  if (data.error) { setStatus(data.error, 'error'); return; }
  _brtFixtures = Array.isArray(data) ? data : [];

  // Store baseline stats keyed by fixture ID
  _brtBaseline = {};
  if (Array.isArray(baselineData)) {
    for (const b of baselineData) _brtBaseline[b.id] = b;
  }

  // Initialise scales to 1.0 and link state per model group
  const seen = {};
  for (const fx of _brtFixtures) {
    if (_brtScales[fx.id] === undefined) _brtScales[fx.id] = 1.0;
    const mk = _brtModelKey(fx);
    if (!seen[mk]) { seen[mk] = true; if (_brtLinked[mk] === undefined) _brtLinked[mk] = true; }
  }
  // Slider values restored from a session (.qsk)
  const rs = window._brtPendingRestore;
  if (rs) {
    for (const fx of _brtFixtures) {
      if (rs.scales && rs.scales[fx.id] !== undefined) _brtScales[fx.id] = rs.scales[fx.id];
      if (rs.manual && rs.manual[fx.id] !== undefined) _brtManual[fx.id] = rs.manual[fx.id];
      if (rs.caps && rs.caps[fx.id] !== undefined) _brtCaps[fx.id] = rs.caps[fx.id];
    }
    Object.assign(_brtLinked, rs.linked || {});
    window._brtPendingRestore = null;
  }
  _brtRender();
  _brtUpdateFetchBtn();
  if (rs && typeof _brtFetchPreview === 'function') _brtFetchPreview();
}

function _brtModelKey(fx) {
  return `${fx.manufacturer}||${fx.model}||${fx.mode}`;
}

function _brtMissingFixtures() {
  return _brtFixtures.filter(fx => !fx.qxf_found).map(fx => ({
    manufacturer: fx.manufacturer,
    model:        fx.model,
    fixture_name: fx.name,
  }));
}

// ── Room and history helpers (3.11.0) ───────────────────────────────────────

const _brtPct = v => Math.round(v * 100);

/** The brightest scene of these fixtures (% of full) and how far they can go up
 *  before the brightest scene of one of them is at full. */
function _brtRoom(fixtures) {
  let peak = null, room = null, usual = null;
  for (const fx of fixtures) {
    const b = _brtBaseline[fx.id];
    if (!b || !b.scene_count || !b.peak) continue;
    const p = b.peak / 255 * 100;
    peak = peak === null ? p : Math.max(peak, p);
    if (b.room_pct != null) room = room === null ? b.room_pct : Math.min(room, b.room_pct);
    if (b.usual_top) { const u = b.usual_top / 255 * 100; usual = usual === null ? u : Math.max(usual, u); }
  }
  return { peak, room, usual };
}

/** The limit set on these fixtures now (%), when they all share one; '' when none, 'mixed' when they differ. */
function _brtCardCap(fixtures) {
  const v = fixtures.map(f => _brtCaps[f.id]);
  if (v.every(x => x === undefined)) return '';
  return v.every(x => x === v[0]) ? v[0] : 'mixed';
}

/** What was done before to these fixtures: [lowest %, highest %] of the total change, or null. */
function _brtEarlier(fixtures) {
  const tot = (_brtHistory && _brtHistory.total) || {};
  const vals = fixtures.map(f => tot[f.id]).filter(v => v !== undefined && Math.abs(v - 1) > 0.004);
  if (!vals.length) return null;
  return [_brtPct(Math.min(...vals)), _brtPct(Math.max(...vals)), vals.length === fixtures.length];
}

function _brtRoomHtml(fixtures, scalePct) {
  const { peak, room, usual } = _brtRoom(fixtures);
  const bits = [];
  if (peak === null) bits.push(`<span class="brt-room-none">${_esc(t('No scene sets its dimmer'))}</span>`);
  else {
    const over = room !== null && scalePct > room;
    bits.push(`<span>${_esc(t('Brightest scene: {0}% of full', Math.round(peak)))}</span>`);
    if (usual !== null && Math.round(usual) < Math.round(peak) - 2)
      bits.push(`<span class="brt-room-usual" title="${_esc(t('Nine lit scenes in ten stay at or below this level. Only a few scenes go higher.'))}">${_esc(t('Usually up to {0}%', Math.round(usual)))}</span>`);
    bits.push(room !== null && room > 100
      ? `<span class="${over ? 'brt-room-over' : 'brt-room-ok'}">${_esc(t('Room to go brighter: up to {0}%', room))}</span>`
      : `<span class="${scalePct > 100 ? 'brt-room-over' : 'brt-room-full'}">${_esc(t('No room to go brighter: the brightest scenes are at full'))}</span>`);
  }
  if (peak !== null) {
    let after = 0;
    for (const fx of fixtures) {
      const b = _brtBaseline[fx.id];
      if (!b || !b.peak) continue;
      let v = Math.min(255, Math.round(b.peak * (_brtScales[fx.id] ?? 1)));
      if (_brtCaps[fx.id] !== undefined) v = Math.min(v, Math.round(_brtCaps[fx.id] * 255 / 100));
      after = Math.max(after, v);
    }
    const a = Math.round(after / 255 * 100);
    if (a !== Math.round(peak)) bits.push(`<span class="brt-room-after">${_esc(t('After your change: brightest scene {0}%', a))}</span>`);
  }
  const cap = _brtCardCap(fixtures);
  if (cap !== '') bits.push(`<span class="brt-room-cap">${_esc(cap === 'mixed' ? t('Limit: different for each fixture') : t('Limit now: {0}%, no scene goes above it', cap))}</span>`);
  const tc = (_brtHistory && _brtHistory.total_caps) || {};
  const ec = fixtures.map(f => tc[f.id]).filter(v => v !== undefined);
  if (ec.length) bits.push(`<span class="brt-room-earlier">${_esc(t('Limited before to {0}%', Math.round(Math.min(...ec))))}</span>`);
  const e = _brtEarlier(fixtures);
  if (e) bits.push(`<span class="brt-room-earlier" title="${_esc(t('From the recipes saved next to this show and its earlier versions'))}">${_esc(
    e[0] === e[1] ? t('Changed before: {0}%', e[0]) : t('Changed before: {0}% to {1}%', e[0], e[1]))}</span>`);
  return `<div class="brt-room">${bits.join('')}</div>`;
}

function _brtFxRoomHtml(fx) {
  const b = _brtBaseline[fx.id];
  const tot = (_brtHistory && _brtHistory.total) || {};
  const bits = [];
  if (b && b.scene_count && b.peak) {
    const mx = Math.round(b.peak / 255 * 100), us = Math.round((b.usual_top || 0) / 255 * 100);
    bits.push(us && us < mx - 2 ? t('max {0}%, usually {1}%', mx, us) : t('max {0}%', mx));
  }
  if (_brtCaps[fx.id] !== undefined) bits.push(t('limit {0}%', _brtCaps[fx.id]));
  if (tot[fx.id] !== undefined && Math.abs(tot[fx.id] - 1) > 0.004) bits.push(t('before {0}%', _brtPct(tot[fx.id])));
  return bits.length ? `<span class="brt-fx-room" title="${_esc(t('Brightest scene of this fixture, and what Swiss Knife changed before'))}">${_esc(bits.join(' · '))}</span>` : '';
}

/** Names for the fixtures of a change: one line per fixture type when the whole type had the same change. */
function _brtScalesText(scales) {
  const byType = {};
  for (const fx of _brtFixtures) (byType[_brtModelKey(fx)] = byType[_brtModelKey(fx)] || []).push(fx);
  const done = new Set(), parts = [];
  for (const [mk, fxs] of Object.entries(byType)) {
    const v = fxs.map(f => scales[f.id]);
    if (v.every(x => x !== undefined && Math.abs(x - v[0]) < 0.004)) {
      parts.push(`${fxs[0].manufacturer} ${fxs[0].model}: ${_brtPct(v[0])}%`);
      fxs.forEach(f => done.add(f.id));
    }
  }
  const names = Object.fromEntries(_brtFixtures.map(f => [f.id, f.name]));
  for (const [id, v] of Object.entries(scales)) if (!done.has(id)) parts.push(`${names[id] || t('fixture {0}', id)}: ${_brtPct(v)}%`);
  return parts.join(', ');
}

function _brtHistoryHtml() {
  const h = _brtHistory;
  if (!h) return '';
  const rows = [];
  if (Object.keys(h.session || {}).length)
    rows.push(`<li><b>${_esc(t('In the show in progress'))}</b>: <span data-i18n="off">${_esc(_brtScalesText(h.session))}</span></li>`);
  const capText = caps => Object.keys(caps || {}).length
    ? _brtScalesText(Object.fromEntries(Object.entries(caps).map(([k, v]) => [k, v / 100]))).replace(/(\d+)%/g, (m) => t('limit {0}', m)) : '';
  if (Object.keys(h.session_caps || {}).length)
    rows.push(`<li><b>${_esc(t('In the show in progress'))}</b>: <span data-i18n="off">${_esc(capText(h.session_caps))}</span></li>`);
  for (const c of h.changes || [])
    rows.push(`<li><b data-i18n="off">${_esc(c.file)}</b> <span class="brt-hist-date">${_esc(c.date)}</span>: <span data-i18n="off">${_esc(
      [Object.keys(c.scales || {}).length ? _brtScalesText(c.scales) : '', capText(c.caps)].filter(Boolean).join('; '))}</span></li>`);
  const checked = (h.checked || []).length;
  let ends = '';
  if (h.ends === 'no_recipe' && checked) ends = t('{0} has no recipe, so changes made before it are not known.', h.checked[checked - 1]);
  else if (h.ends && h.ends.startsWith('missing:')) ends = t('{0} is not in this folder, so changes made before it are not known.', h.ends.slice(8));
  else if (h.ends === 'no_folder') ends = t('The show was opened without its folder, so its recipes cannot be read.');
  const notes = [];
  if (h.edited_after) notes.push(t('This file was changed after Swiss Knife saved it (in QLC+, for example): changes made there are not listed.'));
  if (h.sure === false) notes.push(t('The History was used to jump between steps: the list may be off.'));
  if (ends) notes.push(ends);
  const head = rows.length ? t('Brightness was changed before') : t('No earlier Brightness change found');
  const sub = rows.length ? '' : (checked ? t('Checked the recipes of {0} file(s).', checked) : '');
  return `<div class="brt-history ${rows.length ? 'brt-history-on' : ''}">
    <div class="brt-history-h"><b>${_esc(head)}</b> ${sub ? `<span class="brt-hist-date">${_esc(sub)}</span>` : ''}</div>
    ${rows.length ? `<ul>${rows.join('')}</ul>` : ''}
    ${notes.map(n => `<div class="brt-hist-note">${_esc(n)}</div>`).join('')}
    <div class="brt-hist-note">${_esc(t('The brightest scene of each card is read from the show itself, so it is always right, whatever was done before.'))}</div>
  </div>`;
}

// ── Cards: by fixture type or by fixture group (3.11.0) ─────────────────────

function _brtCards() {
  if (_brtView === 'group' && _brtGroupsList.length) {
    const byId = Object.fromEntries(_brtFixtures.map(f => [String(f.id), f]));
    const cards = _brtGroupsList.map(g => ({ key: 'g:' + g.id, title: g.name, group: true,
      fixtures: g.fixtures.map(id => byId[String(id)]).filter(Boolean) })).filter(c => c.fixtures.length);
    const inGroup = new Set(cards.flatMap(c => c.fixtures.map(f => f.id)));
    const rest = _brtFixtures.filter(f => !inGroup.has(f.id));
    if (rest.length) cards.push({ key: 'g:_none', title: t('Not in any group'), group: true, fixtures: rest });
    return cards;
  }
  const groups = {}, order = [];
  for (const fx of _brtFixtures) {
    const mk = _brtModelKey(fx);
    if (!groups[mk]) { groups[mk] = { key: mk, fixtures: [], group: false }; order.push(mk); }
    groups[mk].fixtures.push(fx);
  }
  return order.map(k => groups[k]);
}

/** "Brightest scene to __%": Scale moves the slider so the brightest scene lands there and keeps
 *  every difference; Limit only brings down the scenes above it.  *keyJs* finds the card. */
function _brtLevelHtml(keyJs, cap, all, key) {
  const v = _brtLevelVal[key] ?? (cap !== '' && cap !== 'mixed' ? cap : '');
  return `<div class="brt-level${all ? ' brt-level-all' : ''}">
    <span>${_esc(all ? t('Every card: brightest scene to') : t('Brightest scene to'))}</span>
    <input type="number" min="1" max="100" step="1" class="brt-num brt-level-num" value="${v}" placeholder="90"
           title="${_esc(t('A level in % of full, for example 90'))}">
    <span class="brt-pct-label">%</span>
    <span class="brt-level-btns">
    <button class="btn btn-surface btn-sm" title="${_esc(t('Moves the slider so the brightest scene lands at this level. Every scene changes in proportion, so the differences between scenes stay.'))}"
            onclick="brtLevel(${keyJs}, 'scale', this)">${_esc(t('Scale'))}</button>
    <button class="btn btn-surface btn-sm" title="${_esc(t('Only the scenes above this level come down to it. The dimmer scenes stay as they are.'))}"
            onclick="brtLevel(${keyJs}, 'limit', this)">${_esc(t('Limit'))}</button>
    ${cap !== '' ? `<button class="btn btn-surface btn-sm" title="${_esc(t('Remove the limit'))}" onclick="brtLevel(${keyJs}, 'nolimit', this)">✕ ${_esc(t('limit'))}</button>` : ''}
    </span></div>`;
}

function brtLevel(key, how, btn) {
  const cards = key === '*' ? [{ key: '*', fixtures: _brtFixtures }] : _brtCards().filter(c => c.key === key);
  if (!cards.length) return;
  const fxs = cards[0].fixtures;
  if (how === 'nolimit') { fxs.forEach(f => delete _brtCaps[f.id]); _brtRender(); return; }
  const inp = btn.closest('.brt-level').querySelector('.brt-level-num');
  const lv = Math.round(Number(inp.value));
  if (!(lv >= 1 && lv <= 100)) { setStatus(t('Type a level from 1 to 100%.'), 'warn'); inp.focus(); return; }
  _brtLevelVal[key] = lv;
  if (how === 'limit') {
    fxs.forEach(f => { if (lv >= 100) delete _brtCaps[f.id]; else _brtCaps[f.id] = lv; });
    setStatus(t('Limit {0}%: the scenes above it come down to it when you apply.', lv), 'ok');
    _brtRender();
    return;
  }
  // scale: per card, so that card's brightest scene lands at the level (a card of all = each fixture type)
  const groups = key === '*' ? _brtCards() : cards;
  let skipped = 0;
  for (const c of groups) {
    const { peak } = _brtRoom(c.fixtures);
    if (!peak) { skipped++; continue; }
    const sc = Math.max(0, Math.min(2, lv / peak));
    c.fixtures.forEach(f => { _brtScales[f.id] = Math.round(sc * 100) / 100; });
  }
  setStatus(t('Sliders set so the brightest scene lands at {0}%.', lv) + (skipped ? ' ' + t('{0} card(s) without dimmer values left as they are.', skipped) : ''), 'ok');
  _brtRender();
}

function brtView(v) {
  _brtView = v === 'group' ? 'group' : 'type';
  try { localStorage.setItem('sk.brt.view', _brtView); } catch (e) { /* private window */ }
  _brtRender();
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function _brtRender() {
  const wrap = document.getElementById('brt-fixture-wrap');
  if (!wrap) return;

  if (!_brtFixtures.length) {
    wrap.innerHTML = '<div class="brt-placeholder">No fixtures found in the loaded workspace.</div>';
    return;
  }

  const hasGroups = _brtGroupsList.length > 0;
  let html = _brtHistoryHtml() + `<div class="brt-allbar">${_brtLevelHtml("'*'", _brtCardCap(_brtFixtures), true, '*')}</div>
  <div class="brt-viewbar">
    <span>${_esc(t('Sliders by'))}</span>
    <label><input type="radio" name="brt-view" ${_brtView !== 'group' ? 'checked' : ''} onchange="brtView('type')"> ${_esc(t('fixture type'))}</label>
    <label title="${_esc(hasGroups ? t('The fixture groups of the show. A fixture in several groups keeps the value you set last.') : t('This show has no fixture groups (make them in Stage & Meshes › Groups).'))}">
      <input type="radio" name="brt-view" ${_brtView === 'group' ? 'checked' : ''} ${hasGroups ? '' : 'disabled'} onchange="brtView('group')"> ${_esc(t('fixture group'))}</label>
  </div>`;

  for (const card of _brtCards()) {
    const mk     = card.key;
    const fxs    = card.fixtures;
    const fx0    = fxs[0];
    const linked = _brtLinked[mk] !== false;
    const noQxf  = fxs.some(f => !f.qxf_found);
    const grpScale = fxs.reduce((s2, f) => s2 + (_brtScales[f.id] ?? 1), 0) / fxs.length;
    const pct    = Math.round(grpScale * 100);
    const mkSafe = _esc(mk);

    const qxfBadge = noQxf
      ? `<span class="brt-badge brt-badge-warn" title="QXF not found — enter dimmer channel manually, upload/fetch the QXF, or assign one below">⚠ No QXF</span>`
      : `<span class="brt-badge brt-badge-ok"   title="QXF loaded from: ${_esc(fx0.qxf_path || 'local filesystem')}">✓ QXF</span>`;

    const mfrSafe   = _esc(fx0.manufacturer);
    const modelSafe = _esc(fx0.model);
    const assignId  = `brt-assign-${mkSafe.replace(/[^a-z0-9]/gi,'_')}`;
    const title = card.group
      ? `<strong data-i18n="off">${_esc(card.title)}</strong> <span class="brt-group-mode">${_esc(t('{0} fixtures', fxs.length))}</span>`
      : `<strong>${mfrSafe} ${modelSafe}</strong> <span class="brt-group-mode">${_esc(fx0.mode)}</span>`;

    html += `
    <div class="brt-group" data-model="${mkSafe}">
      <div class="brt-group-header">
        <span class="brt-group-name">${title} ${qxfBadge}</span>
        ${_brtRoomHtml(fxs, pct)}
        <label class="brt-link-label" title="Move all fixtures of this card together">
          <input type="checkbox" class="brt-link-cb"
                 data-model="${mkSafe}" ${linked ? 'checked' : ''}
                 onchange="brtToggleLink(this)">
          Link group
        </label>
        ${card.group ? '' : `
        <label class="btn btn-surface brt-assign-qxf-btn"
               title="Manually assign a QXF file to this fixture group, bypassing automatic name matching">
          <svg class="ic" aria-hidden="true"><use href="/static/icons.svg#folder"/></svg> Assign QXF
          <input type="file" accept=".qxf" style="display:none" id="${assignId}"
                 onchange="brtAssignQxf(this,'${mfrSafe}','${modelSafe}')">
        </label>`}
        ${linked ? `
        <div class="brt-group-slider">
          <input type="range"  min="0" max="200" step="1" value="${pct}" class="brt-slider"
                 data-model="${mkSafe}" data-linked="1" oninput="brtGroupSlider(this)">
          <div class="brt-group-num">
            <input type="number" min="0" max="200" step="1" value="${pct}" class="brt-num"
                   data-model="${mkSafe}" data-linked="1" oninput="brtGroupNum(this)">
            <span class="brt-pct-label">%</span>
            <button class="btn btn-surface brt-reset-btn" title="Back to 100%"
                    onclick="brtResetGroup(this.closest('.brt-group').dataset.model)">↺ 100%</button>
          </div>
        </div>` : ''}
        ${_brtLevelHtml(`this.closest('.brt-group').dataset.model`, _brtCardCap(fxs), false, mk)}
      </div>
      <div class="brt-fixture-list ${linked ? 'brt-list-linked' : ''}">`;

    for (const fx of fxs) {
      const fPct    = Math.round((_brtScales[fx.id] ?? 1) * 100);
      const manualVal = _brtManual[fx.id];
      const autoOff   = fx.dimmer_offset;
      const doff      = manualVal !== undefined ? manualVal : (autoOff ?? '');
      const hasAuto   = autoOff !== null && autoOff !== undefined;
      const chLabel   = hasAuto && manualVal === undefined
        ? `${fx.channels}&nbsp;ch&nbsp;·` : '';
      const chClass   = (!hasAuto || manualVal !== undefined) ? 'brt-manual-ch' : 'brt-manual-ch brt-ch-override';
      const chTitle   = hasAuto
        ? (manualVal !== undefined
            ? `Manual override active (auto-detected: ch ${autoOff}). Clear to revert.`
            : `Auto-detected from QXF. Edit to override.`)
        : '0-indexed DMX channel offset for Master Dimmer (required — QXF not found)';

      html += `
        <div class="brt-fixture-row" data-id="${_esc(fx.id)}">
          <span class="brt-fx-name"><span data-i18n="off">${_esc(fx.name)}</span>${_brtFxRoomHtml(fx)}</span>
          <label class="brt-manual-label" title="${_esc(chTitle)}">
            ${chLabel} Dimmer&nbsp;ch:
            <input type="number" min="0" max="511" step="1"
                   class="${chClass}" value="${_esc(String(doff))}"
                   placeholder="${hasAuto ? autoOff : '?'}"
                   data-id="${_esc(fx.id)}" data-auto="${hasAuto ? autoOff : ''}"
                   oninput="brtSetManual(this)">
          </label>
          <div class="brt-slider-row" style="${linked ? 'opacity:0.45;pointer-events:none' : ''}">
            <input type="range"  min="0" max="200" step="1" value="${fPct}" class="brt-slider"
                   data-id="${_esc(fx.id)}" oninput="brtFixtureSlider(this)">
            <input type="number" min="0" max="200" step="1" value="${fPct}" class="brt-num"
                   data-id="${_esc(fx.id)}" oninput="brtFixtureNum(this)">
            <span class="brt-pct-label">%</span>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  wrap.innerHTML = html;
  _brtSchedulePreview();
}

// ── GitHub fetch button state ─────────────────────────────────────────────────

function _brtUpdateFetchBtn() {
  const btn = document.getElementById('brt-fetch-gh-btn');
  if (!btn) return;
  const n = _brtMissingFixtures().length;
  btn.disabled = n === 0;
  btn.title = n
    ? `Fetch QXF definitions for ${n} unrecognised fixture type(s) from GitHub (internet)`
    : 'All fixtures already matched locally';
}

// ── Slider / input handlers ───────────────────────────────────────────────────

function brtGroupSlider(el) { _brtSyncGroup(el.dataset.model, parseInt(el.value, 10)); }
function brtGroupNum(el)    { _brtSyncGroup(el.dataset.model, Math.max(0, Math.min(200, parseInt(el.value, 10) || 0))); }
function brtFixtureSlider(el) { _brtSyncFixture(el.dataset.id, parseInt(el.value, 10)); }
function brtFixtureNum(el)    { _brtSyncFixture(el.dataset.id, Math.max(0, Math.min(200, parseInt(el.value, 10) || 0))); }
function brtToggleLink(cb)  { _brtLinked[cb.dataset.model] = cb.checked; _brtRender(); }
function brtResetGroup(mk)  {
  const card = _brtCards().find(c => c.key === mk);
  if (card && card.fixtures.some(f => _brtCaps[f.id] !== undefined)) { card.fixtures.forEach(f => delete _brtCaps[f.id]); _brtSyncGroup(mk, 100); _brtRender(); return; }
  _brtSyncGroup(mk, 100);
}
function brtResetAll()      { for (const fx of _brtFixtures) _brtScales[fx.id] = 1.0; _brtCaps = {}; _brtRender(); }
function brtSetManual(el) {
  const raw = el.value.trim();
  const val = parseInt(raw, 10);
  if (raw === '' || isNaN(val)) {
    // Clear: revert to auto-detected value (stored in data-auto)
    delete _brtManual[el.dataset.id];
    el.classList.add('brt-ch-override');
    el.classList.remove('brt-ch-override'); // triggers re-style on next render
  } else if (val >= 0) {
    _brtManual[el.dataset.id] = val;
    el.classList.add('brt-ch-override');
  }
  _brtSchedulePreview();
}

// ── Assign QXF to a specific fixture group ────────────────────────────────────

async function brtAssignQxf(input, manufacturer, model) {
  if (!input.files?.length) return;
  const file = input.files[0];
  const fd   = new FormData();
  fd.append('file',         file);
  fd.append('manufacturer', manufacturer);
  fd.append('model',        model);
  setStatus(`Assigning ${file.name} to ${manufacturer} ${model}…`);
  let resp;
  try {
    resp = await fetch('/api/brightness/assign-qxf', { method: 'POST', body: fd });
  } catch (e) { setStatus('Upload error: ' + e.message, 'error'); return; }
  const res = await resp.json();
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(res.message || 'QXF assigned.', 'ok');
  input.value = '';
  _brtLoaded  = false;
  await _brtLoadFixtures();
}

// ── Internal sync helpers ─────────────────────────────────────────────────────

function _brtSyncGroup(mk, pct) {
  const card = _brtCards().find(c => c.key === mk);
  if (!card) return;
  const scale = pct / 100;
  for (const fx of card.fixtures) _brtScales[fx.id] = scale;
  for (const el of document.querySelectorAll(`[data-model="${CSS.escape(mk)}"][data-linked="1"]`)) el.value = pct;
  _brtRefreshValues(mk);
}

function _brtSyncFixture(id, pct) {
  _brtScales[id] = pct / 100;
  _brtRefreshValues(null);
}

/** After a change: every fixture input, every other card's slider (a fixture may be in
 *  several groups) and the room notes follow the values; *skip* is the card being moved. */
function _brtRefreshValues(skip) {
  for (const el of document.querySelectorAll('.brt-fixture-row .brt-slider, .brt-fixture-row .brt-num')) {
    const v = Math.round((_brtScales[el.dataset.id] ?? 1) * 100);
    if (document.activeElement !== el) el.value = v;
  }
  for (const card of _brtCards()) {
    const pct = Math.round(card.fixtures.reduce((s2, f) => s2 + (_brtScales[f.id] ?? 1), 0) / card.fixtures.length * 100);
    const box = document.querySelector(`.brt-group[data-model="${CSS.escape(card.key)}"]`);
    if (!box) continue;
    if (card.key !== skip)
      for (const el of box.querySelectorAll('[data-linked="1"]')) if (document.activeElement !== el) el.value = pct;
    const room = box.querySelector('.brt-room');
    if (room) room.outerHTML = _brtRoomHtml(card.fixtures, pct);
  }
  _brtSchedulePreview();
}

// ── Preview (debounced) ───────────────────────────────────────────────────────

function _brtSchedulePreview() {
  clearTimeout(_brtPreviewTm);
  _brtPreviewTm = setTimeout(_brtFetchPreview, 350);
}

async function _brtFetchPreview() {
  if (!_brtFixtures.length) return;
  const res = await _apiJson('/api/brightness/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scales: _brtBuildScales(), caps: _brtBuildCaps() }),
  });
  if (!res.error) _brtSetPreview(res);
}

function _brtSetPreview(stats) {
  const el = document.getElementById('brt-preview');
  if (!el) return;
  if (!stats) { el.textContent = ''; el.className = 'brt-preview-count'; setOutcome('brightness', ''); return; }
  const { fixtures_active: f, scenes: s, values: v } = stats;
  setOutcome('brightness', v ? [skPlural(f, '{0} fixture', '{0} fixtures'), skPlural(s, '{0} scene', '{0} scenes'), skPlural(v, '{0} value', '{0} values')]
    : 'nothing yet — move a slider', '', v ? 'Apply will change' : 'Apply will do');
  el.textContent = t('{0} will change', [skPlural(f, '{0} fixture', '{0} fixtures'), skPlural(s, '{0} scene', '{0} scenes'), skPlural(v, '{0} value', '{0} values')].join(', '));
  el.className   = `brt-preview-count ${v > 0 ? 'brt-preview-active' : ''}`;
  // 3.11.0: say when going brighter cuts scenes at full, or dimming switches lit scenes off
  const warn = [];
  if (stats.clipped) warn.push(t('{0} value(s) would go above full: they stay at 100%, so some scenes look alike', stats.clipped));
  if (stats.to_zero) warn.push(t('{0} lit value(s) would go dark', stats.to_zero));
  if (stats.capped) el.textContent += ' · ' + t('{0} value(s) brought down to the limit', stats.capped);
  if (warn.length) { el.textContent += ' · ⚠ ' + warn.join(' · '); el.classList.add('brt-preview-warn'); }
}

// ── Generate QXW ──────────────────────────────────────────────────────────────

async function brtGenerateQxw() {
  if (!_brtFixtures.length) { setStatus('Load a workspace first.', 'warn'); return; }
  const scales = _brtBuildScales();
  const caps = _brtBuildCaps();
  if (!Object.values(scales).some(v => Math.abs(v - 1.0) > 0.001) && !Object.keys(caps).length) {
    setStatus('All fixtures are at 100% — nothing to change.', 'warn'); return;
  }
  setStatus('Generating…');
  let resp;
  try {
    resp = await fetch('/api/brightness/apply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scales, caps, manual_dimmer_offsets: _brtManual }),
    });
  } catch (e) { setStatus('Network error: ' + e.message, 'error'); return; }
  if (!resp.ok) {
    try { const err = await resp.json(); setStatus(err.error || 'Failed.', 'error'); }
    catch { setStatus('Generate failed.', 'error'); }
    return;
  }
  const blob  = await resp.blob();
  const fname = resp.headers.get('X-Suggested-Filename') || 'workspace_BRIGHTNESS.qxw';
  const scenes = resp.headers.get('X-Scenes-Modified') || '?';
  const vals   = resp.headers.get('X-Values-Changed')  || '?';
  const savedName = await saveFileWithPicker(
    blob, fname,
    [{ description: 'QLC+ Workspace', accept: { 'application/xml': ['.qxw'] } }],
    'Save brightness-adjusted workspace as'
  );
  if (!savedName) return;  // user cancelled
  setStatus(`✓ Saved ${savedName} — ${scenes} scenes, ${vals} channel values adjusted`, 'ok');
}

// ── Upload QXF (one or many) ──────────────────────────────────────────────────

async function brtUploadQxf() {
  const inp = document.getElementById('brt-qxf-input');
  if (!inp?.files?.length) { setStatus('Choose one or more .qxf files.', 'warn'); return; }
  const fd = new FormData();
  for (const f of inp.files) fd.append('file', f);
  setStatus(`Uploading ${inp.files.length} QXF file(s)…`);
  let resp;
  try {
    resp = await fetch('/api/brightness/upload-qxf', { method: 'POST', body: fd });
  } catch (e) { setStatus('Upload error: ' + e.message, 'error'); return; }
  const res = await resp.json();
  const errNote = res.errors?.length ? ' (' + res.errors.join('; ') + ')' : '';
  setStatus((res.message || 'Done.') + errNote, res.saved?.length ? 'ok' : 'warn');
  inp.value = '';
  _brtLoaded = false;
  await _brtLoadFixtures();
}

// ── Scan local fixture directories ────────────────────────────────────────────

async function brtScanLocal() {
  setStatus('Scanning local QLC+ fixture directories…');
  let res;
  try { res = await _apiJson('/api/brightness/scan-local'); }
  catch (e) { setStatus('Scan error: ' + e.message, 'error'); return; }
  if (res.error) { setStatus(res.error, 'error'); return; }

  const total   = res.total_qxf_files ?? 0;
  const matched = res.fixtures_matched?.length ?? 0;
  const missing = res.fixtures_missing?.length ?? 0;
  const ndirs   = res.dirs?.length ?? 0;
  let msg = `Local: ${total} QXF file(s) in ${ndirs} director${ndirs!==1?'ies':'y'}. `;
  msg += matched ? `✓ ${matched} fixture type(s) matched. ` : '';
  msg += missing ? `⚠ ${missing} still unmatched.` : (matched ? 'All fixtures matched!' : '');
  setStatus(msg, (matched > 0 || total > 0) ? 'ok' : 'warn');

  _brtLoaded = false;
  await _brtLoadFixtures();
}

// ── Fetch from GitHub (internet) ──────────────────────────────────────────────

async function brtFetchGithub() {
  const missing = _brtMissingFixtures();
  if (!missing.length) { setStatus('All fixtures already matched — nothing to fetch.', 'warn'); return; }

  // Always show explicit internet-connection warning
  const nameList = missing.map(f => `  • ${f.manufacturer} ${f.model}`).join('\n');
  const ok = confirm(
    `⚠ INTERNET CONNECTION REQUIRED\n\n` +
    `This will make outbound HTTP requests to:\n` +
    `  • api.github.com\n` +
    `  • raw.githubusercontent.com\n\n` +
    `Fixtures to look up (${missing.length}):\n${nameList}\n\n` +
    `Downloaded QXF files will be saved next to your workspace.\n\n` +
    `Continue?`
  );
  if (!ok) return;

  setStatus(`Connecting to GitHub — looking up ${missing.length} fixture type(s)…`);
  let res;
  try {
    res = await _apiJson('/api/brightness/fetch-github', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixtures: missing }),
    });
  } catch (e) { setStatus('Network error: ' + e.message, 'error'); return; }
  if (res.error) { setStatus('' + res.error, 'error'); return; }

  const dl  = res.downloaded?.length ?? 0;
  const nf  = res.not_found?.length  ?? 0;
  const err = res.errors?.length     ?? 0;
  let msg = `GitHub: `;
  if (dl)  msg += `✓ ${dl} QXF file(s) downloaded. `;
  if (nf)  msg += `⚠ ${nf} fixture(s) not found on GitHub. `;
  if (err) msg += `✗ ${err} error(s). `;
  if (!dl && !nf && !err) msg += 'No results.';
  setStatus(msg, dl ? 'ok' : 'warn');

  if (dl) { _brtLoaded = false; await _brtLoadFixtures(); }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _brtBuildCaps() {
  const out = {};
  for (const fx of _brtFixtures) if (_brtCaps[fx.id] !== undefined && _brtCaps[fx.id] < 100) out[fx.id] = _brtCaps[fx.id];
  return out;
}

function _brtBuildScales() {
  const out = {};
  for (const fx of _brtFixtures) out[fx.id] = _brtScales[fx.id] ?? 1.0;
  return out;
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
