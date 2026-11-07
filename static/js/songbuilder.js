/* Song Builder (3.9.8; clearer layout 3.14.0): a table of parts becomes one Show.
 * Three blocks in order: the song (tempo, how lengths are counted), the music, the parts.
 * A part shows its name, look, length, tempo and start; repeat, fades, a tempo change and
 * the chaser's steps are in its ⋯ panel, and show as small tags when set.  Every edit
 * refreshes the bar and the starts a moment later; Build writes the Show. */

let _sbd = { parts: [], funcs: [], showId: '' };
const _SBD_LOOK_TYPES = ['Scene', 'Chaser', 'Collection', 'RGBMatrix', 'EFX', 'Script'];
const _SBD_END = /^(?:until the end|to the end|to end|until end|till the end|end)$/i;

function _sbdEsc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function _sbdFmt(ms) { const s = ms / 1000, m = Math.floor(s / 60); return m + ':' + (s - m * 60).toFixed(1).padStart(4, '0'); }
function _sbdEl(id) { return document.getElementById(id); }

async function sbdInit() {
  try {
    const f = await (await fetch('/api/functions')).json();
    _sbd.funcs = Array.isArray(f) ? f : [];
  } catch (e) { _sbd.funcs = []; }
  const audios = _sbd.funcs.filter(f => f.type === 'Audio');
  _sbdEl('sbd-audio').innerHTML =
    `<option value="">${_sbdEsc(t('No music'))}</option>`
    + `<option value="__path">${_sbdEsc(t('A sound file…'))}</option>`
    + `<option value="__click">${_sbdEsc(t('A click track, made for this song'))}</option>`
    + (audios.length ? `<optgroup label="${_sbdEsc(t('Sounds already in the show'))}">`
      + audios.map(f => `<option value="${_sbdEsc(f.id)}">${_sbdEsc(f.name)}</option>`).join('') + '</optgroup>' : '');
  await _sbdLoadList();
  if (!_sbd.parts.length) { sbdNew(); }
  else { _sbdRender(); sbdPreview(); }
}

async function _sbdLoadList() {
  let list = [];
  try { list = await (await fetch('/api/songbuilder/list')).json(); } catch (e) { /* none */ }
  if (!Array.isArray(list)) list = [];
  _sbdEl('sbd-open').innerHTML =
    `<option value="">${_sbdEsc(t('A new song'))}</option>` +
    (list.length ? `<optgroup label="${_sbdEsc(t('Built here'))}">` + list.map(s => `<option value="${_sbdEsc(s.id)}"${s.id === _sbd.showId ? ' selected' : ''}>${_sbdEsc(s.name)}</option>`).join('') + '</optgroup>' : '');
}

function _sbdSetBpb(v) {
  const sel = _sbdEl('sbd-bpb'), val = String(v || 4);
  if (![...sel.options].some(o => o.value === val)) sel.insertAdjacentHTML('beforeend', `<option value="${_sbdEsc(val)}">${_sbdEsc(val)}/4</option>`);
  sel.value = val;
}

function sbdNew() {
  _sbd.showId = '';
  _sbd.musicMs = 0;
  _sbd.plan = null;
  _sbdEl('sbd-name').value = '';
  _sbdEl('sbd-bpm').value = '';
  _sbdSetBpb(4);
  _sbdEl('sbd-unit').value = 'seconds';
  _sbdEl('sbd-audio').value = '';
  _sbdEl('sbd-path').value = '';
  _sbdEl('sbd-mlen').value = '';
  _sbd.mlenNeeded = false;
  _sbdMusicShow();
  _sbdEl('sbd-music-note').textContent = '';
  _sbd.parts = [_sbdBlank('Intro'), _sbdBlank('Verse'), _sbdBlank('Chorus')];
  _sbdEl('sbd-out').innerHTML = '';
  _sbdRender();
  sbdMusicChanged();
}

function _sbdBlank(name) { return { name: name || '', look: '', function_id: '', length: '', repeat: 1, fade_in: '', fade_out: '', beats: '', bpm: '' }; }

