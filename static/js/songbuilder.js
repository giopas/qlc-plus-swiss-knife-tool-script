/* Song Builder (3.9.8): a table of parts becomes one Show.
 * The table is kept in `_sbd` (name, BPM, music, parts); every edit marks it dirty,
 * Preview shows the starts and warnings, Build writes the Show into the show in progress. */

let _sbd = { parts: [], funcs: [], showId: '' };
const _SBD_LOOK_TYPES = ['Scene', 'Chaser', 'Collection', 'RGBMatrix', 'EFX', 'Script'];

function _sbdEsc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function _sbdFmt(ms) { const s = ms / 1000, m = Math.floor(s / 60); return m + ':' + (s - m * 60).toFixed(1).padStart(4, '0'); }

async function sbdInit() {
  try {
    const f = await (await fetch('/api/functions')).json();
    _sbd.funcs = Array.isArray(f) ? f : [];
  } catch (e) { _sbd.funcs = []; }
  const audios = _sbd.funcs.filter(f => f.type === 'Audio');
  document.getElementById('sbd-audio').innerHTML =
    `<option value="">${_sbdEsc(t('— music file by path —'))}</option>` +
    audios.map(f => `<option value="${_sbdEsc(f.id)}">${_sbdEsc(f.name)}</option>`).join('');
  await _sbdLoadList();
  if (!_sbd.parts.length) { sbdNew(); }
  else { _sbdRender(); sbdPreview(); }
}

async function _sbdLoadList() {
  let list = [];
  try { list = await (await fetch('/api/songbuilder/list')).json(); } catch (e) { /* none */ }
  if (!Array.isArray(list)) list = [];
  document.getElementById('sbd-open').innerHTML =
    `<option value="">${_sbdEsc(t('— a new song —'))}</option>` +
    list.map(s => `<option value="${_sbdEsc(s.id)}"${s.id === _sbd.showId ? ' selected' : ''}>${_sbdEsc(s.name)}</option>`).join('');
}

function sbdNew() {
  _sbd.showId = '';
  document.getElementById('sbd-name').value = '';
  document.getElementById('sbd-bpm').value = '';
  document.getElementById('sbd-bpb').value = '4';
  document.getElementById('sbd-unit').value = 'seconds';
  document.getElementById('sbd-audio').value = '';
  document.getElementById('sbd-path').value = '';
  document.getElementById('sbd-mlen').value = '';
  document.getElementById('sbd-music-note').textContent = '';
  _sbd.parts = [_sbdBlank('Intro'), _sbdBlank('Verse'), _sbdBlank('Chorus')];
  document.getElementById('sbd-out').innerHTML = '';
  _sbdRender();
  sbdPreview();
}

function _sbdBlank(name) { return { name: name || '', look: '', function_id: '', length: '', repeat: 1, fade_in: '', fade_out: '', beats: '' }; }

async function sbdOpen(id) {
  if (!id) { sbdNew(); return; }
  const d = await (await fetch('/api/songbuilder/open?id=' + encodeURIComponent(id))).json();
  if (d.error) { _sbdOut(_sbdEsc(d.error), 'err'); return; }
  _sbd.showId = id;
  document.getElementById('sbd-name').value = d.name || '';
  document.getElementById('sbd-bpm').value = d.bpm || '';
  document.getElementById('sbd-bpb').value = d.beats_per_bar || 4;
  document.getElementById('sbd-unit').value = ['seconds', 'bars', 'beats'].includes(d.unit) ? d.unit : 'seconds';
  const m = d.music || {};
  document.getElementById('sbd-audio').value = m.function_id || '';
  document.getElementById('sbd-path').value = m.path || '';
  document.getElementById('sbd-mlen').value = m.length || '';
  _sbd.parts = (d.parts || []).map(p => ({ ...p, look: (_sbd.funcs.find(f => f.id === p.function_id) || {}).name || '' }));
  _sbdRender();
  sbdMusicChanged();
  sbdPreview();
}

