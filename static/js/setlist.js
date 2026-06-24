/* =============================================================================
   setlist.js — Setlist Manager tab  (FileBot-style: songs | actions | pool)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _slotData      = [];   // [{id, caption, chaser_id, chaser_name}]
let _selectedSlot  = null;
let _setlistLoaded = false;
let _chasers       = [];
let _functions     = [];   // [{id, name, type, contains, vc_button, desc}]
let _songRows      = [];   // [{txt_name, qxw_id, qxw_name, in, hold, out}]
let _selectedSong  = -1;
let _selectedSongs = new Set();   // indices of all selected song rows (multi-select)
let _poolFiltered  = [];
let _selectedPoolIdx = -1;

// Pool filters
let _poolTypeFilter  = '';
let _poolVcFilter    = '';   // '' | 'has' | 'none'
let _poolUsedFilter  = '';   // '' | 'used' | 'unused'

// Collapsed type groups in pool
const _poolGroupCollapsed = new Set();


// ── Public API ────────────────────────────────────────────────────────────────

function invalidateSetlist() {
  _setlistLoaded = false;
  _selectedSlot  = null;
  _chasers       = [];
  _functions     = [];
  _songRows      = [];
  _selectedSong  = -1;
  _selectedSongs = new Set();
  _renderSlots([]);
  _clearSongEditor();
}

async function ensureSetlistLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  // Always re-fetch functions so descriptions loaded in the Dictionary tab
  // are reflected immediately in the pool (descriptions live in shared state).
  await _fetchFunctions();
  if (_setlistLoaded) return;
  _setlistLoaded = true;
  await Promise.all([refreshSlots(), _fetchChasers()]);
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
  _functions    = Array.isArray(data) ? data : [];
  _poolFiltered = _functions.slice();
  _populatePoolTypeFilter();
  _renderFnPool(_poolFiltered);
}

async function refreshFnPool() {
  await _fetchFunctions();
  _applyPoolFilters();
  setStatus('Function pool refreshed.', 'ok');
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
  _selectedSlot  = slotId;
  _selectedSong  = -1;
  _selectedSongs = new Set();
  _renderSlots(_slotData);

  const slot = _slotData.find(s => s.id === slotId);
  const titleEl = document.getElementById('song-pane-title');
  if (titleEl) titleEl.textContent = slot ? slot.caption : `Slot ${slotId}`;

  let details = await _apiJson(`/api/setlist/${slotId}/details`);
  if (!Array.isArray(details) || details.length === 0) {
    const plain = await _apiJson(`/api/setlist/${slotId}/songs`);
    details = (Array.isArray(plain) ? plain : []).map(s => ({
      txt_name: s, qxw_id: '', qxw_name: '', in: '0', hold: '4294967294', out: '0',
    }));
  }
  _songRows = details;
  _setEditorEnabled(true);
  _renderSongList();
  _updateSongCount();
  _clearTimingPanel();
  _renderFnPool(_poolFiltered);
  // Auto-match unassigned songs automatically
  await slAutoMatch();
}

function _clearSongEditor() {
  _songRows = [];
  _setEditorEnabled(false);
  const titleEl = document.getElementById('song-pane-title');
  if (titleEl) titleEl.textContent = 'Songs';
  const list = document.getElementById('fb-song-list');
  if (list) list.innerHTML = '<div class="slot-empty">Select a slot to see songs</div>';
  document.getElementById('song-count').textContent = '';
  _clearTimingPanel();
}

function _setEditorEnabled(on) {
  ['btn-add-song','btn-remove-song','btn-move-song-up','btn-move-song-dn',
   'btn-import-slot-txt','btn-export-slot-txt','btn-auto-match','btn-clear-assign','btn-clear-all',
   'btn-purge-clones',
   'sl-chaser-select','btn-generate-qxw','btn-export-sl-pdf','btn-export-sl-xml','btn-save-songs']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = !on;
    });
}

// ── Song list (FileBot left panel) ─────────────────────────────────────────────

function _renderSongList() {
  const list = document.getElementById('fb-song-list');
  if (!list) return;
  if (!_songRows.length) {
    list.innerHTML = '<div class="slot-empty" style="padding:16px">No songs. Click ➕ to add.</div>';
    return;
  }
  list.innerHTML = _songRows.map((row, i) => {
    const sel       = _selectedSongs.has(i) ? ' fb-song-active' : '';
    const hasAssign = !!row.qxw_id;
    const dotClass  = hasAssign ? 'fb-assign-dot fb-assign-dot-ok' : 'fb-assign-dot';
    const dotTitle  = hasAssign ? `Assigned: ${row.qxw_name || row.qxw_id}` : 'Not assigned';
    // Look up extra details (VC button, description) from the function pool
    const fn = hasAssign ? _functions.find(f => f.id === row.qxw_id) : null;
    // If assigned function is a (Setlist) clone, find its parent base function
    let parentHtml = '';
    if (fn && fn.name.endsWith(' (Setlist)')) {
      const baseName = fn.name.slice(0, -10);  // strip ' (Setlist)'
      const parent   = _functions.find(f => f.name === baseName);
      if (parent) {
        parentHtml = `<div class="fb-song-parent">↑ [${_esc(parent.id)}] ${_esc(parent.name)}</div>`;
      } else {
        // Parent was removed from workspace (e.g. gig-ready file) — still show the derived name
        parentHtml = `<div class="fb-song-parent fb-song-parent-missing">↑ ${_esc(baseName)}</div>`;
      }
    }
    const assignHtml = hasAssign
      ? `<div class="fb-song-assign">${_esc(row.qxw_name || row.qxw_id)}</div>`
        + parentHtml
        + (fn?.vc_button ? `<div class="fb-song-vc">🎛 ${_esc(fn.vc_button)}</div>` : '')
        + (fn?.desc      ? `<div class="fb-song-desc">${_esc(fn.desc)}</div>`        : '')
      : '';
    return `
      <div class="fb-song-item${sel}" data-idx="${i}" onclick="slSelectRow(${i}, event)">
        <span class="fb-song-num">${i + 1}</span>
        <span class="${dotClass}" title="${_esc(dotTitle)}"></span>
        <div class="fb-song-content">
          <input class="fb-song-name" type="text" value="${_esc(row.txt_name||'')}"
                 placeholder="Song name…"
                 onchange="slCellChanged(${i},'txt_name',this.value);_updateTimingLabel()"
                 onclick="event.stopPropagation()">
          ${assignHtml}
        </div>
      </div>`;
  }).join('');
}

// ── Row selection + timing panel ──────────────────────────────────────────────

function slSelectRow(idx, event) {
  if (event && (event.ctrlKey || event.metaKey)) {
    // Ctrl/Cmd+Click: toggle this row in multi-select
    if (_selectedSongs.has(idx)) {
      _selectedSongs.delete(idx);
      _selectedSong = _selectedSongs.size > 0 ? Math.max(..._selectedSongs) : -1;
    } else {
      _selectedSongs.add(idx);
      _selectedSong = idx;
    }
  } else if (event && event.shiftKey && _selectedSong >= 0) {
    // Shift+Click: range select from last anchor to here
    const lo = Math.min(_selectedSong, idx);
    const hi = Math.max(_selectedSong, idx);
    for (let i = lo; i <= hi; i++) _selectedSongs.add(i);
    _selectedSong = idx;
  } else {
    // Normal click: single select
    _selectedSongs = new Set([idx]);
    _selectedSong  = idx;
  }
  document.querySelectorAll('.fb-song-item').forEach((el, i) => {
    el.classList.toggle('fb-song-active', _selectedSongs.has(i));
  });
  _updatePoolAssignBtn();
  if (_selectedSongs.size === 1) {
    _updateTimingPanel();
  } else {
    _clearTimingPanel();
    const lbl = document.getElementById('timing-song-label');
    if (lbl && _selectedSongs.size > 1)
      lbl.textContent = `— ${_selectedSongs.size} songs selected —`;
  }
}

function _clearTimingPanel() {
  _setTimingEnabled(false);
  const lbl = document.getElementById('timing-song-label');
  if (lbl) lbl.textContent = '— select a song —';
  ['timing-in','timing-hold','timing-out'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
}

function _updateTimingPanel() {
  const row = _songRows[_selectedSong];
  if (!row) { _clearTimingPanel(); return; }
  _setTimingEnabled(true);
  const lbl = document.getElementById('timing-song-label');
  if (lbl) lbl.textContent = row.txt_name || `Song ${_selectedSong + 1}`;
  const inEl   = document.getElementById('timing-in');
  const holdEl = document.getElementById('timing-hold');
  const outEl  = document.getElementById('timing-out');
  if (inEl)   inEl.value   = _fmtMs(row.in   ?? '0');
  if (holdEl) holdEl.value = _fmtMs(row.hold ?? '4294967294');
  if (outEl)  outEl.value  = _fmtMs(row.out  ?? '0');
}

function _updateTimingLabel() {
  const row = _songRows[_selectedSong];
  const lbl = document.getElementById('timing-song-label');
  if (lbl && row) lbl.textContent = row.txt_name || `Song ${_selectedSong + 1}`;
}

function _setTimingEnabled(on) {
  ['timing-in','timing-hold','timing-out'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !on;
  });
}

function slTimingChanged(field, inputEl) {
  const row = _songRows[_selectedSong];
  if (!row) return;
  const val = _parseMs(inputEl.value);
  row[field] = val;
  inputEl.value = _fmtMs(val);  // normalize display
}

// ── Row editing ───────────────────────────────────────────────────────────────

function slCellChanged(idx, field, value) {
  if (_songRows[idx]) _songRows[idx][field] = value;
}

function slAddRow() {
  _songRows.push({ txt_name: '', qxw_id: '', qxw_name: '', in: '0', hold: '4294967294', out: '0' });
  _renderSongList();
  _updateSongCount();
  // Select the new row and scroll to it
  slSelectRow(_songRows.length - 1);
  const list = document.getElementById('fb-song-list');
  if (list) list.scrollTop = list.scrollHeight;
}

function slRemoveRow() {
  if (_selectedSong >= 0 && _selectedSong < _songRows.length) {
    slRemoveRowAt(_selectedSong);
  }
}

function slRemoveRowAt(idx) {
  _songRows.splice(idx, 1);
  _selectedSong = Math.min(_selectedSong, _songRows.length - 1);
  if (_selectedSong < 0 && _songRows.length > 0) _selectedSong = 0;
  _selectedSongs = _selectedSong >= 0 ? new Set([_selectedSong]) : new Set();
  _renderSongList();
  _updateSongCount();
  _updateTimingPanel();
  _renderFnPool(_poolFiltered);
}

function slMoveRow(dir) {
  const i = _selectedSong;
  const j = i + dir;
  if (i < 0 || j < 0 || j >= _songRows.length) return;
  [_songRows[i], _songRows[j]] = [_songRows[j], _songRows[i]];
  _selectedSong  = j;
  _selectedSongs = new Set([j]);
  _renderSongList();
}

function _updateSongCount() {
  const el = document.getElementById('song-count');
  if (el) el.textContent = _songRows.length
    ? `${_songRows.length} song${_songRows.length !== 1 ? 's' : ''}`
    : '';
}

// ── Function pool panel ───────────────────────────────────────────────────────

const _FN_TYPE_ICON = {
  Chaser:'🔄', Scene:'🎬', Sequence:'📋', EFX:'✨', Script:'📝',
  Show:'🎭', Audio:'🎵', Collection:'📦', RGBMatrix:'🌈',
};
const _TYPE_ORDER = ['Chaser','Scene','Sequence','EFX','Script','Show','Audio','Collection','RGBMatrix'];

function _computeUsageCounts() {
  const counts = {};
  for (const row of _songRows) {
    if (row.qxw_id) counts[row.qxw_id] = (counts[row.qxw_id] || 0) + 1;
  }
  return counts;
}

function _populatePoolTypeFilter() {
  const sel = document.getElementById('pool-type-filter');
  if (!sel) return;
  const types = [...new Set(_functions.map(f => f.type || '').filter(Boolean))].sort();
  sel.innerHTML = '<option value="">All types</option>'
    + types.map(t => `<option value="${_esc(t)}">${_esc(t)}</option>`).join('');
  sel.value = _poolTypeFilter;
}

/** Build a Set of base function names that have a matching "(Setlist)" clone. */
function _buildSetlistCloneSet() {
  const cloneSet = new Set();
  for (const f of _functions) {
    if (f.name.endsWith(' (Setlist)')) {
      cloneSet.add(f.name.slice(0, -10));   // strip ' (Setlist)' suffix
    }
  }
  return cloneSet;
}