async function sbdOpen(id) {
  if (!id) { sbdNew(); return; }
  const d = await (await fetch('/api/songbuilder/open?id=' + encodeURIComponent(id))).json();
  if (d.error) { _sbdOut(_sbdEsc(d.error), 'err'); return; }
  _sbd.showId = id;
  _sbdEl('sbd-name').value = d.name || '';
  _sbdEl('sbd-bpm').value = d.bpm || '';
  _sbdSetBpb(d.beats_per_bar || 4);
  _sbdEl('sbd-unit').value = ['seconds', 'bars', 'beats'].includes(d.unit) ? d.unit : 'seconds';
  const m = d.music || {};
  _sbdEl('sbd-audio').value = m.function_id || (m.path ? '__path' : '');
  _sbdEl('sbd-path').value = m.path || '';
  _sbdEl('sbd-mlen').value = m.length || '';
  _sbd.mlenNeeded = !!m.length;
  _sbd.parts = (d.parts || []).map(p => ({ ...p, look: (_sbd.funcs.find(f => f.id === p.function_id) || {}).name || '' }));
  _sbdRender();
  sbdMusicChanged();
}

// ── tempo, units, positions ──────────────────────────────────────────────────
function _sbdSongBpm() { return parseFloat(String(_sbdEl('sbd-bpm').value).replace(',', '.')) || 0; }
function _sbdUnit() { return _sbdEl('sbd-unit').value || 'seconds'; }
function _sbdLenHint() { return t('e.g. {0}', { seconds: '8s', bars: '8', beats: '16' }[_sbdUnit()]); }
function sbdUnitChanged() { _sbdRender(); sbdChanged(); }
// Typing a tempo into a song still counted in seconds, with no length typed yet, switches it
// to bars: that is what a tempo is for.
function sbdTempoChanged() {
  if (_sbdSongBpm() && _sbdUnit() === 'seconds' && !_sbd.parts.some(p => String(p.length || '').trim())) _sbdEl('sbd-unit').value = 'bars';
  _sbdRender();
  sbdChanged();
}
// The tempo each part plays at: its own when set, else the one running from the parts before it.
function _sbdTempos() {
  let run = _sbdSongBpm();
  return _sbd.parts.map(p => {
    const own = parseFloat(String(p.bpm || '').replace(',', '.'));
    if (own > 0) { run = own; return { bpm: own, own: true }; }
    return { bpm: run, own: false };
  });
}
// Beats gone by at *ms*, each part counted at its own tempo (3.13.0).
function _sbdBeats(ms) {
  let bpm = _sbdSongBpm(), beats = 0, at = 0;
  for (const r of (_sbd.plan && _sbd.plan.parts) || []) {
    if (!(r.end_ms > r.start_ms)) continue;
    const b = parseFloat(r.bpm) || bpm;
    if (ms <= r.end_ms) return beats + (ms - r.start_ms) * b / 60000;
    beats += (r.end_ms - r.start_ms) * b / 60000; at = r.end_ms; bpm = b;
  }
  return beats + (ms - at) * bpm / 60000;
}
// Where a moment falls in the song: "bar 3", "beat 9" (counted from 1) or the time.
function _sbdPos(ms) {
  const bpb = parseFloat(_sbdEl('sbd-bpb').value) || 4, u = _sbdUnit();
  if (u === 'seconds' || !(_sbdSongBpm() > 0)) return _sbdFmt(ms);
  const beat = _sbdBeats(ms);
  return u === 'bars' ? t('bar {0}', +(beat / bpb + 1).toFixed(2)) : t('beat {0}', +(beat + 1).toFixed(2));
}
function _sbdSpan(ms, from = 0) {
  const bpb = parseFloat(_sbdEl('sbd-bpb').value) || 4, u = _sbdUnit();
  if (u === 'seconds' || !(_sbdSongBpm() > 0)) return _sbdFmt(ms);
  const beats = _sbdBeats(from + ms) - _sbdBeats(from);
  return u === 'bars' ? t('{0} bars', +(beats / bpb).toFixed(2)) : t('{0} beats', +beats.toFixed(2));
}

// ── the parts table ──────────────────────────────────────────────────────────
function _sbdType(p) { return (_sbd.funcs.find(f => f.id === p.function_id) || {}).type || ''; }
function _sbdIsEnd(p) { return _SBD_END.test(String(p.length || '').trim()); }
function _sbdStepsLabel(beats) {
  const b = parseFloat(String(beats || '').replace(',', '.')), bpb = parseFloat(_sbdEl('sbd-bpb').value) || 4;
  if (!(b > 0)) return '';
  if (b === 1) return t('a step every beat');
  if (b === bpb) return t('a step every bar');
  return t('a step every {0} beats', +b);
}
// Small tags for what the ⋯ panel holds, so a closed row still says it.
function _sbdChips(p) {
  const out = [], rep = parseInt(p.repeat, 10) || 1;
  if (rep > 1) out.push(t('× {0}', rep));
  if (String(p.fade_in || '').trim()) out.push(t('fade in {0} s', p.fade_in));
  if (String(p.fade_out || '').trim()) out.push(t('fade out {0} s', p.fade_out));
  if (_sbdType(p) === 'Chaser' && _sbdStepsLabel(p.beats)) out.push(_sbdStepsLabel(p.beats));
  return out.map(c => `<span class="sbd-chip">${_sbdEsc(c)}</span>`).join('');
}

