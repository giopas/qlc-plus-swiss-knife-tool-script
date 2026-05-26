/* =============================================================================
   fixture.js — Fixture Configurator tab (read-only workspace fixture view)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _fixData    = [];
let _fixGrid    = null;
let _fixLoaded  = false;

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateFixtures() {
  _fixLoaded = false;
  _fixData   = [];
  if (_fixGrid) { _fixGrid.destroy(); _fixGrid = null; }
}

async function ensureFixturesLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_fixLoaded) return;
  _fixLoaded = true;
  await _loadFixtures();
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function _loadFixtures() {
  const data = await _apiJson('/api/fixture/rig');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _fixData = Array.isArray(data) ? data : [];
  _renderFixtureTable(_fixData);
}

// ── Filter ────────────────────────────────────────────────────────────────────

function filterFixtures(q) {
  if (!_fixData.length) return;
  q = (q || '').toLowerCase().trim();
  const filtered = q
    ? _fixData.filter(r =>
        Object.values(r).some(v => String(v ?? '').toLowerCase().includes(q)))
    : _fixData;
  _renderFixtureTable(filtered);
}

// ── Render ────────────────────────────────────────────────────────────────────

const FIX_COLS = [
  { id: 'id',       name: 'ID',        width: '60px'  },
  { id: 'name',     name: 'Name',      width: '30%'   },
  { id: 'universe', name: 'Universe',  width: '80px'  },
  { id: 'address',  name: 'Address',   width: '80px'  },
  { id: 'groups',   name: 'Groups',    width: '25%'   },
  { id: 'pos',      name: '3D Pos',    width: ''      },
];

function _renderFixtureTable(data) {
  const wrap = document.getElementById('fix-table-wrap');
  if (_fixGrid) { _fixGrid.destroy(); _fixGrid = null; }

  _fixGrid = new gridjs.Grid({
    columns: FIX_COLS.map(c => ({
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