function _applyPoolFilters() {
  const q   = (document.getElementById('fn-pool-filter')?.value || '').toLowerCase().trim();
  let result = _functions;
  if (_poolTypeFilter)
    result = result.filter(f => (f.type || '') === _poolTypeFilter);
  if (_poolVcFilter === 'has')
    result = result.filter(f => f.vc_button);
  else if (_poolVcFilter === 'none')
    result = result.filter(f => !f.vc_button);
  if (_poolUsedFilter) {
    const setlistClones = _buildSetlistCloneSet();
    const usageCounts   = _computeUsageCounts();
    if (_poolUsedFilter === 'used') {
      result = result.filter(f => (usageCounts[f.id] || 0) > 0 || setlistClones.has(f.name));
    } else if (_poolUsedFilter === 'unused') {
      result = result.filter(f => !(usageCounts[f.id] || 0) && !setlistClones.has(f.name));
    }
  }
  if (q)
    result = result.filter(f =>
      f.id.includes(q) ||
      f.name.toLowerCase().includes(q) ||
      (f.type      || '').toLowerCase().includes(q) ||
      (f.vc_button || '').toLowerCase().includes(q) ||
      (f.desc      || '').toLowerCase().includes(q));
  _poolFiltered    = result;
  _selectedPoolIdx = -1;
  _renderFnPool(_poolFiltered);
  _updatePoolAssignBtn();
}