function _sbdRender() {
  const body = _sbdEl('sbd-rows');
  if (!body) return;
  const act = document.activeElement, keep = act && act.id && act.id.startsWith('sbd-f-') ? [act.id, act.selectionStart] : null;
  const tempos = _sbdTempos(), last = _sbd.parts.length - 1, hasTempo = tempos.some(x => x.bpm > 0);
  _sbdEl('sbd-th-tempo').classList.toggle('sbd-hidden', !hasTempo);
  body.innerHTML = _sbd.parts.map((p, i) => {
    const swatch = `<span class="sbd-swatch" style="background:${_sbdColor(p.name)}"></span>`;
    const end = _sbdIsEnd(p), canEnd = i === last;
    const len = end
      ? `<div class="sbd-len"><span class="sbd-endpill">${_sbdEsc(t('to the end'))}</span><button class="btn btn-surface sbd-ibtn sbd-on" onclick="sbdToggleEnd(${i})" aria-pressed="true" data-tooltip="${_sbdEsc(t('Give this part a length instead'))}">⇥</button></div>`
      : `<div class="sbd-len"><input class="field-input" type="text" value="${_sbdEsc(p.length)}" id="sbd-f-length-${i}" oninput="sbdCell(${i},'length',this.value)" placeholder="${_sbdEsc(_sbdLenHint())}" aria-label="${_sbdEsc(t('Length'))}">`
        + (canEnd ? `<button class="btn btn-surface sbd-ibtn" onclick="sbdToggleEnd(${i})" aria-pressed="false" data-tooltip="${_sbdEsc(t('Play this last part to the end of the music'))}">⇥</button>` : '') + '</div>';
    const tp = tempos[i];
    const tempo = !hasTempo ? '' : `<td class="sbd-tempo">${tp.bpm > 0
      ? `<button class="sbd-tempo-btn${tp.own ? ' sbd-tempo-own' : ''}" onclick="sbdMore(${i}, 'bpm')" data-tooltip="${_sbdEsc(tp.own ? t('This part changes the tempo to {0}', tp.bpm) : t('Carries on at {0}: change it in ⋯', tp.bpm))}">${tp.own ? '♩' : ''}${_sbdEsc(+tp.bpm.toFixed(2))}</button>` : '–'}</td>`;
    const row = `<tr data-i="${i}" class="sbd-row${p._open ? ' sbd-row-open' : ''}">
      <td class="sbd-num">${swatch}${i + 1}</td>
      <td><input class="field-input" type="text" value="${_sbdEsc(p.name)}" id="sbd-f-name-${i}" oninput="sbdCell(${i},'name',this.value)" placeholder="${_sbdEsc(t('Part'))}" aria-label="${_sbdEsc(t('Part'))}"></td>
      <td><input class="field-input sbd-look" type="text" readonly value="${_sbdEsc(p.function_id ? p.look : '')}" onclick="sbdPick(${i})" placeholder="${_sbdEsc(t('Pick a scene or chaser…'))}" aria-label="${_sbdEsc(t('Look'))}">
        <div class="sbd-chips" id="sbd-chips-${i}">${_sbdChips(p)}</div></td>
      <td style="width:150px">${len}</td>
      ${tempo}
      <td class="sbd-start" id="sbd-start-${i}">${p.start_ms === undefined ? '' : _sbdEsc(_sbdPos(p.start_ms))}</td>
      <td class="sbd-acts"><button class="btn btn-surface sbd-ibtn${p._open ? ' sbd-on' : ''}" onclick="sbdMore(${i})" aria-expanded="${p._open ? 'true' : 'false'}" data-tooltip="${_sbdEsc(t('Repeat, fades, tempo change, steps'))}">⋯</button>
        <button class="btn btn-surface sbd-ibtn" onclick="sbdMove(${i},-1)" aria-label="${_sbdEsc(t('Up'))}">↑</button>
        <button class="btn btn-surface sbd-ibtn" onclick="sbdMove(${i},1)" aria-label="${_sbdEsc(t('Down'))}">↓</button>
        <button class="btn btn-surface sbd-ibtn" onclick="sbdCopy(${i})" aria-label="${_sbdEsc(t('Copy this row'))}" data-tooltip="${_sbdEsc(t('Copy this row'))}">⧉</button>
        <button class="btn btn-surface sbd-ibtn" onclick="sbdRemove(${i})" aria-label="${_sbdEsc(t('Remove'))}">×</button></td>
    </tr>`;
    return row + (p._open ? _sbdMoreRow(p, i, tempos, hasTempo) : '');
  }).join('');
  _sbdEl('sbd-shape').classList.toggle('sbd-hidden', _sbd.parts.some(p => p.function_id || String(p.length || '').trim()));
  if (keep) { const el = _sbdEl(keep[0]); if (el) { el.focus(); try { el.setSelectionRange(keep[1], keep[1]); } catch (e) { /* select */ } } }
}

