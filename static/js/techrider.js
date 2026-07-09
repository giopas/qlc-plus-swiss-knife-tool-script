/* =============================================================================
   techrider.js — Tech Rider tab (fixture type summary table)
   ============================================================================= */

'use strict';

// ── Module state ──────────────────────────────────────────────────────────────
let _trData   = null;
let _trLoaded = false;

// ── HTML escape ───────────────────────────────────────────────────────────────
function _escTr(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Public API ────────────────────────────────────────────────────────────────

function invalidateTechRider() {
  _trLoaded = false;
  _trData   = null;
  const wrap = document.getElementById('tr-table-wrap');
  if (wrap) wrap.innerHTML = '';
}

async function ensureTechRiderLoaded() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) return;
  if (_trLoaded) return;
  _trLoaded = true;
  await _loadTechRider();
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function _loadTechRider() {
  const data = await _apiJson('/api/techrider/summary');
  if (data.error) { setStatus(data.error, 'error'); return; }
  _trData = data;
  _renderTechRider(data);
}

// ── Render ────────────────────────────────────────────────────────────────────

function _renderTechRider(data) {
  const wrap = document.getElementById('tr-table-wrap');
  if (!wrap) return;

  if (!data || !data.types || !data.types.length) {
    wrap.innerHTML = `<div style="padding:24px;color:var(--overlay0);font-size:12px">
      Load a workspace to see the tech rider.
    </div>`;
    return;
  }

  const types = data.types;

  const ths = `<th>Type</th><th>Model</th><th>Mode</th><th style="text-align:right">Qty</th>
    <th>Patch Range</th><th>Universe(s)</th>`;

  const trs = types.map(t => {
    const uni = t.universes.join(', ');
    const colorDot = t.color
      ? `<span class="fix-color-dot" style="background:${t.color};margin-right:6px" title="${_escTr(t.manufacturer)}"></span>`
      : '';
    return `<tr>
      <td class="td-wrap">${colorDot}${_escTr(t.manufacturer)}</td>
      <td class="td-wrap" style="color:var(--subtext0)">${_escTr(t.model)}</td>
      <td style="color:var(--subtext0);font-size:11px">${_escTr(t.mode)}</td>
      <td style="text-align:right;font-family:var(--font-mono)">${t.quantity}</td>
      <td style="font-family:var(--font-mono)">${_escTr(t.patch_range)}</td>
      <td style="font-family:var(--font-mono)">${_escTr(uni)}</td>
    </tr>`;
  }).join('');

  // Totals row
  const totalQty = types.reduce((s, t) => s + t.quantity, 0);
  const allUni   = [...new Set(types.flatMap(t => t.universes))].sort((a,b) => a - b).join(', ');
  const totalRow = `<tr style="font-weight:600;border-top:2px solid var(--overlay0)">
    <td colspan="3" style="text-align:right;color:var(--subtext0)">Total</td>
    <td style="text-align:right;font-family:var(--font-mono)">${totalQty}</td>
    <td></td>
    <td style="font-family:var(--font-mono)">${_escTr(allUni)}</td>
  </tr>`;

  wrap.innerHTML = `<table class="custom-table">
    <thead><tr>${ths}</tr></thead>
    <tbody>${trs}${totalRow}</tbody>
  </table>
  <div style="padding:8px 12px;font-size:11px;color:var(--overlay0)">
    ${data.total_groups} fixture type(s) &middot; ${data.total_fixtures} fixture(s) &middot;
    ${data.universes_used.length} universe(s)
  </div>`;
}

// ── Export PDF ────────────────────────────────────────────────────────────────

async function exportTechRiderPdf() {
  const state = await _apiJson('/api/status');
  if (!state.loaded) { setStatus('No workspace loaded.', 'warn'); return; }
  const showName  = typeof getShowName === 'function' ? getShowName() : 'Untitled Show';
  const eventDate = typeof getEventDate === 'function' ? getEventDate() : '';
  const paperSel  = document.getElementById('tr-pdf-paper');
  const paper     = paperSel?.value || 'A3 Landscape';
  try {
    const res = await fetch('/api/techrider/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_name: showName, doc_date: eventDate, paper }),
    });
    if (!res.ok) {
      const e = await res.json();
      setStatus(e.error || 'Export failed.', 'error'); return;
    }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename=([^\s;]+)/);
    const base = typeof getShowfileBase === 'function' ? getShowfileBase() : 'TechRider';
    const name = m ? m[1] : `${base}_TechRider.pdf`;
    const savedName = await saveFileWithPicker(blob, name, null, 'Save tech rider PDF as');
    if (!savedName) return;
    setStatus(`Tech Rider PDF downloaded → ${savedName}`);
  } catch (e) {
    setStatus('Export error: ' + e.message, 'error');
  }
}
