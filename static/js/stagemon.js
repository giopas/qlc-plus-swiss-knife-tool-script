/**
 * Tablet on stage (3.9.0; the Stage Monitor of 3.5.0 with song cards).
 *
 * Two modes in one screen: the Live monitor (a page that follows QLC+: song cards,
 * the Next song banner, role views) and the Simple page (one .html from the
 * Setlist, no network).  The first screen on the page kit (kit.css, kit.js).
 * /api/stagemon/lists reads the show (only reads it); every change here is kept
 * in <show>.stage.json; Export writes index.html + serve_stage.py; Serve shares
 * the folder on the network.
 */

let _sm = null;              // {lists, config, missing, new, folder, server, ...}
let _smSaveT = null;
let _smMode = 'live';        // 'live' | 'simple'
let _smPaneKey = 'card';     // 'card' | 'page' | 'send'
let _smCur = '';             // the cue list shown on the left
let _smSel = -1;             // the song (step index) whose card is open
let _smSeg = null, _smBar = null, _smDict = null;

const _SM_TUNINGS = ['E standard', 'Eb standard', 'D standard', 'Drop D', 'Drop C', 'DADGAD', 'Open G', 'Open D'];
const _SM_NAME_BPM = /[·•\-–—|]\s*(\d{2,3}(?:[.,]\d)?)\s*bpm\s*$/i;   // "Song · 128 BPM", as Apply tempo writes it
const _smTempoOf = name => {
  const m = _SM_NAME_BPM.exec(name || '');
  const v = m ? Math.round(parseFloat(m[1].replace(',', '.'))) : 0;
  return v >= 20 && v <= 400 ? v : 0;
};

function stagemonInit() {
  _smChrome();
  if (!_sm) stagemonLoad();
  else _smStatus();
}

// the cards keep show names untranslated (data-i18n="off"): draw them again in a new language
document.addEventListener('sk-lang', () => { if (_sm) _smRender(); });

function invalidateStagemon() {
  _sm = null; _smSel = -1; _smCur = ''; _smDict = null;
  const el = document.getElementById('sm-lists');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace with a CueList on its Virtual Console.</div>';
  _smCardPane(); _smSync();
  if (document.getElementById('scr-stagemon')?.classList.contains('active')) stagemonLoad();
}

async function stagemonLoad() {
  try {
    const r = await fetch('/api/stagemon/lists');
    const d = await r.json();
    if (!r.ok) { _sm = null; _smSync(); _smCardPane(); return; }
    _sm = d;
    _smRender();
  } catch (e) { /* no workspace */ }
}

// ── the page kit: mode switch and action bar, built once ─────────────────────
function _smChrome() {
  const host = document.getElementById('sm-mode');
  if (host && !_smSeg) {
    _smSeg = skSegmented({options: [{value: 'live', label: 'Live monitor'}, {value: 'simple', label: 'Simple page'}],
                          value: _smMode, onchange: stagemonMode});
    host.appendChild(_smSeg.el);
  }
  if (!_smBar && document.getElementById('sm-actionbar')) {
    _smBar = skActionBar({
      target: '#sm-actionbar',
      chip: () => _smMode === 'simple' ? 'export' : 'beside',
      summary: _smBarSummary,
      secondary: {label: 'Preview', onclick: () => stagemonPreview(), disabled: () => !_smCanExport(), hidden: () => _smMode === 'simple'},
      primary: {label: () => _smMode === 'simple' ? 'Export the page…' : 'Export the page',
                onclick: () => _smMode === 'simple' ? stagemonSimpleExport() : stagemonExport(),
                disabled: () => _smMode === 'live' && !_smCanExport()},
      why: 'Put at least one cue list on the page: tick it on the left.',
    });
  }
}

function stagemonMode(m) {
  _smChrome();
  _smMode = m === 'simple' ? 'simple' : 'live';
  if (_smSeg) _smSeg.set(_smMode);
  document.getElementById('sm-live').hidden = _smMode !== 'live';
  document.getElementById('sm-simple').hidden = _smMode !== 'simple';
  _smSync();
}

function stagemonPane(p) {
  _smPaneKey = ['card', 'page', 'send'].includes(p) ? p : 'card';
  for (const k of ['card', 'page', 'send']) {
    document.getElementById('sm-p-' + k).hidden = k !== _smPaneKey;
    const tab = document.getElementById('sm-t-' + k);
    tab.classList.toggle('on', k === _smPaneKey);
    tab.setAttribute('aria-selected', String(k === _smPaneKey));
  }
  if (_smPaneKey === 'card') _smCardPane();
}