function filterFnPool(q)            { _applyPoolFilters(); }
function filterFnPoolByType(type)   { _poolTypeFilter  = type || ''; _applyPoolFilters(); }
function filterFnPoolByVc(val)      { _poolVcFilter    = val  || ''; _applyPoolFilters(); }
function filterFnPoolByUsed(val)    { _poolUsedFilter  = val  || ''; _applyPoolFilters(); }

function togglePoolGroup(type) {
  if (_poolGroupCollapsed.has(type)) _poolGroupCollapsed.delete(type);
  else                               _poolGroupCollapsed.add(type);
  _renderFnPool(_poolFiltered);
}

function _renderFnPool(list) {
  const wrap = document.getElementById('fn-pool-list');
  if (!wrap) return;
  const countEl = document.getElementById('fn-pool-count');
  if (countEl) countEl.textContent = list.length
    ? `${list.length} function${list.length !== 1 ? 's' : ''}`
    : '';

  if (!list.length) {
    wrap.innerHTML = `<div class="slot-empty">${
      _functions.length === 0 ? 'Load a workspace to see functions' : 'No results'
    }</div>`;
    return;
  }

  const usageCounts   = _computeUsageCounts();
  const setlistClones = _buildSetlistCloneSet();   // names that have a (Setlist) clone

  // Group by type
  const groups = {};
  for (const f of list) {
    const t = f.type || 'Other';
    if (!groups[t]) groups[t] = [];
    groups[t].push(f);
  }
  const sortedTypes = Object.keys(groups).sort((a, b) => {
    const ai = _TYPE_ORDER.indexOf(a), bi = _TYPE_ORDER.indexOf(b);
    if (ai >= 0 && bi >= 0) return ai - bi;
    if (ai >= 0) return -1; if (bi >= 0) return 1;
    return a.localeCompare(b);
  });

  let html = `
    <div class="pool-col-header">
      <span class="pool-col-name">Function</span>
      <span class="pool-col-id">ID</span>
      <span class="pool-col-uses" title="★ = used in slot  ✦ = has (Setlist) clone">★✦</span>
      <span class="pool-col-vc" title="VC Button">VC</span>
    </div>`;

  for (const type of sortedTypes) {
    const icon      = _FN_TYPE_ICON[type] || '◻';
    const fns       = groups[type];
    const collapsed = _poolGroupCollapsed.has(type);
    html += `
      <div class="pool-type-header" onclick="togglePoolGroup('${_esc(type)}')">
        <span class="pool-grp-toggle">${collapsed ? '▶' : '▼'}</span>
        <span>${icon} ${_esc(type)}</span>
        <span class="pool-grp-count">${fns.length}</span>
      </div>
      <div class="pool-type-group${collapsed ? ' pool-grp-collapsed' : ''}">`;

    for (const f of fns) {
      const pIdx          = _poolFiltered.indexOf(f);
      const sel           = pIdx === _selectedPoolIdx ? ' fn-pool-item-active' : '';
      const uses          = usageCounts[f.id] || 0;
      const isSetlistUsed = setlistClones.has(f.name);
      const cntList       = f.contains ? f.contains.split(',').filter(Boolean) : [];

      let usesHtml;
      if (uses > 0 && isSetlistUsed) {
        usesHtml = `<span class="pool-col-uses pool-used" title="Used ${uses}× in this slot">★${uses}</span>`
                 + `<span class="pool-setlist-used" title="Has a (Setlist) clone in workspace — previously generated">✦</span>`;
      } else if (uses > 0) {
        usesHtml = `<span class="pool-col-uses pool-used" title="Used by ${uses} song(s)">★${uses}</span>`;
      } else if (isSetlistUsed) {
        usesHtml = `<span class="pool-setlist-used" title="Has a (Setlist) clone in workspace — previously generated">✦</span>`;
      } else {
        usesHtml = `<span class="pool-col-uses"></span>`;
      }
      const vcTxt   = f.vc_button || '';
      const vcHtml  = vcTxt
        ? `<div class="pool-item-vc">🎛 ${_esc(vcTxt)}</div>`
        : '';
      const descHtml = f.desc
        ? `<div class="pool-item-desc">${_esc(f.desc)}</div>`
        : '';
      html += `
        <div class="fn-pool-item${sel}" data-pidx="${pIdx}"
             ondblclick="slAssignFromPool()"
             onclick="slPoolSelect(${pIdx})">
          <div class="pool-item-row">
            <span class="pool-col-name fn-pool-name">${_esc(f.name)}</span>
            <span class="fn-pool-id">${_esc(f.id)}</span>
            ${usesHtml}
          </div>
          ${vcHtml}${descHtml}
        </div>`;
    }
    html += `</div>`;
  }
  wrap.innerHTML = html;
}