// The ⋯ panel of a part: what most songs never need.
function _sbdMoreRow(p, i, tempos, hasTempo) {
  const before = i > 0 ? tempos[i - 1].bpm : _sbdSongBpm();
  const bpb = parseFloat(_sbdEl('sbd-bpb').value) || 4, b = String(p.beats || '').trim();
  const opts = [['', t('its own timing')], ['1', t('every beat')], ['2', t('every 2 beats')], [String(bpb), t('every bar')]];
  if (b && !opts.some(o => o[0] === b)) opts.push([b, t('every {0} beats', b)]);
  const steps = _sbdType(p) === 'Chaser'
    ? `<label class="sbd-more-f"><span>${_sbdEsc(t('Chaser steps'))}</span><select class="field-input" onchange="sbdCell(${i},'beats',this.value,true)"${hasTempo ? '' : ' disabled'}>`
      + opts.map(([v, l]) => `<option value="${_sbdEsc(v)}"${v === b ? ' selected' : ''}>${_sbdEsc(l)}</option>`).join('') + '</select>'
      + `<small>${_sbdEsc(hasTempo ? t('A step lasts that long at the tempo of the part.') : t('Needs the tempo of the song.'))}</small></label>`
    : `<div class="sbd-more-f"><span>${_sbdEsc(t('Chaser steps'))}</span><small>${_sbdEsc(p.function_id ? t('Only for a chaser: this look is a {0}.', _sbdType(p) || t('look')) : t('Pick a chaser as the look to time its steps.'))}</small></div>`;
  return `<tr class="sbd-more"><td></td><td colspan="${hasTempo ? 6 : 5}"><div class="sbd-more-grid">
    <label class="sbd-more-f"><span>${_sbdEsc(t('Repeat'))}</span><input class="field-input" type="text" value="${_sbdEsc(p.repeat)}" id="sbd-f-repeat-${i}" oninput="sbdCell(${i},'repeat',this.value,true)"><small>${_sbdEsc(t('times in a row'))}</small></label>
    <label class="sbd-more-f"><span>${_sbdEsc(t('Fade in'))}</span><input class="field-input" type="text" value="${_sbdEsc(p.fade_in)}" id="sbd-f-fade_in-${i}" oninput="sbdCell(${i},'fade_in',this.value,true)" placeholder="${_sbdEsc(t('look’s own'))}"><small>${_sbdEsc(t('seconds; 0 for none'))}</small></label>
    <label class="sbd-more-f"><span>${_sbdEsc(t('Fade out'))}</span><input class="field-input" type="text" value="${_sbdEsc(p.fade_out)}" id="sbd-f-fade_out-${i}" oninput="sbdCell(${i},'fade_out',this.value,true)" placeholder="${_sbdEsc(t('look’s own'))}"><small>${_sbdEsc(t('seconds; 0 for none'))}</small></label>
    <label class="sbd-more-f"><span>${_sbdEsc(t('Tempo from here'))}</span><input id="sbd-f-bpm-${i}" class="field-input" type="text" value="${_sbdEsc(p.bpm)}" oninput="sbdCell(${i},'bpm',this.value,true)" placeholder="${_sbdEsc(before > 0 ? String(+before.toFixed(2)) : 'BPM')}"><small>${_sbdEsc(before > 0 ? t('Empty: carries on at {0}. A new tempo lasts until a later part sets another.', +before.toFixed(2)) : t('BPM. It lasts until a later part sets another.'))}</small></label>
    ${steps}
  </div></td></tr>`;
}

function sbdMore(i, focus) {
  const p = _sbd.parts[i];
  if (!p) return;
  p._open = focus ? true : !p._open;
  _sbdRender();
  if (focus === 'bpm') _sbdEl('sbd-f-bpm-' + i)?.focus();
}