function _sbdUnit() { return document.getElementById('sbd-unit').value || 'seconds'; }
function _sbdLenHint() { return { seconds: '8s  ·  0:08', bars: '8', beats: '16' }[_sbdUnit()]; }
function sbdUnitChanged() { _sbdRender(); sbdChanged(); }
// Where a moment falls in the song, in the unit of the song: "bar 3", "beat 9" (counted from 1) or the time.
function _sbdPos(ms) {
  const bpm = parseFloat(document.getElementById('sbd-bpm').value), bpb = parseFloat(document.getElementById('sbd-bpb').value) || 4, u = _sbdUnit();
  if (u === 'seconds' || !(bpm > 0)) return _sbdFmt(ms);
  const beat = ms / (60000 / bpm);
  return u === 'bars' ? t('bar {0}', +(beat / bpb + 1).toFixed(2)) : t('beat {0}', +(beat + 1).toFixed(2));
}
function _sbdSpan(ms) {                                   // a duration: "0:20" or "10 bars" / "40 beats"
  const bpm = parseFloat(document.getElementById('sbd-bpm').value), bpb = parseFloat(document.getElementById('sbd-bpb').value) || 4, u = _sbdUnit();
  if (u === 'seconds' || !(bpm > 0)) return _sbdFmt(ms);
  const beats = ms / (60000 / bpm);
  return u === 'bars' ? t('{0} bars', +(beats / bpb).toFixed(2)) : t('{0} beats', +beats.toFixed(2));
}

function _sbdRender() {
  const body = document.getElementById('sbd-rows');
  if (!body) return;
  body.innerHTML = _sbd.parts.map((p, i) => {
    const swatch = `<span class="sbd-swatch" style="background:${_sbdColor(p.name)}"></span>`;
    return `<tr data-i="${i}">
      <td>${swatch}${i + 1}</td>
      <td><input class="field-input" type="text" value="${_sbdEsc(p.name)}" oninput="sbdCell(${i},'name',this.value)" placeholder="${_sbdEsc(t('Part'))}"></td>
      <td><input class="field-input sbd-look" type="text" readonly value="${_sbdEsc(p.function_id ? p.look : '')}" onclick="sbdPick(${i})" placeholder="${_sbdEsc(t('Pick a scene or chaser…'))}"></td>
      <td style="width:90px"><input class="field-input" type="text" value="${_sbdEsc(p.length)}" oninput="sbdCell(${i},'length',this.value)" placeholder="${_sbdEsc(_sbdLenHint())}"></td>
      <td style="width:60px"><input class="field-input" type="text" value="${_sbdEsc(p.repeat)}" oninput="sbdCell(${i},'repeat',this.value)"></td>
      <td style="width:70px"><input class="field-input" type="text" value="${_sbdEsc(p.fade_in)}" oninput="sbdCell(${i},'fade_in',this.value)" placeholder="0"></td>
      <td style="width:70px"><input class="field-input" type="text" value="${_sbdEsc(p.fade_out)}" oninput="sbdCell(${i},'fade_out',this.value)" placeholder="0"></td>
      <td style="width:70px"><input class="field-input" type="text" value="${_sbdEsc(p.beats)}" oninput="sbdCell(${i},'beats',this.value)" placeholder="–"></td>
      <td class="sbd-start" id="sbd-start-${i}">${p.start_ms === undefined ? '' : _sbdEsc(_sbdPos(p.start_ms))}</td>
      <td style="white-space:nowrap"><button class="btn btn-surface" style="padding:0 6px" onclick="sbdMove(${i},-1)" aria-label="${_sbdEsc(t('Up'))}">↑</button>
        <button class="btn btn-surface" style="padding:0 6px" onclick="sbdMove(${i},1)" aria-label="${_sbdEsc(t('Down'))}">↓</button>
        <button class="btn btn-surface" style="padding:0 6px" onclick="sbdCopy(${i})" aria-label="${_sbdEsc(t('Copy this row'))}" data-tooltip="${_sbdEsc(t('Copy this row'))}">⧉</button>
        <button class="btn btn-surface" style="padding:0 6px" onclick="sbdRemove(${i})" aria-label="${_sbdEsc(t('Remove'))}">×</button></td>
    </tr>`;
  }).join('');
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
// Every edit refreshes the preview (and the bars) a moment after the last key.
function sbdChanged() { clearTimeout(_sbdTimer); _sbdTimer = setTimeout(sbdPreview, 350); }
function sbdCell(i, key, val) { if (_sbd.parts[i]) { _sbd.parts[i][key] = val; if (key === 'name') _sbdRecolor(); sbdChanged(); } }
function _sbdRecolor() { document.querySelectorAll('#sbd-rows tr').forEach((tr, i) => { const sw = tr.querySelector('.sbd-swatch'); if (sw && _sbd.parts[i]) sw.style.background = _sbdColor(_sbd.parts[i].name); }); }
function sbdAddRow() { _sbd.parts.push(_sbdBlank('')); _sbdRender(); sbdChanged(); }
function sbdCopy(i) {
  const p = _sbd.parts[i];
  if (!p) return;
  _sbd.parts.splice(i + 1, 0, { ...p, start_ms: undefined });
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

async function sbdMusicChanged() {
  sbdChanged();
  const note = document.getElementById('sbd-music-note');
  const fid = document.getElementById('sbd-audio').value;
  const path = document.getElementById('sbd-path').value.trim();
  if (fid) {
    const f = _sbd.funcs.find(x => x.id === fid);
    note.textContent = f ? t('Uses the sound function “{0}” already in the show.', f.name) : '';
    return;
  }
  if (!path) { note.textContent = ''; return; }
  const d = await (await fetch('/api/songbuilder/music', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) })).json();
  if (d.error) { note.textContent = d.error; return; }
  if (!d.found) { note.textContent = t('Not found on this computer: check the path.'); return; }
  note.textContent = d.length_ms ? t('Found, {0} long.', _sbdFmt(d.length_ms)) : t('Found, but its length cannot be read: type it in the box (for example 3:45).');
}

