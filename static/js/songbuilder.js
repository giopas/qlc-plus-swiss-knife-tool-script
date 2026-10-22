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
  const looks = _sbd.funcs.filter(f => _SBD_LOOK_TYPES.includes(f.type));
  document.getElementById('sbd-looks').innerHTML =
    looks.map(f => `<option value="${_sbdEsc(f.name)} [${_sbdEsc(f.id)}]">${_sbdEsc(f.type)}</option>`).join('');
  const audios = _sbd.funcs.filter(f => f.type === 'Audio');
  document.getElementById('sbd-audio').innerHTML =
    `<option value="">${_sbdEsc(t('— music file by path —'))}</option>` +
    audios.map(f => `<option value="${_sbdEsc(f.id)}">${_sbdEsc(f.name)}</option>`).join('');
  await _sbdLoadList();
  if (!_sbd.parts.length) { sbdNew(); }
  else _sbdRender();
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
  document.getElementById('sbd-audio').value = '';
  document.getElementById('sbd-path').value = '';
  document.getElementById('sbd-mlen').value = '';
  document.getElementById('sbd-music-note').textContent = '';
  _sbd.parts = [_sbdBlank('Intro'), _sbdBlank('Verse'), _sbdBlank('Chorus')];
  document.getElementById('sbd-out').innerHTML = '';
  _sbdRender();
}

function _sbdBlank(name) { return { name: name || '', look: '', function_id: '', length: '', repeat: 1, fade_in: '', fade_out: '', beats: '' }; }

async function sbdOpen(id) {
  if (!id) { sbdNew(); return; }
  const d = await (await fetch('/api/songbuilder/open?id=' + encodeURIComponent(id))).json();
  if (d.error) { _sbdOut(d.error, 'err'); return; }
  _sbd.showId = id;
  document.getElementById('sbd-name').value = d.name || '';
  document.getElementById('sbd-bpm').value = d.bpm || '';
  document.getElementById('sbd-bpb').value = d.beats_per_bar || 4;
  const m = d.music || {};
  document.getElementById('sbd-audio').value = m.function_id || '';
  document.getElementById('sbd-path').value = m.path || '';
  document.getElementById('sbd-mlen').value = m.length || '';
  _sbd.parts = (d.parts || []).map(p => ({ ...p, look: (_sbd.funcs.find(f => f.id === p.function_id) || {}).name || '' }));
  _sbdRender();
  sbdMusicChanged();
  sbdPreview();
}

function _sbdRender() {
  const body = document.getElementById('sbd-rows');
  if (!body) return;
  body.innerHTML = _sbd.parts.map((p, i) => {
    const label = p.function_id ? `${p.look} [${p.function_id}]` : '';
    return `<tr data-i="${i}">
      <td>${i + 1}</td>
      <td><input type="text" value="${_sbdEsc(p.name)}" oninput="sbdCell(${i},'name',this.value)" placeholder="${_sbdEsc(t('Part'))}"></td>
      <td><input type="text" list="sbd-looks" value="${_sbdEsc(label)}" onchange="sbdLook(${i},this)" placeholder="${_sbdEsc(t('Search a scene or chaser…'))}"></td>
      <td style="width:90px"><input type="text" value="${_sbdEsc(p.length)}" oninput="sbdCell(${i},'length',this.value)" placeholder="8 bars"></td>
      <td style="width:60px"><input type="text" value="${_sbdEsc(p.repeat)}" oninput="sbdCell(${i},'repeat',this.value)"></td>
      <td style="width:70px"><input type="text" value="${_sbdEsc(p.fade_in)}" oninput="sbdCell(${i},'fade_in',this.value)" placeholder="0"></td>
      <td style="width:70px"><input type="text" value="${_sbdEsc(p.fade_out)}" oninput="sbdCell(${i},'fade_out',this.value)" placeholder="0"></td>
      <td style="width:70px"><input type="text" value="${_sbdEsc(p.beats)}" oninput="sbdCell(${i},'beats',this.value)" placeholder="–"></td>
      <td class="sbd-start" id="sbd-start-${i}">${p.start_ms === undefined ? '' : _sbdFmt(p.start_ms)}</td>
      <td style="white-space:nowrap"><button class="btn btn-surface" style="padding:0 6px" onclick="sbdMove(${i},-1)" aria-label="${_sbdEsc(t('Up'))}">↑</button>
        <button class="btn btn-surface" style="padding:0 6px" onclick="sbdMove(${i},1)" aria-label="${_sbdEsc(t('Down'))}">↓</button>
        <button class="btn btn-surface" style="padding:0 6px" onclick="sbdRemove(${i})" aria-label="${_sbdEsc(t('Remove'))}">×</button></td>
    </tr>`;
  }).join('');
}

function sbdDirty() { /* the preview is stale; nothing to do until the next Preview */ }
function sbdCell(i, key, val) { if (_sbd.parts[i]) _sbd.parts[i][key] = val; }
function sbdAddRow() { _sbd.parts.push(_sbdBlank('')); _sbdRender(); }
function sbdRemove(i) { _sbd.parts.splice(i, 1); _sbdRender(); }
function sbdMove(i, d) {
  const j = i + d;
  if (j < 0 || j >= _sbd.parts.length) return;
  [_sbd.parts[i], _sbd.parts[j]] = [_sbd.parts[j], _sbd.parts[i]];
  _sbdRender();
}

function sbdLook(i, el) {
  const m = /\[(\d+)\]\s*$/.exec(el.value);
  const f = m ? _sbd.funcs.find(x => x.id === m[1]) : _sbd.funcs.find(x => x.name === el.value.trim() && _SBD_LOOK_TYPES.includes(x.type));
  if (f) { _sbd.parts[i].function_id = f.id; _sbd.parts[i].look = f.name; if (!_sbd.parts[i].name) { _sbd.parts[i].name = f.name; } el.value = `${f.name} [${f.id}]`; }
  else { _sbd.parts[i].function_id = ''; _sbd.parts[i].look = ''; }
}

async function sbdMusicChanged() {
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
    show_id: _sbd.showId,
    music: fid ? { function_id: fid } : (path ? { path, length: document.getElementById('sbd-mlen').value.trim() } : {}),
    parts: _sbd.parts.map(p => ({ name: p.name, function_id: p.function_id, length: p.length, repeat: p.repeat,
                                  fade_in: p.fade_in, fade_out: p.fade_out, beats: p.beats })),
  };
}

function _sbdOut(html, cls) { document.getElementById('sbd-out').innerHTML = `<div class="${cls === 'err' ? 'sbd-err' : ''}">${html}</div>`; }

function _sbdShowPlan(res) {
  (res.parts || []).forEach((r, i) => { const el = document.getElementById('sbd-start-' + i); if (el) el.textContent = _sbdFmt(r.start_ms); if (_sbd.parts[i]) _sbd.parts[i].start_ms = r.start_ms; });
  const total = t('Total {0}', _sbdFmt(res.length_ms || 0)) + (res.music_ms ? ' · ' + t('music {0}', _sbdFmt(res.music_ms)) : '');
  const warns = (res.warnings || []).map(w => `<div class="sbd-warn">⚠ ${_sbdEsc(w)}</div>`).join('');
  return `<div>${_sbdEsc(total)}</div>${warns}`;
}

async function sbdPreview() {
  const res = await _sbdPost('/api/songbuilder/preview');
  if (res.error) { _sbdOut(_sbdEsc(res.error), 'err'); return; }
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