function sbdToggleEnd(i) {
  const p = _sbd.parts[i];
  if (!p) return;
  if (_sbdIsEnd(p)) { p.length = ''; }
  else {
    if (!_sbd.musicMs) { _sbdOut(_sbdEsc(t('“To the end” needs the music: choose it in step 2 first.')), 'hint'); return; }
    p.length = 'to the end'; p.repeat = 1;
  }
  _sbdRender();
  sbdChanged();
}

// A typical song shape, so an empty table shows how it is meant to be filled in.
function sbdShape() {
  const bars = _sbdSongBpm() > 0 && _sbdUnit() !== 'seconds', beats = _sbdUnit() === 'beats';
  const bpb = parseFloat(_sbdEl('sbd-bpb').value) || 4;
  const len = n => bars ? String(beats ? n * bpb : n) : (n * 2) + 's';
  const shape = [['Intro', 4], ['Verse', 8], ['Chorus', 8], ['Verse', 8], ['Chorus', 8], ['Outro', 4]];
  _sbd.parts = shape.map(([n, l]) => ({ ..._sbdBlank(n), length: len(l) }));
  if (_sbd.musicMs) _sbd.parts[_sbd.parts.length - 1].length = 'to the end';
  _sbdRender();
  sbdChanged();
  _sbdOut(_sbdEsc(t('A typical song is filled in. Pick a look for each part, then change the lengths to fit.')), 'hint');
}

// Colours by part name in order of first appearance: the same as the tracks of the Show (core/song_builder.py).
const _SBD_COLORS = ['#d9534f', '#f0ad4e', '#5cb85c', '#5bc0de', '#9b59b6', '#e67e22', '#1abc9c', '#e91e63'];
const _SBD_MUSIC = '#4a90d9';
function _sbdColor(name) {
  const names = [...new Set(_sbd.parts.map((p, i) => (p.name || '').trim() || `Part ${i + 1}`))];
  const k = names.indexOf((name || '').trim() || `Part ${_sbd.parts.findIndex(p => p.name === name) + 1}`);
  return _SBD_COLORS[(k < 0 ? 0 : k) % _SBD_COLORS.length];
}

// ── the look picker: the same list as the Setlist's function list ─────────────
let _sbdPickRow = -1;

function sbdPick(i) {
  _sbdPickRow = i;
  const types = [...new Set(_sbd.funcs.filter(f => _SBD_LOOK_TYPES.includes(f.type)).map(f => f.type))];
  document.getElementById('sbd-pick-type').innerHTML =
    `<option value="">${_sbdEsc(t('All types'))}</option>` + types.map(x => `<option value="${_sbdEsc(x)}">${_sbdEsc(x)}</option>`).join('');
  document.getElementById('sbd-pick-q').value = '';
  document.getElementById('sbd-pick-modal').classList.remove('sbd-hidden');
  sbdPickRender();
  document.getElementById('sbd-pick-q').focus();
}

function sbdPickClose() { document.getElementById('sbd-pick-modal').classList.add('sbd-hidden'); }

function sbdPickRender() {
  const q = document.getElementById('sbd-pick-q').value.trim().toLowerCase();
  const ty = document.getElementById('sbd-pick-type').value;
  const list = _sbd.funcs.filter(f => _SBD_LOOK_TYPES.includes(f.type) && (!ty || f.type === ty)
    && (!q || (f.name + ' ' + (f.vc_button || '') + ' ' + (f.desc || '')).toLowerCase().includes(q)));
  const groups = {};
  list.forEach(f => (groups[f.type] = groups[f.type] || []).push(f));
  let html = list.length ? '' : `<div class="slot-empty">${_sbdEsc(t('No results'))}</div>`;
  Object.keys(groups).sort((a, b) => _SBD_LOOK_TYPES.indexOf(a) - _SBD_LOOK_TYPES.indexOf(b)).forEach(type => {
    html += `<div class="pool-type-header"><span>${_sbdEsc(type)}</span><span class="pool-grp-count">${groups[type].length}</span></div>`;
    groups[type].forEach(f => {
      const vc = f.vc_button || f.vc_inherited || '';
      html += `<div class="fn-pool-item" data-id="${_sbdEsc(f.id)}">
        <div class="pool-item-row"><span class="pool-col-name fn-pool-name">${_sbdEsc(f.name)}</span><span class="fn-pool-id">${_sbdEsc(f.id)}</span></div>
        ${vc ? `<div class="pool-item-vc">${_sbdEsc(vc)}</div>` : ''}${f.desc ? `<div class="pool-item-desc">${_sbdEsc(f.desc)}</div>` : ''}</div>`;
    });
  });
  document.getElementById('sbd-pick-list').innerHTML = html;
}