function slPoolSelect(idx) {
  _selectedPoolIdx = idx;
  document.querySelectorAll('.fn-pool-item').forEach(el => {
    el.classList.toggle('fn-pool-item-active', parseInt(el.dataset.pidx) === idx);
  });
  _updatePoolAssignBtn();
}

function _updatePoolAssignBtn() {
  const btn = document.getElementById('btn-pool-assign');
  if (btn) btn.disabled = _selectedPoolIdx < 0 || _selectedSongs.size === 0 || !_selectedSlot;
  const clrBtn = document.getElementById('btn-clear-assign');
  if (clrBtn) {
    const hasAssign = _selectedSongs.size > 0
      && [..._selectedSongs].some(i => !!_songRows[i]?.qxw_id);
    clrBtn.disabled = !hasAssign || !_selectedSlot;
  }
}

// ── Assignment actions ────────────────────────────────────────────────────────

function slAssignFromPool() {
  if (_selectedPoolIdx < 0 || _selectedSongs.size === 0) return;
  const fn = _poolFiltered[_selectedPoolIdx];
  if (!fn) return;

  const targets = [..._selectedSongs].sort((a, b) => a - b);
  for (const songIdx of targets) {
    const row = _songRows[songIdx];
    if (row) { row.qxw_id = fn.id; row.qxw_name = fn.name; }
  }

  if (targets.length === 1) {
    // Single: in-place DOM update + flash + auto-advance
    const songIdx = targets[0];
    const listEl = document.querySelector(`#fb-song-list .fb-song-item[data-idx="${songIdx}"]`);
    if (listEl) {
      const dot = listEl.querySelector('.fb-assign-dot');
      if (dot) { dot.classList.add('fb-assign-dot-ok'); dot.title = `Assigned: ${fn.name}`; }
      let assignDiv = listEl.querySelector('.fb-song-assign');
      if (!assignDiv) {
        assignDiv = document.createElement('div');
        assignDiv.className = 'fb-song-assign';
        listEl.querySelector('.fb-song-content')?.appendChild(assignDiv);
      }
      assignDiv.textContent = fn.name;
      listEl.classList.add('row-flash');
      setTimeout(() => listEl.classList.remove('row-flash'), 600);
    }
    if (songIdx < _songRows.length - 1) slSelectRow(songIdx + 1);
  } else {
    _renderSongList();
    setStatus(`Assigned "${fn.name}" to ${targets.length} songs.`, 'ok');
  }
  _renderFnPool(_poolFiltered);
}