function _sbdSpec() {
  const fid = document.getElementById('sbd-audio').value;
  const path = document.getElementById('sbd-path').value.trim();
  return {
    name: document.getElementById('sbd-name').value.trim(),
    bpm: document.getElementById('sbd-bpm').value.trim(),
    beats_per_bar: document.getElementById('sbd-bpb').value.trim(),
    unit: _sbdUnit(),
    show_id: _sbd.showId,
    music: fid ? { function_id: fid } : (path ? { path, length: document.getElementById('sbd-mlen').value.trim() } : {}),
    parts: _sbd.parts.map(p => ({ name: p.name, function_id: p.function_id, length: p.length, repeat: p.repeat,
                                  fade_in: p.fade_in, fade_out: p.fade_out, beats: p.beats })),
  };
}

function _sbdOut(html, cls) { document.getElementById('sbd-out').innerHTML = `<div class="${cls === 'err' ? 'sbd-err' : cls === 'hint' ? 'sbd-hint' : ''}">${html}</div>`; }

function _sbdBars(res) {
  const total = res.length_ms || 0, music = res.music_ms || 0, scale = Math.max(total, music, 1);
  const pct = ms => (100 * ms / scale).toFixed(3) + '%';
  const seg = (r) => {
    const bad = r.issue ? ' sbd-seg-bad' : '';
    const tip = `${r.name || ''} · ${_sbdPos(r.start_ms)}–${_sbdPos(r.end_ms)}` + (r.issue ? ` · ${r.issue}` : '');
    const color = r.issue ? '' : `background:${_sbdColor(r.name)}`;
    return `<div class="sbd-seg${bad}" style="left:${pct(r.start_ms)};width:${pct(r.end_ms - r.start_ms)};${color}" data-tooltip="${_sbdEsc(tip)}"><span>${_sbdEsc(r.name)}</span></div>`;
  };
  const lights = (res.parts || []).map(seg).join('');
  const free = (res.free_ms || 0) > 0
    ? `<div class="sbd-gap" style="left:${pct(total)};width:${pct(res.free_ms)}" data-tooltip="${_sbdEsc(t('Free: {0} not covered by any part', _sbdSpan(res.free_ms)))}"><span>${_sbdEsc(t('Free {0}', _sbdSpan(res.free_ms)))}</span></div>` : '';
  const empty = scale <= 1 ? `<div class="sbd-gap sbd-gap-all" style="left:0;width:100%"><span>${_sbdEsc(t('Give the parts a length to see the song here'))}</span></div>` : '';
  const musicBar = music ? `<div class="sbd-seg" style="left:0;width:${pct(music)};background:${_SBD_MUSIC}"><span>${_sbdEsc(t('Music'))} ${_sbdFmt(music)}</span></div>` : '';
  const over = (music && total > music) ? `<div class="sbd-gap" style="left:${pct(music)};width:${pct(total - music)}" data-tooltip="${_sbdEsc(t('Past the end of the music'))}"></div>` : '';
  return `<div class="sbd-bar-row"><span class="sbd-bar-lbl">${_sbdEsc(t('Parts'))}</span><div class="sbd-bar">${lights}${free}${empty}</div></div>`
       + (music ? `<div class="sbd-bar-row"><span class="sbd-bar-lbl">${_sbdEsc(t('Music'))}</span><div class="sbd-bar">${musicBar}${over}</div></div>` : '')
       + `<div class="sbd-bar-row"><span class="sbd-bar-lbl"></span><div class="sbd-ruler"><span>${_sbdEsc(_sbdPos(0))}</span><span>${_sbdEsc(_sbdPos(scale))}</span></div></div>`;
}