const _smCanExport = () => !!_sm && _smCfg().lists.length > 0;
function _smBarSummary() {
  if (_smMode === 'simple') return 'One .html file with every setlist. The show is not touched.';
  if (!_sm || !_smCfg().lists.length) return '';
  return `Reads the show, writes the page and ${_sm.sidecar || 'the settings file'}`;
}

const _smCfg = () => _sm.config;
const _smItem = id => _smCfg().lists.find(x => x.id === String(id));
const _smList = id => _sm.lists.find(x => x.id === String(id));

function _smWhere(cl) {
  const parts = [...cl.path];
  if (cl.frame_page) parts.push(cl.frame_page.name || `page ${cl.frame_page.page + 1}`);
  return parts.join(' › ');
}

// the tuning of the song before, as the page works it out: hidden songs and songs with no tuning do not count
function _smChange(it, cl, idx) {
  let last = '';
  for (const st of cl.steps) {
    const s = it.steps[String(st.index)] || {};
    if (s.hide) continue;
    const t = (s.card && s.card.tuning) || '';
    if (st.index === idx) return last && t && t !== last ? {from: last, to: t} : null;
    if (t) last = t;
  }
  return null;
}

// ── the songs of a cue list, and its settings ────────────────────────────────
function _smRender() {
  if (!_sm) return;
  const cfg = _smCfg();
  const el = document.getElementById('sm-lists');
  const note = document.getElementById('sm-notice');
  const warn = [];
  if (_sm.missing.length)
    warn.push(_esc(`Gone from the show since the last export: ${_sm.missing.map(m => m.label || m.id).join(', ')}`));
  if (_sm.new.length && _sm.saved)
    warn.push(_esc(`New in the show, not on the page yet: ${_sm.new.map(id => (_smList(id) || {}).caption || id).join(', ')}`));
  note.innerHTML = warn.map(w => `<div class="sm-warn">${w}</div>`).join('');

  if (!_sm.lists.length) {
    el.innerHTML = `<div class="porter-placeholder">${_esc('This show has no CueList on its Virtual Console. Add one with the Setlist or the VC Visual Editor.')}</div>`;
    _smSettings(); _smCardPane(); _smSync(); return;
  }
  if (!_smList(_smCur)) _smCur = (cfg.lists[0] && cfg.lists[0].id) || _sm.lists[0].id;
  const cl = _smList(_smCur), it = _smItem(_smCur);
  const pos = it ? cfg.lists.indexOf(it) : -1;

  const tabs = _sm.lists.map(c => {
    const on = !!_smItem(c.id);
    return `<button type="button" class="sm-tab${c.id === _smCur ? ' sel' : ''}${on ? ' on' : ''}" onclick="stagemonList_('${c.id}')"
      title="${_esc(on ? 'On the page' : 'Not on the page')}"><span class="sm-dot"></span><span data-i18n="off">${_esc(c.caption || `CueList ${c.id}`)}</span></button>`;
  }).join('');
  const ch = cl.chaser ? _esc(cl.chaser.name) : `<span class="doc-error">${_esc(t('no chaser'))}</span>`;
  const ins = Object.entries(cl.inputs || {}).map(([k, v]) => `${_esc(k)}: ${_esc(v.join(', '))}`).join(' · ');
  const head = `<div class="sm-listcfg">
      <label class="sm-check"><input type="checkbox" ${it ? 'checked' : ''} ${cl.chaser ? '' : 'disabled'} onchange="stagemonTick('${cl.id}', this.checked)"> <b>${_esc('On the tablet page')}</b></label>
      ${it ? `<input class="field-input" maxlength="80" value="${_esc(it.label)}" placeholder="${_esc(cl.caption || 'Label on the page')}" data-i18n="${cl.caption ? 'off' : ''}"
               oninput="stagemonList('${cl.id}', 'label', this.value)" title="Label on the page (the CueList's caption when empty)">
        <select class="field-input" style="width:auto" onchange="stagemonList('${cl.id}', 'mode', this.value)"
                title="Read-only: the tablet only shows the cues; nothing on it changes the show. Control: the page also has Previous, Stop and Next buttons that work this cue list in QLC+ like its own buttons or the pedal. Previous and Next act after the safety hold set on the Page tab, Stop after a longer one.">
          <option value="read"${it.mode === 'read' ? ' selected' : ''}>${_esc('Read-only: shows the cues')}</option>
          <option value="control"${it.mode === 'control' ? ' selected' : ''}>${_esc('Control: adds Previous / Stop / Next (hold)')}</option>
        </select>
        <button class="btn btn-surface btn-sm sm-ord" onclick="stagemonMove('${cl.id}', -1)" ${pos <= 0 ? 'disabled' : ''} title="Earlier on the page">↑</button>
        <button class="btn btn-surface btn-sm sm-ord" onclick="stagemonMove('${cl.id}', 1)" ${pos >= cfg.lists.length - 1 ? 'disabled' : ''} title="Later on the page">↓</button>` : ''}
    </div>
    <div class="sm-meta sm-meta-flat" data-i18n="off">${_esc(_smWhere(cl))} · ${ch}${ins ? `<br>${ins}` : ''}</div>`;
  el.innerHTML = `<div class="sm-tabs" role="tablist">${tabs}</div>${head}<div id="sm-songs"></div>`;
  _smSongs();
  _smSettings();
  _smCardPane();
  _smSync();
}