function slClearAssignment() {
  if (_selectedSongs.size === 0) return;
  for (const idx of _selectedSongs) {
    const row = _songRows[idx];
    if (row) { row.qxw_id = ''; row.qxw_name = ''; }
  }
  _renderSongList();
  _renderFnPool(_poolFiltered);
  _updatePoolAssignBtn();
}

function slPurgeClones() {
  if (!_selectedSlot || !_songRows.length) return;
  const cloned = _songRows.filter(r => r.qxw_name && r.qxw_name.endsWith(' (Setlist)'));
  if (!cloned.length) {
    setStatus('No (Setlist) clone assignments found in this slot.', 'warn'); return;
  }
  if (!confirm(
    `Unassign ${cloned.length} song(s) linked to (Setlist) clones?\n\n` +
    `The clone functions remain in the workspace — only the song assignments are cleared. ` +
    `Use Re-Match or assign manually afterwards.`
  )) return;
  let count = 0;
  for (const row of _songRows) {
    if (row.qxw_name && row.qxw_name.endsWith(' (Setlist)')) {
      row.qxw_id = ''; row.qxw_name = ''; count++;
    }
  }
  _selectedSong  = -1;
  _selectedSongs = new Set();
  _renderSongList();
  _renderFnPool(_poolFiltered);
  _updatePoolAssignBtn();
  _clearTimingPanel();
  setStatus(`Cleared ${count} (Setlist) clone assignment(s). Songs are unassigned — Re-Match or assign manually.`, 'ok');
}

