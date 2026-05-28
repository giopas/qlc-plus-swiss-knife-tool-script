/* =============================================================================
   triggers.js — Trigger Manager tab
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _trgData     = [];    // raw list from server
let _trgFiltered = [];    // current filtered/sorted view
let _trgSort     = { col: 'caption', dir: 1 };
let _trgSelUid   = null;  // selected trigger uid
let _trgLoaded   = false;

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateTriggers() {
  _trgLoaded   = false;
  _trgData     = [];
  _trgSelUid   = null;
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
    const active  = r.uid === _trgSelUid ? ' row-active' : '';
    const dot     = r.has
      ? '<span class="dot-yes" title="Has trigger">●</span>'
      : '<span class="dot-no"  title="No trigger">●</span>';
    const keyCell  = r.key  ? `<span class="key-cell">${_te(r.key)}</span>`  : '<span class="no-val">—</span>';
    const uniCell  = r.uni  ? `<span class="midi-cell">${_te(r.uni)}</span>` : '<span class="no-val">—</span>';
    const chCell   = r.ch   ? `<span class="midi-cell">${_te(r.ch)}</span>`  : '<span class="no-val">—</span>';
    return `<tr class="${active}" onclick="selectTrigger('${r.uid}')">
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

// ── Duplicates ────────────────────────────────────────────────────────────────

async function checkDuplicates() {
  const data = await _apiJson('/api/triggers/duplicates');
  if (data.error) { setStatus(data.error, 'error'); return; }
  const keys = Object.keys(data);
  if (!keys.length) {
    setStatus('No duplicate key bindings found ✓', 'ok');
  } else {
    const summary = keys.map(k => `${k}: ${data[k].join(', ')}`).join(' | ');
    setStatus(`Duplicates found — ${summary}`, 'warn');
    console.warn('[Triggers] Duplicate key bindings:', data);
  }
}

// ── Save to QXW ──────────────────────────────────────────────────────────────

async function saveTriggers() {
  const result = await _apiJson('/api/triggers/save', { method: 'POST' });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Saved triggers → ${result.path.split(/[\\/]/).pop()}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _te(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