function stagemonList_(id) {          // show another cue list on the left
  _smCur = String(id); _smSel = -1;
  _smRender();
}

// the song rows alone: they are drawn again on every change of a card, so the card's fields keep their focus
function _smSongs() {
  const box = document.getElementById('sm-songs');
  if (!box || !_sm) return;
  const cl = _smList(_smCur), it = _smItem(_smCur);
  if (!cl) { box.innerHTML = ''; return; }
  if (!it) {
    box.innerHTML = `<div class="porter-placeholder">${_esc('Tick “On the tablet page” to choose its songs and write their cards.')}</div>`;
    return;
  }
  const rows = cl.steps.map(st => {
    const s = it.steps[String(st.index)] || {};
    const c = s.card || {};
    const bpm = c.bpm || _smTempoOf(st.name);
    const tc = _smChange(it, cl, st.index);
    const chips = [
      bpm ? `<span class="sm-chip" title="${_esc('Tempo')}">♪ ${bpm}</span>` : '',
      c.tuning ? `<span class="sm-chip${tc ? ' warn' : ''}" title="${_esc(tc ? 'The tuning changes from the song before' : 'Tuning')}">${tc ? '▲ ' : ''}${_esc(c.tuning)}</span>` : '',
      (c.starts || c.note || (c.players || []).length) ? `<span class="sm-chip" title="${_esc('This song has a card')}">${_esc('card')}</span>` : '',
    ].join('');
    return `<tr class="sm-song${s.hide ? ' sm-hidden' : ''}${st.index === _smSel ? ' sel' : ''}" data-i="${st.index}">
      <td><input type="checkbox" ${s.hide ? '' : 'checked'} title="Show this step on the page"
                 onchange="stagemonStep('${cl.id}', ${st.index}, 'hide', !this.checked)"></td>
      <td class="sm-n">${st.index + 1}</td>
      <td class="sm-fn" tabindex="0" role="button" onclick="stagemonSelect(${st.index})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();stagemonSelect(${st.index})}"
          data-i18n="off">${_esc(st.name)}${st.note ? `<div class="sm-meta" style="margin:0">${_esc(st.note)}</div>` : ''}</td>
      <td class="sm-chips">${chips}</td>
      <td><input class="field-input" maxlength="120" value="${_esc(s.label || '')}" placeholder="${_esc('Name on the page')}"
                 oninput="stagemonStep('${cl.id}', ${st.index}, 'label', this.value)"></td>
    </tr>`;
  }).join('');
  box.innerHTML = `<div class="sm-steps"><table>${rows}</table></div>`;
}

function stagemonSelect(idx) {
  _smSel = idx;
  _smSongs();
  stagemonPane('card');
}

// ── the song card ────────────────────────────────────────────────────────────
function _smField(label, inner) { return `<label class="sm-field"><span>${_esc(label)}</span>${inner}</label>`; }

async function _smDictionary() {
  if (_smDict) return _smDict;
  try {
    const r = await fetch('/api/dictionary/');
    const rows = r.ok ? await r.json() : [];
    _smDict = new Map(rows.filter(x => x.desc).map(x => [String(x.id), x.desc]));
  } catch (e) { _smDict = new Map(); }
  return _smDict;
}