function slClearAllAssignments() {
  if (!_songRows.length) return;
  _songRows.forEach(r => { r.qxw_id = ''; r.qxw_name = ''; });
  _renderSongList();
  _renderFnPool(_poolFiltered);
  _updatePoolAssignBtn();
  setStatus('All assignments cleared.');
}

// ── Auto-match ────────────────────────────────────────────────────────────────

async function slAutoMatch() {
  if (!_selectedSlot || !_songRows.length) {
    setStatus('Select a slot with songs first.', 'warn'); return;
  }
  const unmatched = _songRows
    .map((r, i) => ({ idx: i, name: r.txt_name }))
    .filter(x => x.name && !_songRows[x.idx].qxw_id);

  if (!unmatched.length) {
    setStatus('All songs already have a function assigned.', 'ok'); return;
  }
  setStatus(`Auto-matching ${unmatched.length} song(s)…`);
  const res = await _apiPost('/api/setlist/auto-match', {
    songs: unmatched.map(x => x.name),
  });
  if (res.error) { setStatus(res.error, 'error'); return; }

  let matched = 0;
  res.forEach((m, i) => {
    if (m.matched_id) {
      const row = _songRows[unmatched[i].idx];
      row.qxw_id   = m.matched_id;
      row.qxw_name = m.matched_name;
      matched++;
    }
  });
  _renderSongList();
  _renderFnPool(_poolFiltered);
  setStatus(`Auto-matched ${matched} of ${unmatched.length} song(s).`, matched > 0 ? 'ok' : 'warn');
}

