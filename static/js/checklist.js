/* =============================================================================
   checklist.js — Setup Checklist tab (Grid.js read-only fixture table)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _chkData    = [];
let _chkGrid    = null;
let _chkLoaded  = false;

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateChecklist() {
  _chkLoaded = false;
  _chkData   = [];
  if (_chkGrid) { _chkGrid.destroy(); _chkGrid = null; }
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
  _renderChecklistTable(_chkData);
}

// ── Filter ────────────────────────────────────────────────────────────────────

function filterChecklist(q) {
  if (!_chkData.length) return;
  q = (q || '').toLowerCase().trim();
  const filtered = q
    ? _chkData.filter(r =>
        Object.values(r).some(v => String(v ?? '').toLowerCase().includes(q)))
    : _chkData;
  _renderChecklistTable(filtered);
}

// ── Render ────────────────────────────────────────────────────────────────────

const CHK_COLS = [
  { id: 'id',       name: 'ID',        width: '60px'  },
  { id: 'name',     name: 'Name',      width: '30%'   },
  { id: 'universe', name: 'Universe',  width: '80px'  },
  { id: 'address',  name: 'Address',   width: '80px'  },
  { id: 'groups',   name: 'Groups',    width: '25%'   },
  { id: 'pos',      name: '3D Pos',    width: ''      },
];

function _renderChecklistTable(data) {
  const wrap = document.getElementById('chk-table-wrap');
  if (_chkGrid) { _chkGrid.destroy(); _chkGrid = null; }

  _chkGrid = new gridjs.Grid({
    columns: CHK_COLS.map(c => ({
      id:    c.id,
      name:  c.name,
      width: c.width || undefined,
      sort:  true,
    })),
    data:       data.map(r => [r.id, r.name, r.universe, r.address, r.groups, r.pos]),
    sort:       true,
    pagination: { limit: 200, summary: true },
    style: { table: { width: '100%' } },
  }).render(wrap);
}

// ── Export Blueprint PDF ──────────────────────────────────────────────────────

async function exportChecklistPdf() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('No workspace loaded.', 'warn'); return; }
  const showName = prompt('Show name for PDF:', 'My Show') || 'Untitled';
  const paper    = 'A3 Landscape';
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