function _smCardPane() {
  const box = document.getElementById('sm-p-card');
  if (!box) return;
  const hint = m => { box.innerHTML = `<div class="porter-placeholder">${_esc(m)}</div>`; };
  if (!_sm) return hint('Open a show with a CueList to write song cards.');
  const cl = _smList(_smCur), it = _smItem(_smCur);
  if (!cl) return hint('Open a show with a CueList to write song cards.');
  if (!it) return hint('Put this cue list on the page (tick it on the left) to write cards for its songs.');
  const st = cl.steps[_smSel];
  if (!st) return hint('Choose a song on the left. Its card is what each player sees on the tablet.');
  const s = it.steps[String(st.index)] || {};
  const c = s.card || {};
  const own = _smTempoOf(st.name);
  const used = new Set(_SM_TUNINGS);
  Object.values(it.steps).forEach(x => { if (x.card && x.card.tuning) used.add(x.card.tuning); });
  const players = (c.players || []).map((p, i) => `<div class="sm-pl">
      <input class="field-input" maxlength="30" value="${_esc(p.who || '')}" placeholder="${_esc('Player')}" oninput="stagemonPlayer(${i}, 'who', this.value)">
      <input class="field-input" maxlength="80" value="${_esc(p.note || '')}" placeholder="${_esc('Pedal or FX')}" oninput="stagemonPlayer(${i}, 'note', this.value)">
      <button class="btn btn-surface btn-sm" onclick="stagemonDelPlayer(${i})" title="Remove this line" aria-label="Remove this line">✕</button></div>`).join('');
  box.innerHTML = `
    <div class="sm-card-h"><span class="sm-n">${st.index + 1}</span> <b data-i18n="off">${_esc(s.label || st.name)}</b></div>
    ${_smField('Tuning', `<input class="field-input" list="sm-tunings" maxlength="40" value="${_esc(c.tuning || '')}" oninput="stagemonCard('tuning', this.value)">
       <datalist id="sm-tunings">${[...used].map(x => `<option value="${_esc(x)}">`).join('')}</datalist>`)}
    <div class="sm-tc" id="sm-tc" aria-live="polite"></div>
    ${_smField('Tempo', `<span class="sm-tempo">${own ? _esc(`${own} BPM from the Setlist`) : _esc('No tempo set on the Setlist')}</span>
       <input class="field-input sm-bpm" type="number" min="20" max="400" value="${c.bpm || ''}" placeholder="${own || 'BPM'}" title="A tempo of your own for this card: it wins over the Setlist's"
              oninput="stagemonCard('bpm', this.value)">`)}
    ${_smField('Starts', `<input class="field-input" maxlength="80" value="${_esc(c.starts || '')}" placeholder="${_esc('Drums, 4 bars count-in')}" oninput="stagemonCard('starts', this.value)">`)}
    <div class="sm-field sm-players"><span>${_esc('Per player')}</span><div>${players}
      <button class="btn btn-surface btn-sm" onclick="stagemonAddPlayer()" ${(c.players || []).length >= 8 ? 'disabled' : ''}>${_esc('+ Add a player')}</button></div></div>
    ${_smField('Note', `<input class="field-input" maxlength="200" id="sm-card-note" value="${_esc(c.note || '')}" placeholder="${_esc('Capo 2')}" oninput="stagemonCard('note', this.value)">`)}
    <div class="sm-dictline" id="sm-dictline"></div>
    <div class="sm-card-f"><button class="btn btn-surface btn-sm" onclick="stagemonClearCard()" ${Object.keys(c).length ? '' : 'disabled'}>${_esc('Clear this card')}</button>
      <span class="sm-meta" style="margin:0">${_esc('Kept next to the show, with every version of it.')}</span></div>`;
  _smTcLine();
  _smDictionary().then(d => {
    const line = document.getElementById('sm-dictline');
    const text = d.get(String(st.fid));
    if (!line || !text || _smCl() !== cl.id + ':' + st.index) return;
    line.innerHTML = `<span class="sm-meta" style="margin:0" data-i18n="off">${_esc(text.length > 160 ? text.slice(0, 157) + '…' : text)}</span>
      <button class="btn btn-surface btn-sm" onclick="stagemonUseDictionary()">${_esc('Use the Dictionary text')}</button>`;
  });
}
const _smCl = () => _smCur + ':' + _smSel;