document.addEventListener('click', e => {
  const it = e.target.closest && e.target.closest('#sbd-pick-list .fn-pool-item');
  if (it) sbdPickChoose(it.dataset.id);
});

function sbdPickChoose(id) {
  const f = _sbd.funcs.find(x => x.id === id), row = _sbd.parts[_sbdPickRow];
  if (f && row) { row.function_id = f.id; row.look = f.name; if (!(row.name || '').trim()) row.name = f.name; }
  sbdPickClose();
  _sbdRender();
  sbdChanged();
}

let _sbdTimer = null;
// Every edit refreshes the bar and the starts a moment after the last key.
function sbdChanged() { clearTimeout(_sbdTimer); _sbdTimer = setTimeout(sbdPreview, 350); }
// *redraw*: the edit changes what other rows show (tags, tempo), so the table is drawn again;
// the field being typed in keeps its place.
function sbdCell(i, key, val, redraw) {
  if (!_sbd.parts[i]) return;
  _sbd.parts[i][key] = val;
  if (key === 'name') _sbdRecolor();
  if (redraw) _sbdRender();
  sbdChanged();
}
function _sbdRecolor() { document.querySelectorAll('#sbd-rows tr.sbd-row').forEach(tr => { const i = +tr.dataset.i, sw = tr.querySelector('.sbd-swatch'); if (sw && _sbd.parts[i]) sw.style.background = _sbdColor(_sbd.parts[i].name); }); }
function sbdAddRow() { _sbd.parts.push(_sbdBlank('')); _sbdRender(); sbdChanged(); }
function sbdCopy(i) {
  const p = _sbd.parts[i];
  if (!p) return;
  _sbd.parts.splice(i + 1, 0, { ...p, start_ms: undefined, _open: false });
  _sbdRender();
  sbdChanged();
}
function sbdRemove(i) { _sbd.parts.splice(i, 1); _sbdRender(); sbdChanged(); }
function sbdMove(i, d) {
  const j = i + d;
  if (j < 0 || j >= _sbd.parts.length) return;
  [_sbd.parts[i], _sbd.parts[j]] = [_sbd.parts[j], _sbd.parts[i]];
  _sbdRender();
  sbdChanged();
}

// ── music ────────────────────────────────────────────────────────────────────
function _sbdMusicShow() {
  const v = _sbdEl('sbd-audio').value;
  _sbdEl('sbd-path').classList.toggle('sbd-hidden', v !== '__path');
  _sbdEl('sbd-browse').classList.toggle('sbd-hidden', v !== '__path');
  _sbdEl('sbd-mlen-wrap').classList.toggle('sbd-hidden', !(v === '__path' && (_sbd.mlenNeeded || _sbdEl('sbd-mlen').value.trim())));
  _sbdEl('sbd-click-wrap').classList.toggle('sbd-hidden', v !== '__click');
}