// ── Chaser selector ───────────────────────────────────────────────────────────

function _populateChaserDropdown() {
  const sel = document.getElementById('sl-chaser-select');
  if (!sel) return;
  let opts = '<option value="__new__">— Create new —</option>';
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
  setStatus(`Saved ${rows.length} songs.`, 'ok');
}

async function saveSongs() { await slSaveDetails(); }

// ── TXT load/save (global backup) ────────────────────────────────────────────

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
  setStatus(`Saved → ${result.path.split(/[\\/]/).pop()}`, 'ok');
}

// ── Per-slot TXT import ───────────────────────────────────────────────────────

function slImportSongsTxt(input) {
  if (!input.files.length || !_selectedSlot) return;
  const file   = input.files[0];
  const reader = new FileReader();
  reader.onload = async e => {
    const lines = e.target.result.split(/\r?\n/)
      .map(l => l.trim()).filter(l => l && !l.startsWith('#'));
    if (!lines.length) { setStatus('File is empty.', 'warn'); return; }
    if (_songRows.length > 0) {
      if (!confirm(`Replace ${_songRows.length} song(s) with ${lines.length} from "${file.name}"?`)) {
        input.value = ''; return;
      }
    }
    _songRows = lines.map(name => ({
      txt_name: name, qxw_id: '', qxw_name: '', in: '0', hold: '4294967294', out: '0',
    }));
    _renderSongList();
    _updateSongCount();
    _clearTimingPanel();
    _renderFnPool(_poolFiltered);
    await slSaveDetails();
    setStatus(`Imported ${lines.length} song(s) from "${file.name}".`, 'ok');
  };
  reader.readAsText(file, 'utf-8');
  input.value = '';
}

function slExportSongsTxt() {
  if (!_selectedSlot || !_songRows.length) {
    setStatus('No songs to export.', 'warn'); return;
  }
  const slot  = _slotData.find(s => s.id === _selectedSlot);
  const label = (slot?.caption || `Slot_${_selectedSlot}`)
    .replace(/[^\w\s-]/g,'').trim().replace(/\s+/g,'_');
  const lines = [
    `# QLC+ Swiss Knife — Setlist: ${slot?.caption || _selectedSlot}`,
    `# Slot ID: ${_selectedSlot}`, `# ${_songRows.length} song(s)`, '',
    ..._songRows.map(r => r.txt_name || ''),
  ];
  const blob = new Blob([lines.join('\n') + '\n'], { type: 'text/plain' });
  const a    = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = `${label}_setlist.txt`; a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`Exported ${_songRows.length} song(s) → ${label}_setlist.txt`);
}

// ── Generate QXW ──────────────────────────────────────────────────────────────