function _smTcLine() {
  const el = document.getElementById('sm-tc');
  const cl = _smList(_smCur), it = _smItem(_smCur);
  if (!el || !cl || !it) return;
  const tc = _smChange(it, cl, _smSel);
  el.textContent = tc ? `▲ ${t('Differs from the song before')}: ${tc.from} → ${tc.to}` : '';
}

function _smEditCard(fn) {
  const it = _smItem(_smCur);
  if (!it || _smSel < 0) return;
  const k = String(_smSel);
  const s = Object.assign({}, it.steps[k]);
  const card = JSON.parse(JSON.stringify(s.card || {}));
  fn(card);
  for (const f of ['tuning', 'starts', 'note']) if (!String(card[f] || '').trim()) delete card[f];
  const bpm = Math.round(+card.bpm);
  if (bpm >= 20 && bpm <= 400) card.bpm = bpm; else delete card.bpm;
  if (!(card.players || []).length) delete card.players;
  if (Object.keys(card).length) s.card = card; else delete s.card;
  if (Object.keys(s).length) it.steps[k] = s; else delete it.steps[k];
  _smChanged(false);
  _smSongs(); _smTcLine();
}

function stagemonCard(key, value) { _smEditCard(c => { c[key] = value; }); }
function stagemonPlayer(i, key, value) { _smEditCard(c => { if (c.players && c.players[i]) c.players[i][key] = value; }); }
function stagemonAddPlayer() { _smEditCard(c => { c.players = (c.players || []).concat([{who: '', note: ''}]).slice(0, 8); }); _smCardPane(); }
function stagemonDelPlayer(i) { _smEditCard(c => { (c.players || []).splice(i, 1); }); _smCardPane(); }
function stagemonClearCard() { _smEditCard(c => { Object.keys(c).forEach(k => delete c[k]); }); _smCardPane(); }
async function stagemonUseDictionary() {
  const cl = _smList(_smCur), st = cl && cl.steps[_smSel];
  const text = st && (await _smDictionary()).get(String(st.fid));
  if (!text) return;
  _smEditCard(c => { c.note = (c.note ? c.note + ' · ' : '') + text; c.note = c.note.slice(0, 200); });
  _smCardPane();
}

// ── the page's settings ──────────────────────────────────────────────────────
function _smSettings() {
  if (!_sm) return;
  const c = _smCfg();
  const set = (id, v) => { const e = document.getElementById(id); if (e && document.activeElement !== e) e.value = v; };
  set('sm-title', c.title);
  set('sm-simple-title', c.title);
  set('sm-wsport', c.ws_port);
  set('sm-httpport', c.http_port);
  document.getElementById('sm-next').checked = c.show_next;
  document.getElementById('sm-clock').checked = c.show_clock;
  document.getElementById('sm-numbers').checked = c.show_numbers;
  document.getElementById('sm-notes').checked = c.show_notes;
  document.querySelectorAll('#sm-font button').forEach(b => b.classList.toggle('on', b.dataset.v === c.font));
  set('sm-theme', c.theme);
  set('sm-hold', String(c.hold_ms));
  set('sm-folder', _sm.folder || '');
  setFileChip('sm-folder-chip', _sm.folder, 'no folder yet');
  _smServer(_sm.server);
}

function _smSync() {
  const n = _sm ? _smCfg().lists.length : 0;
  const s = document.getElementById('sm-summary');
  if (s) s.innerHTML = _sm
    ? `<span class="doc-chip">${_esc(`${_sm.lists.length} cue list(s) in the show`)}</span> <span class="doc-chip">${_esc(`${n} on the page`)}</span>`
    : '';
  if (_smBar) _smBar.update();
}

// ── edits (kept in <show>.stage.json) ────────────────────────────────────────
function _smChanged(redraw = false) {
  if (redraw) _smRender(); else _smSync();
  clearTimeout(_smSaveT);
  _smSaveT = setTimeout(_smSave, 400);
}

async function _smSave() {
  if (!_sm) return;
  try {
    const r = await fetch('/api/stagemon/config', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({config: _smCfg()}),
    });
    const d = await r.json();
    const el = document.getElementById('sm-saved');
    if (el) el.textContent = d.saved ? `Settings kept in ${d.sidecar}` : (d.note || d.error || '');
  } catch (e) { /* kept in the page until the next try */ }
}

function stagemonSet(key, value) {
  if (!_sm) return;
  _smCfg()[key] = value;
  _smSettings();
  _smChanged();
}