// Pick the music with the computer's own file dialog (3.13.0).  A file in the show's folder
// is written relative to it, like QLC+ does, so the two can move together.
async function sbdBrowseMusic() {
  const path = await nativePick('Select the music file',
    [{ label: 'Sound', exts: ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac'] }]);
  if (!path) {
    if (nativePick.unavailable) _sbdEl('sbd-music-note').textContent = t('No file dialog here: type the path of the file.');
    return;
  }
  _sbdEl('sbd-path').value = path;
  await sbdMusicChanged();
}

async function sbdMusicChanged() {
  const note = _sbdEl('sbd-music-note');
  const v = _sbdEl('sbd-audio').value;
  const path = _sbdEl('sbd-path').value.trim();
  _sbdMusicShow();
  sbdChanged();
  if (v === '') { note.textContent = t('No music: the Show lasts as long as its parts.'); return; }
  if (v === '__click') {
    note.textContent = _sbdSongBpm() > 0
      ? t('A sound file with a click on every beat, at the tempo of each part, as long as the song. It is saved next to the show and becomes the music. Make it again after you change the parts.')
      : t('A click track needs the tempo of the song: type it in step 1.');
    return;
  }
  if (v !== '__path') {
    const f = _sbd.funcs.find(x => x.id === v);
    note.textContent = f ? t('Uses the sound “{0}” already in the show.', f.name) : '';
    return;
  }
  if (!path) { note.textContent = t('Press Browse… to pick the file.'); return; }
  const d = await (await fetch('/api/songbuilder/music', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) })).json();
  if (d.error) { note.textContent = d.error; return; }
  if (d.path && d.path !== path) { _sbdEl('sbd-path').value = d.path; sbdChanged(); }
  _sbd.mlenNeeded = !d.found || !d.length_ms;
  _sbdMusicShow();
  if (!d.found) { note.textContent = t('Not found on this computer: pick it with Browse…, or type its length in the box to carry on.'); return; }
  note.textContent = d.length_ms ? t('Found, {0} long.', _sbdFmt(d.length_ms)) : t('Its length can’t be read from this file: type it in the box (m:ss).');
}

function _sbdSpec() {
  const v = _sbdEl('sbd-audio').value;
  const path = _sbdEl('sbd-path').value.trim();
  const music = (v && !v.startsWith('__')) ? { function_id: v }
    : (v === '__path' && path ? { path, length: _sbdEl('sbd-mlen').value.trim() } : {});
  return {
    name: _sbdEl('sbd-name').value.trim(),
    bpm: _sbdEl('sbd-bpm').value.trim(),
    beats_per_bar: _sbdEl('sbd-bpb').value.trim(),
    unit: _sbdUnit(),
    show_id: _sbd.showId,
    music,
    // steps only mean something on a chaser: on any other look they are not sent (3.14.0)
    parts: _sbd.parts.map(p => ({ name: p.name, function_id: p.function_id, length: p.length, repeat: p.repeat,
                                  fade_in: p.fade_in, fade_out: p.fade_out,
                                  beats: _sbdType(p) === 'Chaser' ? p.beats : '', bpm: p.bpm })),
  };
}

function _sbdOut(html, cls) { _sbdEl('sbd-out').innerHTML = `<div class="${cls === 'err' ? 'sbd-err' : cls === 'hint' ? 'sbd-hint' : ''}">${html}</div>`; }

function _sbdBars(res) {
  const total = res.length_ms || 0, music = res.music_ms || 0, scale = Math.max(total, music, 1);
  const pct = ms => (100 * ms / scale).toFixed(3) + '%';
  const seg = (r, i, arr) => {
    const bad = r.issue ? ' sbd-seg-bad' : '';
    const prevBpm = i > 0 ? arr[i - 1].bpm : null;
    const bpmChanged = i > 0 && r.bpm && r.bpm !== prevBpm;
    const chip = bpmChanged ? ` <span class="sbd-bpm-chip">♩${_sbdEsc(r.bpm)}</span>` : '';
    const tip = `${r.name || ''} · ${_sbdPos(r.start_ms)}–${_sbdPos(r.end_ms)}` + (r.bpm ? ` · ${r.bpm} BPM` : '') + (r.issue ? ` · ${r.issue}` : '');
    const color = r.issue ? '' : `background:${_sbdColor(r.name)}`;
    return `<div class="sbd-seg${bad}" style="left:${pct(r.start_ms)};width:${pct(r.end_ms - r.start_ms)};${color}" data-tooltip="${_sbdEsc(tip)}"><span>${_sbdEsc(r.name)}${chip}</span></div>`;
  };
  const lights = (res.parts || []).map((r, i, arr) => seg(r, i, arr)).join('');
  const free = (res.free_ms || 0) > 0
    ? `<div class="sbd-gap" style="left:${pct(total)};width:${pct(res.free_ms)}" data-tooltip="${_sbdEsc(t('Free: {0} not covered by any part', _sbdSpan(res.free_ms, total)))}"><span>${_sbdEsc(t('Free {0}', _sbdSpan(res.free_ms, total)))}</span></div>` : '';
  const empty = scale <= 1 ? `<div class="sbd-gap sbd-gap-all" style="left:0;width:100%"><span>${_sbdEsc(t('Give the parts a length to see the song here'))}</span></div>` : '';
  const musicBar = music ? `<div class="sbd-seg" style="left:0;width:${pct(music)};background:${_SBD_MUSIC}"><span>${_sbdEsc(t('Music'))} ${_sbdFmt(music)}</span></div>` : '';
  const over = (music && total > music) ? `<div class="sbd-gap" style="left:${pct(music)};width:${pct(total - music)}" data-tooltip="${_sbdEsc(t('Past the end of the music'))}"></div>` : '';
  return `<div class="sbd-bar-row"><span class="sbd-bar-lbl">${_sbdEsc(t('Parts'))}</span><div class="sbd-bar">${lights}${free}${empty}</div></div>`
       + (music ? `<div class="sbd-bar-row"><span class="sbd-bar-lbl">${_sbdEsc(t('Music'))}</span><div class="sbd-bar">${musicBar}${over}</div></div>` : '')
       + `<div class="sbd-bar-row"><span class="sbd-bar-lbl"></span><div class="sbd-ruler"><span>${_sbdEsc(_sbdPos(0))}</span><span>${_sbdEsc(_sbdPos(scale))}</span></div></div>`;
}

// The line beside Build: what is left to do, or that the song is ready.
function _sbdFoot(res) {
  const el = _sbdEl('sbd-foot-note');
  if (!el) return;
  const noLook = _sbd.parts.filter(p => !p.function_id).length;
  const bad = (res.parts || []).filter(r => r.issue).length;
  if (!_sbdEl('sbd-name').value.trim()) el.textContent = t('Give the song a name in step 1.');
  else if (noLook) el.textContent = t('Pick a look for {0} part(s).', noLook);
  else if (bad) el.textContent = t('Fix the parts listed above the button.');
  else el.textContent = t('Ready: {0} parts, {1}.', _sbd.parts.length, _sbdFmt(res.length_ms || 0));
}

function _sbdShowPlan(res) {
  _sbd.plan = res;                                        // the tempo map for bar and beat numbers
  (res.parts || []).forEach((r, i) => { const el = _sbdEl('sbd-start-' + i); if (_sbd.parts[i]) _sbd.parts[i].start_ms = r.start_ms; if (el) el.textContent = _sbdPos(r.start_ms); });
  _sbdEl('sbd-bars').innerHTML = _sbdBars(res);
  _sbdFoot(res);
  const total = t('Total {0}', _sbdSpan(res.length_ms || 0)) + (res.music_ms ? ' · ' + t('music {0}', _sbdFmt(res.music_ms)) : '') + ((res.free_ms || 0) > 0 ? ' · ' + t('Free {0}', _sbdSpan(res.free_ms, res.length_ms || 0)) : '');
  const issues = (res.parts || []).map((r, i) => r.issue && _sbd.parts[i] && (_sbd.parts[i].function_id || String(_sbd.parts[i].length || '').trim())
    ? `<div class="sbd-hint">${_sbdEsc(t('Row {0}: {1}', i + 1, r.issue))}</div>` : '').join('');
  const song = _sbdEl('sbd-song-note');
  if (song) song.textContent = (_sbdUnit() !== 'seconds' && !(_sbdSongBpm() > 0)) ? t('Bars and beats need the tempo: type the BPM, or count in seconds.') : '';
  const warns = (res.warnings || []).map(w => `<div class="sbd-warn">⚠ ${_sbdEsc(w)}</div>`).join('');
  return `<div>${_sbdEsc(total)}</div>${issues}${warns}`;
}

async function sbdPreview() {
  const res = await _sbdPost('/api/songbuilder/preview');
  if (!res.error) _sbd.musicMs = res.music_ms || 0;
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'hint'); return; }
  _sbdEl('sbd-out').innerHTML = _sbdShowPlan(res);
}

