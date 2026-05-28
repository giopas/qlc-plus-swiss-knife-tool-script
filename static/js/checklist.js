/* =============================================================================
   checklist.js — Setup Checklist tab (vanilla table with color dots)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _chkData    = [];
let _chkLoaded  = false;
let _chkSort    = { col: 'universe_addr', dir: 1 };

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateChecklist() {
  _chkLoaded = false;
  _chkData   = [];
  _renderChecklistTable([]);
}

async function ensureChecklistLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_chkLoaded) return;
  _chkLoaded = true;
  await _loadChecklist();
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function _loadChecklist() {
  const data = await _apiJson('/api/checklist/fixtures');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _chkData = Array.isArray(data) ? data : [];
  _renderChecklistTable(_applyChkSort(_chkData));
}

// ── Filter ────────────────────────────────────────────────────────────────────

function filterChecklist(q) {
  if (!_chkData.length) return;
  q = (q || '').toLowerCase().trim();
  const filtered = q
    ? _chkData.filter(r =>
        ['id','name','model','patch','groups','mode'].some(
          k => String(r[k] ?? '').toLowerCase().includes(q)))
    : _chkData;
  _renderChecklistTable(_applyChkSort(filtered));
}

// ── Sort ──────────────────────────────────────────────────────────────────────

function _applyChkSort(rows) {
  const { col, dir } = _chkSort;
  return [...rows].sort((a, b) => {
    let av, bv;
    if (col === 'id' || col === 'universe_addr') {
      av = (a.universe || 0) * 1000 + (a.address || 0);
      bv = (b.universe || 0) * 1000 + (b.address || 0);
    } else {
      av = String(a[col] ?? '').toLowerCase();
      bv = String(b[col] ?? '').toLowerCase();
    }
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

function _chkSortBy(col) {
  if (_chkSort.col === col) _chkSort.dir *= -1;
  else { _chkSort.col = col; _chkSort.dir = 1; }
  const q = document.getElementById('chk-filter')?.value || '';
  filterChecklist(q);
}

// ── Render ────────────────────────────────────────────────────────────────────

function _esc2(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

const _CHK_COLS = [
  { key: 'color',        label: '',          w: '32px',  sort: false },
  { key: 'id',          label: 'ID',         w: '50px',  sort: 'universe_addr' },
  { key: 'name',        label: 'Name',       w: '22%',   sort: 'name' },
  { key: 'model',       label: 'Model',      w: '20%',   sort: 'model' },
  { key: 'mode',        label: 'Mode',       w: '10%',   sort: 'mode' },
  { key: 'patch',       label: 'Patch',      w: '80px',  sort: 'universe_addr' },
  { key: 'groups',      label: 'Groups',     w: '16%',   sort: 'groups' },
  { key: 'pos',         label: '3D Pos',     w: '',      sort: false },
];

function _renderChecklistTable(data) {
  const wrap = document.getElementById('chk-table-wrap');
  if (!wrap) return;

  if (!data.length) {
    wrap.innerHTML = `<div style="padding:24px;color:var(--overlay0);font-size:12px">${
      _chkData.length === 0 ? 'Load a workspace to see fixtures.' : 'No results.'
    }</div>`;
    return;
  }

  const arrow = k => {
    const sortKey = _CHK_COLS.find(c => c.key === k)?.sort || k;
    if (_chkSort.col !== sortKey) return '';
    return _chkSort.dir === 1 ? ' ↑' : ' ↓';
  };

  const ths = _CHK_COLS.map(c => {
    const sortKey = c.sort;
    const cls = sortKey && _chkSort.col === sortKey ? (_chkSort.dir===1?'sort-asc':'sort-desc') : '';
    const click = sortKey ? `onclick="_chkSortBy('${sortKey}')"` : '';
    return `<th ${click} style="width:${c.w}" class="${cls}">${_esc2(c.label)}${arrow(c.key)}</th>`;
  }).join('');

  const trs = data.map(r => {
    const color  = r.color || '#888';
    const inThreeD = r.in_3d ? `title="${_esc2(r.pos)}"` : '';
    const posCell = r.in_3d
      ? `<span style="color:var(--teal)">${_esc2(r.pos)}</span>`
      : `<span style="color:var(--overlay0)">—</span>`;
    return `<tr>
      <td style="text-align:center">
        <span class="fix-color-dot" style="background:${color}" title="${_esc2(r.model||'')}"></span>
      </td>
      <td style="font-family:var(--font-mono);color:var(--overlay0)">${_esc2(r.id)}</td>
      <td class="td-wrap">${_esc2(r.name)}</td>
      <td class="td-wrap" style="color:var(--subtext0)">${_esc2(r.model||'')}</td>
      <td style="color:var(--subtext0);font-size:11px">${_esc2(r.mode||'')}</td>
      <td style="font-family:var(--font-mono)">${_esc2(r.patch||`U${r.universe}.${String(r.address).padStart(3,'0')}`)}</td>
      <td class="td-wrap" style="color:var(--subtext0)">${_esc2(r.groups||'—')}</td>
      <td ${inThreeD}>${posCell}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="custom-table">
    <thead><tr>${ths}</tr></thead>
    <tbody>${trs}</tbody>
  </table>`;
}

// ── Export Blueprint PDF ──────────────────────────────────────────────────────

async function exportChecklistPdf() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('No workspace loaded.', 'warn'); return; }
  const showName = prompt('Show name for PDF:', 'My Show') || 'Untitled';
  const paperSel = document.getElementById('chk-pdf-paper');
  const paper    = paperSel?.value || 'A3 Landscape';
  try {
    const res = await fetch('/api/checklist/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_name: showName, paper }),
    });
    if (!res.ok) {
      const e = await res.json();
      setStatus(e.error || 'Export failed.', 'error'); return;
    }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename=([^\s;]+)/);
    const name = m ? m[1] : 'blueprint.pdf';
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`Blueprint PDF downloaded → ${name}`);
  } catch (e) {
    setStatus('Export error: ' + e.message, 'error');
  }
}

// ── Export TXT ────────────────────────────────────────────────────────────────

async function exportChecklistTxt() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('No workspace loaded.', 'warn'); return; }
  try {
    const res  = await fetch('/api/checklist/export-txt', { method: 'POST' });
    if (!res.ok) { setStatus('Export failed.', 'error'); return; }
    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = 'checklist.txt';
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`Exported ${_chkData.length} fixtures → checklist.txt`);
  } catch (e) {
    setStatus('Export error: ' + e.message, 'error');
  }
}