function stagemonTick(id, on) {
  const c = _smCfg();
  if (on && !_smItem(id)) c.lists.push({id: String(id), label: '', mode: 'read', steps: {}});
  if (!on) { c.lists = c.lists.filter(x => x.id !== String(id)); _smSel = -1; }
  _smChanged(true);
}

function stagemonList(id, key, value) {
  const it = _smItem(id);
  if (!it) return;
  it[key] = value;
  _smChanged(key === 'mode');
}

function stagemonMove(id, delta) {
  const L = _smCfg().lists;
  const i = L.findIndex(x => x.id === String(id));
  const j = i + delta;
  if (i < 0 || j < 0 || j >= L.length) return;
  [L[i], L[j]] = [L[j], L[i]];
  _smChanged(true);
}

function stagemonStep(id, index, key, value) {
  const it = _smItem(id);
  if (!it) return;
  const k = String(index);
  const s = Object.assign({}, it.steps[k]);
  if (key === 'hide') { if (value) s.hide = true; else delete s.hide; }
  if (key === 'label') { if (String(value).trim()) s.label = value; else delete s.label; }
  if (Object.keys(s).length) it.steps[k] = s; else delete it.steps[k];
  _smChanged(false);
  _smSongs(); _smCardPane();
}

// ── Simple page: the Setlist's one-file page ─────────────────────────────────
async function stagemonSimpleExport() {
  const notes = !!document.getElementById('sm-tab-notes')?.checked;
  const title = (_sm && _smCfg().title || '').trim();
  await slTabletPage({title, notes});
}

// ── folder, preview, export, serve ───────────────────────────────────────────
async function stagemonPickFolder() {
  const p = await nativePick('Folder for the Stage Monitor page', [], _sm && _sm.folder ? _sm.folder.replace(/[\\/][^\\/]*$/, '') : '', true);
  if (p) stagemonFolder(p);
  else if (nativePick.unavailable) document.getElementById('sm-folder')?.focus();
}

function stagemonFolder(p) {
  if (!_sm) return;
  _sm.folder = String(p || '').trim();
  _smSettings();
}

function _smLang() {
  return (typeof I18N !== 'undefined' && I18N.lang) || 'en';
}

async function stagemonPreview() {
  if (!_sm) return;
  try {
    // In the app's own window the server opens your browser (that window opens no new windows);
    // in a browser the preview opens in a new tab of that same browser, wherever Swiss Knife runs.
    const r = await fetch('/api/stagemon/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: _smCfg(), lang: _smLang(), open: true}),
    });
    const d = await r.json();
    if (!r.ok) { setStatus(d.error || 'Preview failed', 'error'); return; }
    if (d.opened) setStatus('Preview opened in your browser.');
    else window.open(d.url, '_blank');
  } catch (e) { setStatus('Preview failed', 'error'); }
}

// Replacing an earlier export is the one place Swiss Knife writes over files: it asks first.
const _SM_REPLACE = 'The folder already has a Stage Monitor page from an earlier export:\n\n{0}\n\n'
  + 'Replace these files? This is the only time Swiss Knife writes over files. They are the Stage Monitor\'s own; '
  + 'the show and every other file in the folder stay as they are.';

async function stagemonExport(replace = false) {
  if (!_sm) return;
  try {
    const r = await fetch('/api/stagemon/export', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: _smCfg(), folder: _sm.folder, lang: _smLang(), replace}),
    });
    const d = await r.json();
    if (r.status === 409 && d.replace && !replace) {
      const files = d.replace.map(f => '   ' + f).join('\n');
      if (confirm(t(_SM_REPLACE, files))) return stagemonExport(true);
      setStatus('Export cancelled: the earlier page was kept.', 'warn');
      return;
    }
    if (!r.ok) { setStatus(d.error || 'Export failed', 'error'); return; }
    _sm.folder = d.folder;
    _sm.saved = !!d.sidecar;
    _sm.missing = [];
    _smSettings();
    skDone(d.replaced && d.replaced.length
      ? `Exported to ${d.folder.split(/[\\/]/).pop()}, replacing ${d.replaced.length} file(s)`
      : `Exported to ${d.folder.split(/[\\/]/).pop()}`);
    setStatus(d.server && d.server.running
      ? `Stage Monitor page written: ${d.page}. The tablet gets it when the page is reloaded.`
      : 'Page exported. At the gig, double-click Start Stage Monitor in that folder (QLC+ must run with -w).');
  } catch (e) { setStatus('Export failed', 'error'); }
}