async function slGenerateQxw() {
  if (!_selectedSlot) return;

  // Save current rows first so the server has fresh data
  await slSaveDetails();

  const sel      = document.getElementById('sl-chaser-select');
  const targetId = sel?.value || '__new__';

  // Fetch the generated QXW as a raw blob from the server
  let resp;
  try {
    resp = await fetch(`/api/setlist/${_selectedSlot}/generate-qxw`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ target_chaser_id: targetId }),
    });
  } catch (e) {
    setStatus('Network error: ' + e.message, 'error'); return;
  }

  if (!resp.ok) {
    try {
      const err = await resp.json();
      setStatus(err.error || 'Generate failed.', 'error');
    } catch { setStatus('Generate failed.', 'error'); }
    return;
  }

  const blob          = await resp.blob();
  const suggestedName = resp.headers.get('X-Suggested-Filename') || 'workspace_GIG_READY.qxw';

  // ── Try native OS Save dialog (Chrome / Edge) ─────────────────────────────
  if (typeof window.showSaveFilePicker === 'function') {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        startIn: 'documents',
        types: [{
          description: 'QLC+ Workspace',
          accept: { 'application/xml': ['.qxw'] },
        }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      setStatus(`✓ Saved: ${handle.name}`, 'ok');
      await _fetchChasers();
      return;
    } catch (e) {
      if (e.name === 'AbortError') return;  // user cancelled the dialog
      // showSaveFilePicker threw for another reason → fall through to <a> download
    }
  }

  // ── Fallback: standard browser download ──────────────────────────────────
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 3000);
  setStatus(`✓ Downloaded: ${suggestedName}`, 'ok');
  await _fetchChasers();
}

// ── Export XML TXT ────────────────────────────────────────────────────────────

function slExportXmlTxt() {
  if (!_selectedSlot || !_songRows.length) {
    setStatus('Select a slot with songs first.', 'warn'); return;
  }
  const slot = _slotData.find(s => s.id === _selectedSlot);
  const chaserName = slot?.chaser_name || `Slot ${_selectedSlot}`;
  const _x = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  const lines = [
    '', `<Function ID="NEW_ID" Type="Chaser" Name="${_x(chaserName)}">`,
    ' <Speed FadeIn="0" FadeOut="0" Duration="4294967294"/>',
    ' <Direction>Forward</Direction>', ' <RunOrder>Loop</RunOrder>',
    ' <SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="Common"/>',
  ];
  let sc = 0;
  for (const d of _songRows) {
    if (d.qxw_id)
      lines.push(` <Step Number="${sc}" FadeIn="${d.in||0}" Hold="${d.hold||4294967294}" FadeOut="${d.out||0}">${d.qxw_id}</Step>`), sc++;
  }
  lines.push('</Function>', '');
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  const a    = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = `Slot${_selectedSlot}_Code_Export.txt`; a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`XML TXT exported (${sc} steps).`);
}

// ── Export PDF ────────────────────────────────────────────────────────────────

async function slExportPdf() {
  if (!_selectedSlot) return;
  const showName = prompt('Show name:', 'My Show') || 'Untitled';
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
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setStatus('PDF downloaded.', 'ok');
  } catch (err) { setStatus(String(err), 'error'); }
}

// ── Pool resize (drag handle) ─────────────────────────────────────────────────

function _initPoolResize() {
  const handle   = document.getElementById('pool-resize-handle');
  const poolPane = document.querySelector('.fn-pool-pane');
  if (!handle || !poolPane) return;
  let startX = 0, startW = 0;
  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startX = e.clientX;
    startW = poolPane.getBoundingClientRect().width;
    const onMove = ev => {
      const delta = startX - ev.clientX;
      const newW  = Math.max(220, Math.min(600, startW + delta));
      poolPane.style.width      = newW + 'px';
      poolPane.style.flexShrink = '0';
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _initPoolResize);
} else {
  _initPoolResize();
}

// ── Time formatting ───────────────────────────────────────────────────────────

const _INF_VAL = '4294967294';

function _fmtMs(v) {
  const s = String(v ?? '');
  if (s === _INF_VAL || s.toLowerCase() === 'inf') return 'Inf';
  const n = parseInt(s);
  return (isNaN(n) || n === 0) ? '0' : String(n);
}

function _parseMs(v) {
  const s = (v || '').trim().toLowerCase();
  if (s === '' || s === 'inf' || s === '∞') return _INF_VAL;
  const n = parseInt(s);
  return isNaN(n) ? '0' : String(Math.max(0, n));
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function _apiPost(url, body) {
  try {
    const r = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await r.json();
  } catch (e) { return { error: String(e) }; }
}
