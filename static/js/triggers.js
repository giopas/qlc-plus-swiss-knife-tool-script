/* =============================================================================
   triggers.js — Trigger Manager tab
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _trgData          = [];         // raw list from server
let _trgFiltered      = [];         // current filtered/sorted view
let _trgSort          = { col: 'caption', dir: 1 };
let _trgSelUid        = null;       // selected trigger uid
let _trgLoaded        = false;
let _trgConflictUids  = new Set();  // UIDs with duplicate key bindings
let _trgMatrixVisible = false;      // whether matrix panel is open

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateTriggers() {
  _trgLoaded        = false;
  _trgData          = [];
  _trgSelUid        = null;
  _trgConflictUids  = new Set();
  _renderTrgTable([]);
  _hideTrgEditForm();
}

async function ensureTriggersLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_trgLoaded) return;
  _trgLoaded = true;
  await _loadTriggers();
}

// ── Data fetch ────────────────────────────────────────────────────────────────

async function _loadTriggers() {
  const data = await _apiJson('/api/triggers/');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _trgData     = Array.isArray(data) ? data : [];
  _trgFiltered = _trgData;
  _applyTrgFilter();
}

// ── Filter ────────────────────────────────────────────────────────────────────

function filterTriggers(q) {
  const assignedOnly = document.getElementById('trg-assigned-only').checked;
  q = (q || '').toLowerCase().trim();
  _trgFiltered = _trgData.filter(r => {
    if (assignedOnly && !r.has) return false;
    if (!q) return true;
    return r.caption.toLowerCase().includes(q) ||
           r.type.toLowerCase().includes(q) ||
           r.func.toLowerCase().includes(q) ||
           r.key.toLowerCase().includes(q);
  });
  _renderTrgTable(_sortTrg(_trgFiltered));
}

function _applyTrgFilter() {
  filterTriggers(document.getElementById('trg-filter').value);
}

// ── Sort ──────────────────────────────────────────────────────────────────────

function _sortTrg(rows) {
  const { col, dir } = _trgSort;
  return [...rows].sort((a, b) => {
    const av = (a[col] || '').toLowerCase();
    const bv = (b[col] || '').toLowerCase();
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

function _trgSortBy(col) {
  if (_trgSort.col === col) _trgSort.dir *= -1;
  else { _trgSort.col = col; _trgSort.dir = 1; }
  _renderTrgTable(_sortTrg(_trgFiltered));
}

// ── Render ────────────────────────────────────────────────────────────────────

function _renderTrgTable(rows) {
  const wrap = document.getElementById('trg-table-wrap');

  if (!rows.length) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--overlay0);font-size:12px">'
                   + (_trgData.length === 0
                       ? 'Load a workspace to see triggers.'
                       : 'No results for current filter.') + '</div>';
    return;
  }

  const sortArrow = k =>
    _trgSort.col !== k ? '' : (_trgSort.dir === 1 ? ' ↑' : ' ↓');

  const cols = [
    { key: '●',       label: '●',        w: '30px',  sort: false },
    { key: 'type',    label: 'Type',      w: '120px', sort: true  },
    { key: 'caption', label: 'Caption',   w: '22%',   sort: true  },
    { key: 'func',    label: 'Function',  w: '22%',   sort: true  },
    { key: 'key',     label: 'Key',       w: '90px',  sort: true  },
    { key: 'uni',     label: 'MIDI Uni',  w: '76px',  sort: false },
    { key: 'ch',      label: 'MIDI Ch',   w: '76px',  sort: false },
  ];

  const ths = cols.map(c => {
    const cls = (c.sort && _trgSort.col === c.key)
      ? (_trgSort.dir === 1 ? 'sort-asc' : 'sort-desc') : '';
    const click = c.sort ? `onclick="_trgSortBy('${c.key}')"` : '';
    return `<th ${click} class="${cls}" style="width:${c.w}">${c.label}${c.sort ? sortArrow(c.key) : ''}</th>`;
  }).join('');

  const trs = rows.map(r => {
    const isActive   = r.uid === _trgSelUid;
    const isConflict = _trgConflictUids.has(r.uid);
    const cls = [isActive ? 'row-active' : '', isConflict ? 'row-conflict' : ''].filter(Boolean).join(' ');
    const dot     = r.has
      ? '<span class="dot-yes" title="Has trigger">●</span>'
      : '<span class="dot-no"  title="No trigger">●</span>';
    const keyCell  = r.key  ? `<span class="key-cell">${_te(r.key)}</span>`  : '<span class="no-val">—</span>';
    const uniCell  = r.uni  ? `<span class="midi-cell">${_te(r.uni)}</span>` : '<span class="no-val">—</span>';
    const chCell   = r.ch   ? `<span class="midi-cell">${_te(r.ch)}</span>`  : '<span class="no-val">—</span>';
    const conflict  = isConflict ? ' title="Duplicate key binding"' : '';
    return `<tr class="${cls}"${conflict} onclick="selectTrigger('${r.uid}')">
      <td>${dot}</td>
      <td>${_badge(r.type)}</td>
      <td class="td-wrap">${_te(r.caption)}</td>
      <td class="td-wrap">${_te(r.func) || '<span class="no-val">—</span>'}</td>
      <td>${keyCell}</td>
      <td>${uniCell}</td>
      <td>${chCell}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="custom-table">
    <thead><tr>${ths}</tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

// ── Row selection ─────────────────────────────────────────────────────────────

function selectTrigger(uid) {
  _trgSelUid = uid;
  // Re-render to highlight row
  _renderTrgTable(_sortTrg(_trgFiltered));

  const row = _trgData.find(r => r.uid === uid);
  if (!row) return;

  document.getElementById('trg-edit-info').style.display = 'none';
  const form = document.getElementById('trg-edit-form');
  form.style.display = 'flex';

  document.getElementById('trg-caption-display').textContent = `${row.type}: ${row.caption}`;
  document.getElementById('trg-key-input').value = row.key || '';
  document.getElementById('trg-uni-input').value = row.uni || '';
  document.getElementById('trg-ch-input').value  = row.ch  || '';
}

function _hideTrgEditForm() {
  document.getElementById('trg-edit-info').style.display = 'block';
  document.getElementById('trg-edit-form').style.display = 'none';
  document.getElementById('trg-caption-display').textContent = '';
  document.getElementById('trg-key-input').value = '';
  document.getElementById('trg-uni-input').value = '';
  document.getElementById('trg-ch-input').value  = '';
}

// ── Apply / Clear edit ────────────────────────────────────────────────────────

async function applyTriggerEdit() {
  if (!_trgSelUid) return;
  const key = document.getElementById('trg-key-input').value.trim();
  const uni = document.getElementById('trg-uni-input').value.trim();
  const ch  = document.getElementById('trg-ch-input').value.trim();

  const result = await _apiJson(`/api/triggers/${_trgSelUid}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, uni, ch }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }

  // Update local cache
  const row = _trgData.find(r => r.uid === _trgSelUid);
  if (row) { row.key = key; row.uni = uni; row.ch = ch; row.has = !!(key || (uni && ch)); }

  _applyTrgFilter();
  setStatus(`Updated trigger: ${_trgSelUid}`);
}

async function clearTriggerEdit() {
  document.getElementById('trg-key-input').value = '';
  document.getElementById('trg-uni-input').value = '';
  document.getElementById('trg-ch-input').value  = '';
  await applyTriggerEdit();
}

// ── Duplicates (inline conflict highlighting) ─────────────────────────────────

async function checkDuplicates() {
  const data = await _apiJson('/api/triggers/duplicates');
  if (data.error) { setStatus(data.error, 'error'); return; }
  const dupKeys = Object.keys(data);

  // Build a set of UIDs whose key appears in the duplicates map
  _trgConflictUids = new Set();
  if (dupKeys.length) {
    const dupSet = new Set(dupKeys);
    _trgData.forEach(r => { if (r.key && dupSet.has(r.key)) _trgConflictUids.add(r.uid); });
  }

  _renderTrgTable(_sortTrg(_trgFiltered)); // re-render with red highlights

  if (!dupKeys.length) {
    setStatus('No duplicate key bindings found ✓', 'ok');
  } else {
    const count = _trgConflictUids.size;
    const summary = dupKeys.map(k => `${k}: ${data[k].join(', ')}`).join(' | ');
    setStatus(`⚠ ${count} trigger(s) share a key — ${summary}`, 'warn');
  }
}

// ── Save to QXW ──────────────────────────────────────────────────────────────

async function saveTriggers() {
  const result = await _apiJson('/api/triggers/save', { method: 'POST' });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Saved triggers → ${result.path.split(/[\\/]/).pop()}`);
}

// ── Bulk MIDI Shift modal ─────────────────────────────────────────────────────

function openMidiShiftModal() {
  document.getElementById('trg-shift-modal').style.display = 'flex';
  const st = document.getElementById('trg-shift-status');
  st.textContent = '';
  st.style.color = 'var(--overlay0)';
}

function closeMidiShiftModal() {
  document.getElementById('trg-shift-modal').style.display = 'none';
}

async function submitMidiShift() {
  const fromUni = document.getElementById('trg-shift-from-uni').value.trim();
  const fromCh  = document.getElementById('trg-shift-from-ch').value.trim();
  const toUni   = document.getElementById('trg-shift-to-uni').value.trim();
  const toCh    = document.getElementById('trg-shift-to-ch').value.trim();

  const statusEl = document.getElementById('trg-shift-status');
  statusEl.style.color = 'var(--overlay0)';
  statusEl.textContent = 'Shifting…';

  const result = await _apiJson('/api/triggers/midi-shift', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_uni: fromUni, from_ch: fromCh, to_uni: toUni, to_ch: toCh }),
  });

  if (result.error) {
    statusEl.style.color = 'var(--red)';
    statusEl.textContent = result.error;
    return;
  }

  statusEl.style.color = 'var(--green)';
  statusEl.textContent = `✓ Updated ${result.updated} trigger(s).`;

  if (result.updated > 0) {
    // Reload the triggers table and close modal after a short pause
    _trgLoaded = false;
    await _loadTriggers();
    _trgConflictUids = new Set(); // clear conflict highlights after shift
    _applyTrgFilter();
    setTimeout(() => {
      closeMidiShiftModal();
      setStatus(`MIDI shift applied — ${result.updated} trigger(s) updated.`, 'ok');
    }, 1000);
  }
}

// ── Assignment Matrix ─────────────────────────────────────────────────────────

function toggleMatrix() {
  _trgMatrixVisible = !_trgMatrixVisible;
  const panel = document.getElementById('trg-matrix-panel');
  const btn   = document.getElementById('trg-matrix-btn');
  panel.style.display = _trgMatrixVisible ? 'block' : 'none';
  btn.classList.toggle('btn-view-active', _trgMatrixVisible);
  if (_trgMatrixVisible) _fetchMatrix();
}

async function _fetchMatrix() {
  const wrap = document.getElementById('trg-matrix-wrap');
  wrap.innerHTML = '<div style="padding:12px;color:var(--overlay0);font-size:12px">Loading…</div>';
  const data = await _apiJson('/api/triggers/matrix');
  if (data.error) {
    wrap.innerHTML = `<div style="padding:12px;color:var(--red);font-size:12px">${_te(data.error)}</div>`;
    return;
  }
  _renderMatrix(data);
}

function _renderMatrix(data) {
  const wrap = document.getElementById('trg-matrix-wrap');
  const { keys, widgets } = data;

  if (!keys.length) {
    wrap.innerHTML = '<div style="padding:12px;color:var(--overlay0);font-size:12px">No key assignments found.</div>';
    return;
  }

  // Only show widgets that have a key assignment
  const keySet = new Set(keys);
  const assigned = widgets.filter(w => w.key && keySet.has(w.key));

  if (!assigned.length) {
    wrap.innerHTML = '<div style="padding:12px;color:var(--overlay0);font-size:12px">No widget key assignments found.</div>';
    return;
  }

  // Group by key so we can also show duplicate counts
  const keyCount = {};
  assigned.forEach(w => { keyCount[w.key] = (keyCount[w.key] || 0) + 1; });

  const headerCells = ['<th style="text-align:left;padding:4px 8px;white-space:nowrap">Widget</th>'];
  keys.forEach(k => {
    const isDup = keyCount[k] > 1;
    const style = `padding:4px 6px;text-align:center;white-space:nowrap;font-family:var(--font-mono);font-size:10px${isDup ? ';color:var(--red)' : ''}`;
    const title = isDup ? ` title="${keyCount[k]} widgets share this key"` : '';
    headerCells.push(`<th style="${style}"${title}>${_te(k)}${isDup ? ' ⚠' : ''}</th>`);
  });

  const bodyRows = assigned.map(w => {
    const cells = [
      `<td style="padding:4px 8px;white-space:nowrap;font-size:11px;cursor:pointer"
           onclick="selectTrigger('${w.uid}')">${_badge(w.type)} ${_te(w.caption)}</td>`
    ];
    keys.forEach(k => {
      const match = w.key === k;
      const click = match ? `onclick="selectTrigger('${w.uid}')"` : '';
      const mark  = match
        ? `<span style="color:var(--green);font-size:14px;cursor:pointer" title="Click to edit">✓</span>`
        : '';
      cells.push(`<td style="text-align:center;padding:4px 6px" ${click}>${mark}</td>`);
    });
    return `<tr>${cells.join('')}</tr>`;
  }).join('');

  wrap.innerHTML = `
    <div style="font-size:11px;color:var(--overlay0);margin-bottom:6px;padding:0 4px">
      ${assigned.length} widget(s) · ${keys.length} unique key(s)
      ${Object.values(keyCount).some(c => c > 1) ? ' · <span style="color:var(--red)">⚠ duplicate keys detected</span>' : ''}
    </div>
    <div style="overflow:auto;max-height:320px">
      <table class="custom-table" style="width:auto;min-width:100%">
        <thead><tr>${headerCells.join('')}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>`;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _te(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