async function stagemonServe() {
  if (!_sm) return;
  const r = await fetch('/api/stagemon/serve', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({folder: _sm.folder, port: _smCfg().http_port}),
  });
  const d = await r.json();
  if (!r.ok) setStatus(d.error || 'Could not serve the page', 'error');
  _sm.server = d.server; _smServer(d.server);
}

async function stagemonOpenFolder() {
  const r = await fetch('/api/stagemon/open-folder', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({folder: _sm ? _sm.folder : ''}),
  });
  const d = await r.json();
  if (!r.ok) setStatus(d.error || 'Could not open the folder', 'error');
}

async function stagemonStop() {
  const r = await fetch('/api/stagemon/stop', {method: 'POST'});
  const d = await r.json();
  if (_sm) _sm.server = d.server;
  _smServer(d.server);
}

async function _smStatus() {
  try {
    const d = await (await fetch('/api/stagemon/status')).json();
    if (_sm) _sm.server = d.server;
    _smServer(d.server);
  } catch (e) { /* later */ }
}

let _smPoll = null;
let _smQrFor = '';
function stagemonQr(url) {
  const box = document.getElementById('sm-qrbox');
  if (!box) return;
  _smQrFor = url;
  box.textContent = '';
  const cap = document.createElement('div');
  cap.className = 'sm-meta';
  cap.textContent = 'Scan with the tablet camera:';
  const img = document.createElement('img');
  img.className = 'sm-qr';
  img.width = img.height = 200;
  img.alt = 'QR code ' + url;
  img.src = '/api/stagemon/qr?text=' + encodeURIComponent(url);
  const code = document.createElement('code');
  code.className = 'sm-qr-url';
  code.textContent = url;
  box.append(cap, img, code);
}
function _smServer(sv) {
  clearTimeout(_smPoll);
  if (sv && sv.running && !sv.https_from && document.getElementById('scr-stagemon')?.classList.contains('active'))
    _smPoll = setTimeout(_smStatus, 4000);
  const el = document.getElementById('sm-server');
  if (!el || !sv) return;
  document.getElementById('sm-serve').hidden = sv.running;
  document.getElementById('sm-stop').hidden = !sv.running;
  if (sv.running) {
    const urls = sv.urls.length ? sv.urls : [`http://localhost:${sv.port}/`];
    const copy = u => `<button class="btn btn-surface btn-sm" onclick="navigator.clipboard && navigator.clipboard.writeText('${_esc(u)}')">${_esc('Copy')}</button>`;
    el.innerHTML = `<div>${_esc('Serving — open on the tablet:')}</div>` + urls.map(u =>
      `<div class="sm-url"><code>${_esc(u)}</code>${copy(u)}</div>`).join('');
    const qrBtn = u => `<button class="btn btn-surface btn-sm" onclick="stagemonQr('${_esc(u)}')">${_esc('QR code')}</button>`;
    el.innerHTML += `<div class="sm-roles"><div class="sm-meta" style="margin:6px 0 0">${_esc('A view for each player:')}</div>` +
      ['commander', 'band', 'vocals'].map(r => `<div class="sm-url sm-role"><span>${_esc(r)}</span><code>${_esc(urls[0] + '?role=' + r)}</code>${copy(urls[0] + '?role=' + r)}${qrBtn(urls[0] + '?role=' + r)}</div>`).join('') + '</div>';
    el.innerHTML += `<div class="sm-qrbox" id="sm-qrbox"></div>`;
    stagemonQr(_smQrFor && _smQrFor.startsWith(urls[0]) ? _smQrFor : urls[0]);
    if (sv.https_from) el.innerHTML += `<div class="sm-warn">${_esc(`${sv.https_from} asked for https://. On that device type the address with http://, as shown above.`)}</div>`;
    el.innerHTML += `<div class="sm-meta" style="margin:6px 0 0">${_esc('At the gig only QLC+ (with -w) and this server are needed. Without Swiss Knife: double-click Start Stage Monitor in the folder.')}</div>`;
  } else {
    const ips = sv.addresses || [];
    const where = ips.length ? _esc(`This computer: ${ips.join(', ')}`)
      : _esc('No network address found. Join or create a Wi-Fi network first.');
    el.innerHTML = `<div class="sm-meta" style="margin:0">${where}</div>`
      + (sv.error ? `<div class="sm-warn">${_esc(sv.error)}</div>` : '');
  }
}