function _sbdShowPlan(res) {
  (res.parts || []).forEach((r, i) => { const el = document.getElementById('sbd-start-' + i); if (_sbd.parts[i]) _sbd.parts[i].start_ms = r.start_ms; if (el) el.textContent = _sbdPos(r.start_ms); });
  document.getElementById('sbd-bars').innerHTML = _sbdBars(res);
  const total = t('Total {0}', _sbdSpan(res.length_ms || 0)) + (res.music_ms ? ' · ' + t('music {0}', _sbdFmt(res.music_ms)) : '') + ((res.free_ms || 0) > 0 ? ' · ' + t('Free {0}', _sbdSpan(res.free_ms)) : '');
  const issues = (res.parts || []).map((r, i) => r.issue ? `<div class="sbd-hint">${_sbdEsc(t('Row {0}: {1}', i + 1, r.issue))}</div>` : '').join('');
  const warns = (res.warnings || []).map(w => `<div class="sbd-warn">⚠ ${_sbdEsc(w)}</div>`).join('');
  return `<div>${_sbdEsc(total)}</div>${issues}${warns}`;
}

async function sbdPreview() {
  const res = await _sbdPost('/api/songbuilder/preview');
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'hint'); return; }
  document.getElementById('sbd-out').innerHTML = _sbdShowPlan(res);
}

async function _sbdPost(url) {
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_sbdSpec()) });
    return await r.json();
  } catch (e) { return { error: String(e) }; }
}

async function sbdBuild() {
  const res = await _sbdPost('/api/songbuilder/build');
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'err'); return; }
  _sbd.showId = res.show_id;
  await _sbdLoadList();
  document.getElementById('sbd-out').innerHTML =
    `<div>${_sbdEsc(t('✓ Show “{0}” built (ID {1}). Assign it to a song in the Setlist.', res.name, res.show_id))}</div>` + _sbdShowPlan(res);
  if (typeof showRefresh === 'function') showRefresh();
  if (typeof setStatus === 'function') setStatus(t('✓ Show “{0}” built — Save as new file… when you’re ready.', res.name), (res.warnings || []).length ? 'warn' : 'ok');
}