async function _sbdPost(url, extra) {
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ..._sbdSpec(), ...(extra || {}) }) });
    return await r.json();
  } catch (e) { return { error: String(e) }; }
}

async function sbdBuild() {
  const res = await _sbdPost('/api/songbuilder/build');
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'err'); return; }
  _sbd.showId = res.show_id;
  await _sbdLoadList();
  _sbdEl('sbd-out').innerHTML =
    `<div>${_sbdEsc(t('✓ Show “{0}” built (ID {1}). Assign it to a song in the Setlist Manager.', res.name, res.show_id))}</div>` + _sbdShowPlan(res);
  if (typeof showRefresh === 'function') showRefresh();
  if (typeof setStatus === 'function') setStatus(t('✓ Show “{0}” built — Save as new file… when you’re ready.', res.name), (res.warnings || []).length ? 'warn' : 'ok');
}

// A click track (3.10.0; follows each part's tempo since 3.13.0): saved next to the show and used as the music.
async function sbdClick() {
  const res = await _sbdPost('/api/songbuilder/click', { sound: _sbdEl('sbd-click-sound').value });
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'err'); return; }
  _sbdEl('sbd-audio').value = '__path';
  _sbdEl('sbd-path').value = res.path;
  _sbdEl('sbd-mlen').value = '';
  _sbd.mlenNeeded = false;
  await sbdMusicChanged();
  sbdPreview();
  setStatus(t('✓ Click track saved: {0}', res.name), 'ok');
}
