/* =============================================================================
   setlist.js — Setlist Manager tab
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _slotData      = [];    // [{id, caption, chaser_id, chaser_name}]
let _selectedSlot  = null;  // slot id currently being edited
let _setlistLoaded = false;

// ── Public API (called by app.js) ─────────────────────────────────────────────

function invalidateSetlist() {
  _setlistLoaded = false;
  _selectedSlot  = null;
  _renderSlots([]);
  _clearSongEditor();
}

async function ensureSetlistLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_setlistLoaded) return;
  _setlistLoaded = true;
  await refreshSlots();
}

// ── Slot list ──────────────────────────────────────────────────────────────────

async function refreshSlots() {
  const data = await _apiJson('/api/setlist/slots');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _slotData = Array.isArray(data) ? data : [];
  _renderSlots(_slotData);
}

function _renderSlots(slots) {
  const el = document.getElementById('slot-list');
  if (!slots.length) {
    el.innerHTML = '<div class="slot-empty">No CueList slots found in workspace</div>';
    return;
  }
  el.innerHTML = slots.map(s => `
    <div class="slot-item${_selectedSlot === s.id ? ' active' : ''}"
         onclick="selectSlot('${s.id}')">
      <div class="slot-caption">${_esc(s.caption)}</div>
      <div class="slot-sub">${s.chaser_name ? '↪ ' + _esc(s.chaser_name) : 'No chaser linked'}</div>
    </div>
  `).join('');
}

async function selectSlot(slotId) {
  _selectedSlot = slotId;
  _renderSlots(_slotData);   // re-render to update .active class

  const slot = _slotData.find(s => s.id === slotId);
  const titleEl = document.getElementById('song-pane-title');
  if (slot) titleEl.textContent = `Songs — ${slot.caption}`;

  const songs = await _apiJson(`/api/setlist/${slotId}/songs`);
  const editor = document.getElementById('song-editor');
  const saveBtn = document.getElementById('btn-save-songs');

  editor.value    = (Array.isArray(songs) ? songs : []).join('\n');
  editor.disabled = false;
  saveBtn.disabled = false;
  _updateSongCount();
}

function _clearSongEditor() {
  const editor  = document.getElementById('song-editor');
  const saveBtn = document.getElementById('btn-save-songs');
  const title   = document.getElementById('song-pane-title');
  editor.value     = '';
  editor.disabled  = true;
  saveBtn.disabled = true;
  title.textContent = 'Select a slot →';
  document.getElementById('song-count').textContent = '';
}

function _updateSongCount() {
  const lines = document.getElementById('song-editor').value
    .split('\n').filter(l => l.trim());
  document.getElementById('song-count').textContent =
    lines.length ? `${lines.length} song${lines.length !== 1 ? 's' : ''}` : '';
}

// ── Save songs for current slot ───────────────────────────────────────────────

async function saveSongs() {
  if (!_selectedSlot) return;
  const lines  = document.getElementById('song-editor').value
    .split('\n').filter(l => l.trim());
  const result = await _apiJson(`/api/setlist/${_selectedSlot}/songs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ songs: lines }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Saved ${lines.length} songs for slot ${_selectedSlot}`);
  _updateSongCount();
}

// ── Load / Save TXT ───────────────────────────────────────────────────────────

async function loadSetlistFile() {
  const path = document.getElementById('setlist-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiJson('/api/setlist/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Loaded ${result.count} slot(s) from file`);
  // Refresh editor if a slot is selected
  if (_selectedSlot) selectSlot(_selectedSlot);
}

async function saveSetlistFile() {
  const path = document.getElementById('setlist-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiJson('/api/setlist/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Saved setlist → ${result.path.split(/[\\/]/).pop()}`);
}

// ── Song count update on keyup ────────────────────────────────────────────────
document.getElementById('song-editor')
  .addEventListener('input', _updateSongCount);

// ── Escape helper (reuse from app.js global scope) ───────────────────────────
function _esc(s) {
  return String(s ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
