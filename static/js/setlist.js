/* =============================================================================
   setlist.js — Setlist Manager tab (full song detail table + chaser generation)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _slotData      = [];   // [{id, caption, chaser_id, chaser_name}]
let _selectedSlot  = null; // slot id currently being edited
let _setlistLoaded = false;
let _chasers       = [];   // [{id, name}] — available Chaser functions
let _functions     = [];   // [{id, name, type}] — all workspace functions (for dropdown)
let _songRows      = [];   // [{txt_name, qxw_id, qxw_name, in, hold, out}] — current slot
let _selectedSong  = -1;   // selected row index in _songRows


// ── Public API ────────────────────────────────────────────────────────────────

function invalidateSetlist() {
  _setlistLoaded = false;
  _selectedSlot  = null;
  _chasers       = [];
  _functions     = [];
  _songRows      = [];
  _selectedSong  = -1;
  _renderSlots([]);
  _clearSongEditor();
}

async function ensureSetlistLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_setlistLoaded) return;
  _setlistLoaded = true;
  await Promise.all([refreshSlots(), _fetchChasers(), _fetchFunctions()]);
}

// ── Data fetching ─────────────────────────────────────────────────────────────

async function refreshSlots() {
  const data = await _apiJson('/api/setlist/slots');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _slotData = Array.isArray(data) ? data : [];
  _renderSlots(_slotData);
}

async function _fetchChasers() {
  const data = await _apiJson('/api/setlist/chasers');
  _chasers = Array.isArray(data) ? data : [];
  _populateChaserDropdown();
}

async function _fetchFunctions() {
  const data = await _apiJson('/api/functions');
  _functions = Array.isArray(data) ? data : [];
}

// ── Slot list ──────────────────────────────────────────────────────────────────

function _renderSlots(slots) {
  const el = document.getElementById('slot-list');
  if (!el) return;
  if (!slots.length) {
    el.innerHTML = '<div class="slot-empty">No CueList slots found in workspace</div>';
    return;
  }
  el.innerHTML = slots.map(s => `
    <div class="slot-item${_selectedSlot === s.id ? ' active' : ''}"
         onclick="selectSlot('${_esc(s.id)}')">
      <div class="slot-caption">${_esc(s.caption)}</div>
      <div class="slot-sub">${s.chaser_name ? '↪ ' + _esc(s.chaser_name) : 'No chaser linked'}</div>
    </div>
  `).join('');
}

async function selectSlot(slotId) {
  _selectedSlot = slotId;
  _selectedSong = -1;
  _renderSlots(_slotData);

  const slot = _slotData.find(s => s.id === slotId);
  const titleEl = document.getElementById('song-pane-title');
  if (titleEl) titleEl.textContent = slot ? `Songs — ${slot.caption}` : `Slot ${slotId}`;

  // Load detailed rows; fall back to simple strings
  let details = await _apiJson(`/api/setlist/${slotId}/details`);
  if (!Array.isArray(details) || details.length === 0) {
    const plain = await _apiJson(`/api/setlist/${slotId}/songs`);
    details = (Array.isArray(plain) ? plain : []).map(s => ({
      txt_name: s, qxw_id: '', qxw_name: '', in: '0', hold: '4294967294', out: '0',
    }));
  }
  _songRows = details;
  _setEditorEnabled(true);
  _renderSongTable();
  _updateSongCount();
}

function _clearSongEditor() {
  _songRows = [];
  _setEditorEnabled(false);
  const titleEl = document.getElementById('song-pane-title');
  if (titleEl) titleEl.textContent = 'Select a slot →';
  const body = document.getElementById('song-detail-body');
  if (body) body.innerHTML = `
    <tr id="song-placeholder-row">
      <td colspan="7" style="text-align:center;color:var(--overlay0);padding:20px">
        Select a slot on the left to edit its songs.
      </td>
    </tr>`;
  document.getElementById('song-count').textContent = '';
}

function _setEditorEnabled(on) {
  ['btn-add-song','btn-remove-song','btn-move-song-up','btn-move-song-dn',
   'sl-chaser-select','btn-generate-qxw','btn-export-sl-pdf','btn-export-sl-xml','btn-save-songs']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = !on;
    });
}

// ── Song detail table render ──────────────────────────────────────────────────

function _renderSongTable() {
  const body = document.getElementById('song-detail-body');
  if (!body) return;
  if (!_songRows.length) {
    body.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--overlay0);padding:20px">
      No songs. Click ➕ Add Song to start.
    </td></tr>`;
    return;
  }

  // Build function options once
  const fnOpts = _functions.map(f =>
    `<option value="${_esc(f.id)}">${_esc(f.name)} [${_esc(f.type||'')}]</option>`
  ).join('');
  const fnOptsWithBlank = `<option value="">— none —</option>${fnOpts}`;

  body.innerHTML = _songRows.map((row, i) => {
    const sel  = i === _selectedSong ? ' row-active' : '';
    const inV  = _fmtMs(row.in   ?? '0');
    const holdV= _fmtMs(row.hold ?? '4294967294');
    const outV = _fmtMs(row.out  ?? '0');
    return `
    <tr class="song-row${sel}" data-idx="${i}" onclick="slSelectRow(${i})">
      <td class="song-num">${i + 1}</td>
      <td><input class="song-field" type="text" value="${_esc(row.txt_name||'')}"
            onchange="slCellChanged(${i},'txt_name',this.value)"
            onclick="event.stopPropagation()"></td>
      <td>
        <select class="song-field song-fn-sel"
                onchange="slCellChanged(${i},'qxw_id',this.value);slSyncFnName(${i},this)"
                onclick="event.stopPropagation()">
          ${fnOptsWithBlank}
        </select>
      </td>
      <td><input class="song-field song-time" type="text" value="${_esc(inV)}"
            placeholder="0" title="ms or 'Inf'"
            onchange="slCellChanged(${i},'in',_parseMs(this.value))"
            onclick="event.stopPropagation()"></td>
      <td><input class="song-field song-time" type="text" value="${_esc(holdV)}"
            placeholder="Inf" title="ms or 'Inf'"
            onchange="slCellChanged(${i},'hold',_parseMs(this.value))"
            onclick="event.stopPropagation()"></td>
      <td><input class="song-field song-time" type="text" value="${_esc(outV)}"
            placeholder="0" title="ms or 'Inf'"
            onchange="slCellChanged(${i},'out',_parseMs(this.value))"
            onclick="event.stopPropagation()"></td>
      <td><button class="btn-icon" title="Remove row"
            onclick="slRemoveRowAt(${i});event.stopPropagation()">✕</button></td>
    </tr>`;
  }).join('');

  // Set function dropdown selections
  _songRows.forEach((row, i) => {
    const sel = body.querySelector(`tr[data-idx="${i}"] .song-fn-sel`);
    if (sel && row.qxw_id) sel.value = String(row.qxw_id);
  });
}

// ── Row editing ───────────────────────────────────────────────────────────────

function slSelectRow(idx) {
  _selectedSong = idx;
  document.querySelectorAll('#song-detail-body tr.song-row').forEach((tr, i) => {
    tr.classList.toggle('row-active', i === idx);
  });
}

function slCellChanged(idx, field, value) {
  if (_songRows[idx]) _songRows[idx][field] = value;
}

function slSyncFnName(idx, sel) {
  if (!_songRows[idx]) return;
  const opt = sel.options[sel.selectedIndex];
  _songRows[idx].qxw_name = opt ? opt.text.replace(/\s*\[.*?\]\s*$/, '') : '';
  _songRows[idx].qxw_id   = sel.value;
}

function slAddRow() {
  _songRows.push({ txt_name: '', qxw_id: '', qxw_name: '', in: '0', hold: '4294967294', out: '0' });
  _renderSongTable();
  _updateSongCount();
  // Scroll to bottom
  const wrap = document.getElementById('song-detail-wrap');
  if (wrap) wrap.scrollTop = wrap.scrollHeight;
}

function slRemoveRow() {
  if (_selectedSong >= 0 && _selectedSong < _songRows.length) {
    slRemoveRowAt(_selectedSong);
  }
}

function slRemoveRowAt(idx) {
  _songRows.splice(idx, 1);
  _selectedSong = Math.min(_selectedSong, _songRows.length - 1);
  _renderSongTable();
  _updateSongCount();
}

function slMoveRow(dir) {
  const i = _selectedSong;
  const j = i + dir;
  if (i < 0 || j < 0 || j >= _songRows.length) return;
  [_songRows[i], _songRows[j]] = [_songRows[j], _songRows[i]];
  _selectedSong = j;
  _renderSongTable();
}

function _updateSongCount() {
  const el = document.getElementById('song-count');
  if (el) el.textContent = _songRows.length
    ? `${_songRows.length} song${_songRows.length !== 1 ? 's' : ''}`
    : '';
}

// ── Chaser selector ───────────────────────────────────────────────────────────

function _populateChaserDropdown() {
  const sel = document.getElementById('sl-chaser-select');
  if (!sel) return;
  let opts = '<option value="__new__">— Create new chaser —</option>';
  for (const c of _chasers)
    opts += `<option value="${_esc(c.id)}">${_esc(c.name)}</option>`;
  sel.innerHTML = opts;
}

// ── Save ──────────────────────────────────────────────────────────────────────

async function slSaveDetails() {
  if (!_selectedSlot) return;
  const rows = _songRows.map(r => ({
    txt_name: r.txt_name || '',
    qxw_id:   r.qxw_id   || '',
    qxw_name: r.qxw_name || '',
    in:       String(r.in   ?? '0'),
    hold:     String(r.hold ?? '4294967294'),
    out:      String(r.out  ?? '0'),
  }));
  const res = await _apiPost(`/api/setlist/${_selectedSlot}/details`, { rows });
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(`Saved ${rows.length} songs for slot ${_selectedSlot}.`, 'ok');
}

// ── Legacy: save songs as plain strings (for TXT compat) ─────────────────────

async function saveSongs() {
  // Alias kept for backward compatibility (called by old btn-save-songs)
  await slSaveDetails();
}

// ── TXT load/save ─────────────────────────────────────────────────────────────

async function loadSetlistFile() {
  const path = document.getElementById('setlist-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiPost('/api/setlist/load', { path });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Loaded ${result.count} slot(s) from file.`, 'ok');
  if (_selectedSlot) await selectSlot(_selectedSlot);
}

async function saveSetlistFile() {
  const path = document.getElementById('setlist-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiPost('/api/setlist/save', { path });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Saved setlist → ${result.path.split(/[\\/]/).pop()}`, 'ok');
}

// ── Generate QXW ──────────────────────────────────────────────────────────────

async function slGenerateQxw() {
  if (!_selectedSlot) return;
  await slSaveDetails();  // flush UI state first
  const sel = document.getElementById('sl-chaser-select');
  const targetId = sel?.value || '__new__';
  const res = await _apiPost(`/api/setlist/${_selectedSlot}/generate-qxw`,
                             { target_chaser_id: targetId });
  if (res.error) { setStatus(res.error, 'error'); return; }
  setStatus(`QXW saved → ${res.filename}`, 'ok');
  await _fetchChasers();  // refresh chaser list in case a new one was created
}

// ── Export XML TXT (raw Chaser XML block, like original script) ───────────────

function slExportXmlTxt() {
  if (!_selectedSlot || !_songRows.length) {
    setStatus('Select a slot with songs first.', 'warn'); return;
  }
  const slot = _slotData.find(s => s.id === _selectedSlot);
  const chaserName = slot?.chaser_name || `Slot ${_selectedSlot}`;
  const _x = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

  const lines = [
    '',
    `<Function ID="NEW_ID" Type="Chaser" Name="${_x(chaserName)}">`,
    ' <Speed FadeIn="0" FadeOut="0" Duration="4294967294"/>',
    ' <Direction>Forward</Direction>',
    ' <RunOrder>Loop</RunOrder>',
    ' <SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="Common"/>',
  ];
  let sc = 0;
  for (const d of _songRows) {
    if (d.qxw_id) {
      lines.push(
        ` <Step Number="${sc}" FadeIn="${d.in||0}" Hold="${d.hold||4294967294}" FadeOut="${d.out||0}">${d.qxw_id}</Step>`
      );
      sc++;
    }
  }
  lines.push('</Function>', '');

  const txt  = lines.join('\n');
  const blob = new Blob([txt], { type: 'text/plain' });
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = `Slot${_selectedSlot}_Code_Export.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`XML TXT exported (${sc} steps).`);
}

// ── Export PDF ────────────────────────────────────────────────────────────────

async function slExportPdf() {
  if (!_selectedSlot) return;
  const showName = prompt('Show name for PDF:', 'My Show') || 'Untitled';
  try {
    const resp = await fetch(`/api/setlist/${_selectedSlot}/export-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_name: showName, paper: 'A4 Landscape' }),
    });
    if (!resp.ok) { const e = await resp.json(); setStatus(e.error || 'Error', 'error'); return; }
    const blob = await resp.blob();
    const cd   = resp.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename=([^\s;]+)/);
    const name = m ? m[1] : `setlist_${_selectedSlot}.pdf`;
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setStatus('Setlist PDF downloaded.', 'ok');
  } catch (err) { setStatus(String(err), 'error'); }
}

// ── Time formatting helpers ───────────────────────────────────────────────────

const _INF_VAL = '4294967294';

function _fmtMs(v) {
  const s = String(v ?? '');
  if (s === _INF_VAL || s.toLowerCase() === 'inf') return 'Inf';
  const n = parseInt(s);
  if (isNaN(n) || n === 0) return '0';
  return String(n);
}

function _parseMs(v) {
  const s = (v || '').trim().toLowerCase();
  if (s === '' || s === 'inf' || s === '∞') return _INF_VAL;
  const n = parseInt(s);
  return isNaN(n) ? '0' : String(Math.max(0, n));
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function _apiPost(url, body) {
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await r.json();
  } catch (e) { return { error: String(e) }; }
}
