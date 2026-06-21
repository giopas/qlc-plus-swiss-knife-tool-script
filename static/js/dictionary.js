/* =============================================================================
   dictionary.js — Dictionary Manager tab
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _dictData       = [];   // [{id, name, type, desc, vc_button}]
let _dictFiltered   = [];
let _dictSort       = { col: 'id', dir: 1 };
let _dictSelFid     = null;
let _dictLoaded     = false;
let _dictTypeFilter   = '';
let _dictVcFilter     = '';   // '' | 'has' | 'none'
let _dictVcNameFilter = '';   // free-text search within VC button name
let _dictFrameFilter  = '';   // exact frame name match

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateDictionary() {
  _dictLoaded  = false;
  _dictData    = [];
  _dictSelFid  = null;
  _renderDictTable([]);
  _resetDictEdit();
}

async function ensureDictionaryLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_dictLoaded) return;
  _dictLoaded = true;
  await _loadDictionary();
}

// ── Data fetch ────────────────────────────────────────────────────────────────

async function _loadDictionary() {
  const data = await _apiJson('/api/dictionary/');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _dictData     = Array.isArray(data) ? data : [];
  _dictFiltered = _dictData;
  _populateTypeFilter();
  _populateFrameFilter();
  _applyDictFilters();
}

// ── Filters ───────────────────────────────────────────────────────────────────

function filterDictionary(q) { _applyDictFilters(q); }

function filterDictByType(type) {
  _dictTypeFilter = type || '';
  _applyDictFilters();
}

function filterDictByVc(val) {
  _dictVcFilter = val || '';
  _applyDictFilters();
}

function filterDictByVcName(val) {
  _dictVcNameFilter = (val || '').trim();
  _applyDictFilters();
}

function filterDictByFrame(val) {
  _dictFrameFilter = val || '';
  _applyDictFilters();
}

function _applyDictFilters(q) {
  if (q === undefined) q = (document.getElementById('dict-filter')?.value || '').trim();
  q = q.toLowerCase().trim();
  let result = _dictData;
  if (_dictTypeFilter)
    result = result.filter(r => (r.type || '') === _dictTypeFilter);
  if (_dictVcFilter === 'has')
    result = result.filter(r => r.vc_button);
  else if (_dictVcFilter === 'none')
    result = result.filter(r => !r.vc_button);
  if (_dictVcNameFilter) {
    const vcq = _dictVcNameFilter.toLowerCase();
    result = result.filter(r => (r.vc_button || '').toLowerCase().includes(vcq));
  }
  if (_dictFrameFilter)
    result = result.filter(r => (r.vc_frames || []).includes(_dictFrameFilter));
  if (q)
    result = result.filter(r =>
      r.id.includes(q) ||
      r.name.toLowerCase().includes(q) ||
      (r.type        || '').toLowerCase().includes(q) ||
      (r.desc        || '').toLowerCase().includes(q) ||
      (r.vc_button   || '').toLowerCase().includes(q) ||
      (r.vc_frames   || []).some(f => f.toLowerCase().includes(q)));
  _dictFiltered = result;
  _renderDictTable(_sortDict(_dictFiltered));
}

function _populateTypeFilter() {
  const sel = document.getElementById('dict-type-filter');
  if (!sel) return;
  const types = [...new Set(_dictData.map(r => r.type || '').filter(Boolean))].sort();
  sel.innerHTML = '<option value="">All types</option>'
    + types.map(t => `<option value="${_de(t)}">${_de(t)}</option>`).join('');
  sel.value = _dictTypeFilter;
}

function _populateFrameFilter() {
  const sel = document.getElementById('dict-frame-filter');
  if (!sel) return;
  const frames = [...new Set(_dictData.flatMap(r => r.vc_frames || []))].sort();
  sel.innerHTML = '<option value="">All frames</option>'
    + frames.map(f => `<option value="${_de(f)}">${_de(f)}</option>`).join('');
  sel.value = _dictFrameFilter;
}

// ── Sort ──────────────────────────────────────────────────────────────────────

function _sortDict(rows) {
  const { col, dir } = _dictSort;
  return [...rows].sort((a, b) => {
    const av = col === 'id' ? parseInt(a[col]) || 0 : (a[col] || '').toLowerCase();
    const bv = col === 'id' ? parseInt(b[col]) || 0 : (b[col] || '').toLowerCase();
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

function _dictSortBy(col) {
  if (_dictSort.col === col) _dictSort.dir *= -1;
  else { _dictSort.col = col; _dictSort.dir = 1; }
  _renderDictTable(_sortDict(_dictFiltered));
}

// ── Render ────────────────────────────────────────────────────────────────────

function _renderDictTable(rows) {
  const wrap = document.getElementById('dict-table-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--overlay0);font-size:12px">'
                   + ((_dictData.length === 0)
                       ? 'Load a workspace to see functions.'
                       : 'No results for current filter.') + '</div>';
    return;
  }

  const cols = [
    { key: 'id',        label: 'ID',         w: '55px'  },
    { key: 'type',      label: 'Type',        w: '90px'  },
    { key: 'name',      label: 'Name',        w: '28%'   },
    { key: 'vc_button', label: 'VC Button',   w: '14%'   },
    { key: 'desc',      label: 'Description', w: ''      },
  ];

  const sortArrow = k =>
    _dictSort.col !== k ? '' : (_dictSort.dir === 1 ? ' ↑' : ' ↓');

  const ths = cols.map(c =>
    `<th onclick="_dictSortBy('${c.key}')"
         style="width:${c.w}"
         class="${_dictSort.col === c.key ? (_dictSort.dir===1?'sort-asc':'sort-desc') : ''}"
     >${c.label}${sortArrow(c.key)}</th>`
  ).join('');

  const trs = rows.map(r => {
    const active = r.id === _dictSelFid ? ' row-active' : '';
    const vcHtml = r.vc_button
      ? `<span class="vc-badge" title="${_de(r.vc_button)}">${_de(r.vc_button.length > 18 ? r.vc_button.substring(0,17)+'…' : r.vc_button)}</span>`
      : `<span class="no-val">—</span>`;
    return `<tr class="${active}" onclick="_selectDictRow('${r.id}')">
      <td style="font-family:var(--font-mono);color:var(--overlay0)">${_de(r.id)}</td>
      <td>${_badge(r.type)}</td>
      <td class="td-wrap">${_de(r.name)}</td>
      <td>${vcHtml}</td>
      <td class="td-wrap">${r.desc
        ? _de(r.desc)
        : '<span class="no-val">—</span>'}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="custom-table">
    <thead><tr>${ths}</tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

// ── Row selection + edit panel ────────────────────────────────────────────────

function _selectDictRow(fid) {
  _dictSelFid = fid;
  const row   = _dictData.find(r => r.id === fid);
  if (!row) return;

  document.querySelectorAll('#dict-table-wrap tr.row-active')
    .forEach(tr => tr.classList.remove('row-active'));
  document.querySelectorAll('#dict-table-wrap tr').forEach(tr => {
    if (tr.querySelector('td')?.textContent.trim() === fid)
      tr.classList.add('row-active');
  });

  document.getElementById('dict-edit-label').textContent =
    `[${row.id}] ${row.name}${row.vc_button ? '  •  VC: ' + row.vc_button : ''}`;
  const ta = document.getElementById('dict-desc-input');
  ta.value    = row.desc || '';
  ta.disabled = false;
  document.getElementById('btn-save-dict-entry').disabled = false;
}

function _resetDictEdit() {
  document.getElementById('dict-edit-label').textContent = 'Select a row to edit its description';
  const ta = document.getElementById('dict-desc-input');
  ta.value    = '';
  ta.disabled = true;
  document.getElementById('btn-save-dict-entry').disabled = true;
}

// ── Save description ──────────────────────────────────────────────────────────

async function saveDictEntry() {
  if (!_dictSelFid) return;
  const desc   = document.getElementById('dict-desc-input').value;
  const result = await _apiJson(`/api/dictionary/${_dictSelFid}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ desc }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  const row = _dictData.find(r => r.id === _dictSelFid);
  if (row) row.desc = desc;
  _renderDictTable(_sortDict(_dictFiltered));
  setStatus(`Description saved for ID ${_dictSelFid}`);
}

// ── Browse TXT file (client-side import) ──────────────────────────────────────

function importDictTxtFile(input) {
  if (!input.files.length) return;
  const file   = input.files[0];
  const reader = new FileReader();
  reader.onload = e => {
    const lines  = e.target.result.split(/\r?\n/);
    let   count  = 0;
    for (const line of lines) {
      const cl = line.trim();
      if (!cl || cl.startsWith('#') || cl.startsWith('ID|')) continue;
      const parts = cl.split('|');
      if (parts.length < 3) continue;
      const fid  = parts[0].trim();
      if (!fid.match(/^\d+$/)) continue;
      // Support both ID|Name|Desc and ID|Name|Type|Desc formats
      const desc = (parts.length >= 4 ? parts.slice(3) : parts.slice(2))
                   .join('|').replace(/\\n/g, '\n').trim();
      const row  = _dictData.find(r => r.id === fid);
      if (row && desc) { row.desc = desc; count++; }
    }
    _applyDictFilters();
    setStatus(`Imported ${count} description(s) from "${file.name}". Click Save on each row or use Save TXT.`, 'ok');
  };
  reader.readAsText(file, 'utf-8');
  input.value = '';
}

// ── Load / Save TXT ───────────────────────────────────────────────────────────

async function loadDictFile() {
  const path = document.getElementById('dict-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiJson('/api/dictionary/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Loaded ${result.count} description(s) from file`);
  await _loadDictionary();
}

async function saveDictFile() {
  const path = document.getElementById('dict-path').value.trim();
  if (!path) { setStatus('Paste a .txt path first.', 'warn'); return; }
  const result = await _apiJson('/api/dictionary/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (result.error) { setStatus(result.error, 'error'); return; }
  setStatus(`Dictionary saved → ${result.path.split(/[\\/]/).pop()}`);
}

// ── Export TXT download ───────────────────────────────────────────────────────

async function exportDictTxt() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('No workspace loaded.', 'warn'); return; }
  try {
    const res = await fetch('/api/dictionary/export-txt', { method: 'POST' });
    if (!res.ok) { setStatus('Export failed.', 'error'); return; }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename=([^\s;]+)/);
    const name = m ? m[1] : 'dictionary.txt';
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`Exported ${_dictData.length} entries → ${name}`);
  } catch (e) {
    setStatus('Export error: ' + e.message, 'error');
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _de(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
