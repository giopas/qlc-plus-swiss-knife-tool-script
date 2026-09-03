/* =========================================================================
   static/js/quickstart.js — Quick Start QXW Wizard
   =========================================================================
   5-step wizard: Fixtures → Placement → Analysis → VC Preview → Export
   Calls /api/quickstart/* endpoints (quick_start_routes.py)
   ========================================================================= */

let _qsLoaded = false;
function ensureQuickStartLoaded() {
  if (_qsLoaded) return;
  _qsLoaded = true;
  qsRefreshStatus();
}

/* ── state ─────────────────────────────────────────────────────────────── */
let _qsStep = 1;
const _qsTotalSteps = 5;

/* ── helpers ────────────────────────────────────────────────────────────── */
function _qsApi(method, path, body) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  return fetch('/api/quickstart' + path, opts).then(r => r.json());
}

function _qsShow(id) {
  document.querySelectorAll('.qs-step').forEach(el => el.style.display = 'none');
  const el = document.getElementById(id);
  if (el) el.style.display = '';
}

function _qsUpdateNav() {
  const back = document.getElementById('qs-btn-back');
  const next = document.getElementById('qs-btn-next');
  const exp  = document.getElementById('qs-btn-export');

  if (back) back.style.display = _qsStep > 1 ? '' : 'none';
  if (next) next.style.display = _qsStep < _qsTotalSteps ? '' : 'none';
  if (exp)  exp.style.display  = _qsStep === _qsTotalSteps ? '' : 'none';

  // Update step indicator
  const ind = document.getElementById('qs-step-indicator');
  if (ind) ind.textContent = `Step ${_qsStep} of ${_qsTotalSteps}`;

  // Update step labels
  for (let i = 1; i <= _qsTotalSteps; i++) {
    const dot = document.getElementById('qs-dot-' + i);
    if (!dot) continue;
    dot.classList.toggle('qs-dot-active', i === _qsStep);
    dot.classList.toggle('qs-dot-done', i < _qsStep);
  }
}

/* ── navigation ─────────────────────────────────────────────────────────── */
function qsGoStep(n) {
  _qsStep = Math.max(1, Math.min(_qsTotalSteps, n));
  _qsShow('qs-step-' + _qsStep);
  _qsUpdateNav();

  // auto-actions on step entry
  if (_qsStep === 2) qsRefreshRigTable();
  if (_qsStep === 3) qsRunAnalysis();
  if (_qsStep === 4) qsLoadPreview();
  if (_qsStep === 5) qsLoadSummary();
}

function qsNext() { qsGoStep(_qsStep + 1); }
function qsBack() { qsGoStep(_qsStep - 1); }

/* ── Step 1: Fixture Selection ─────────────────────────────────────────── */
function qsRefreshStatus() {
  _qsApi('GET', '/status').then(d => {
    if (d.rig && d.rig.length > 0) _qsRenderRigTable(d.rig);
  }).catch(() => {});
}

function qsLoadQxf() {
  const path = document.getElementById('qs-qxf-path').value.trim();
  if (!path) return;
  _qsApi('POST', '/load-qxf', { path })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      const info = document.getElementById('qs-qxf-info');
      if (info) {
        info.textContent = `✓ Loaded: ${d.manufacturer || ''} ${d.model || ''} — ${d.channels || '?'} ch`;
        info.style.color = 'var(--green)';
      }
    })
    .catch(e => alert('Failed to load QXF: ' + e));
}

function qsUploadQxf() {
  const inp = document.getElementById('qs-qxf-upload');
  if (!inp || !inp.files.length) return;
  const fd = new FormData();
  fd.append('file', inp.files[0]);
  fetch('/api/quickstart/upload-qxf', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(d => {
      if (d.error) { alert(d.error); return; }
      const info = document.getElementById('qs-qxf-info');
      if (info) {
        info.textContent = `✓ Uploaded: ${d.manufacturer || ''} ${d.model || ''} — ${d.channels || '?'} ch`;
        info.style.color = 'var(--green)';
      }
    })
    .catch(e => alert('Upload failed: ' + e));
}

function qsAddFixture() {
  const name = document.getElementById('qs-fix-name').value.trim() || 'Fixture';
  const qty  = parseInt(document.getElementById('qs-fix-qty').value) || 1;
  _qsApi('POST', '/add-fixture', { name, quantity: qty })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsRenderRigTable(d.rig);
    })
    .catch(e => alert('Add failed: ' + e));
}

function qsRemoveFixture(idx) {
  _qsApi('POST', '/remove-fixture', { index: idx })
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsRenderRigTable(d.rig);
    })
    .catch(e => alert('Remove failed: ' + e));
}

function qsClearRig() {
  _qsApi('POST', '/clear')
    .then(d => _qsRenderRigTable(d.rig || []))
    .catch(e => alert('Clear failed: ' + e));
}

function _qsRenderRigTable(rig) {
  const wrap = document.getElementById('qs-rig-table');
  if (!wrap) return;
  if (!rig || rig.length === 0) {
    wrap.innerHTML = '<div class="qs-empty">No fixtures added yet. Load a QXF and add fixtures above.</div>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>#</th><th>Name</th><th>Channels</th><th>Universe</th><th>Address</th><th></th></tr></thead><tbody>';
  rig.forEach((f, i) => {
    html += `<tr>
      <td>${i + 1}</td>
      <td>${f.name || '—'}</td>
      <td>${f.channels || '—'}</td>
      <td>${f.universe != null ? f.universe + 1 : '—'}</td>
      <td>${f.address != null ? f.address + 1 : '—'}</td>
      <td><button class="btn btn-danger btn-sm" onclick="qsRemoveFixture(${i})">✕</button></td>
    </tr>`;
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

/* ── Step 2: Stage Placement ───────────────────────────────────────────── */
function qsRefreshRigTable() {
  _qsApi('GET', '/status').then(d => {
    if (d.rig) _qsRenderPlacementTable(d.rig);
  });
}

function _qsRenderPlacementTable(rig) {
  const wrap = document.getElementById('qs-placement-table');
  if (!wrap) return;
  if (!rig || rig.length === 0) {
    wrap.innerHTML = '<div class="qs-empty">No fixtures in rig. Go back to Step 1.</div>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>#</th><th>Name</th><th>X (mm)</th><th>Z (mm)</th><th>Y (mm)</th></tr></thead><tbody>';
  rig.forEach((f, i) => {
    html += `<tr>
      <td>${i + 1}</td>
      <td>${f.name || '—'}</td>
      <td><input type="number" class="filter-input" style="width:70px" value="${f.x || 0}" onchange="qsUpdatePos(${i},'x',this.value)"></td>
      <td><input type="number" class="filter-input" style="width:70px" value="${f.z || 0}" onchange="qsUpdatePos(${i},'z',this.value)"></td>
      <td><input type="number" class="filter-input" style="width:70px" value="${f.y || 0}" onchange="qsUpdatePos(${i},'y',this.value)"></td>
    </tr>`;
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

function qsUpdatePos(idx, axis, val) {
  const body = { index: idx };
  body[axis] = parseInt(val) || 0;
  _qsApi('POST', '/update-placement', body).catch(() => {});
}

function qsAutoDmx() {
  _qsApi('POST', '/auto-dmx')
    .then(d => {
      if (d.error) { alert(d.error); return; }
      _qsRenderPlacementTable(d.rig);
      const info = document.getElementById('qs-dmx-info');
      if (info) {
        info.textContent = `✓ Auto-assigned ${d.rig.length} fixtures across ${d.universes || 1} universe(s)`;
        info.style.color = 'var(--green)';
      }
    })
    .catch(e => alert('Auto-DMX failed: ' + e));
}

/* ── Step 3: Capability Analysis ───────────────────────────────────────── */
function qsRunAnalysis() {
  const wrap = document.getElementById('qs-analysis-result');
  if (wrap) wrap.innerHTML = '<div class="qs-loading">Analyzing fixture capabilities…</div>';
  _qsApi('GET', '/analyse')
    .then(d => {
      if (d.error) { wrap.innerHTML = `<div class="qs-error">${d.error}</div>`; return; }
      let html = '<div class="qs-analysis">';
      html += '<h4>Fixture Groups</h4>';
      const groups = d.groups || {};
      for (const [key, indices] of Object.entries(groups)) {
        const label = { moving_heads: 'Moving Heads', color_fixtures: 'Color Fixtures', dimmers_only: 'Dimmers', other: 'Other' }[key] || key;
        html += `<div class="qs-group-row"><span class="qs-group-label">${label}</span> <span class="qs-group-count">${indices.length} fixture(s)</span></div>`;
      }
      html += '<h4>Capabilities Detected</h4><ul>';
      if (d.has_any_rgb) html += '<li>RGB colour mixing</li>';
      if (d.has_any_strobe) html += '<li>Strobe / flash</li>';
      if (d.has_any_dimmer) html += '<li>Dimmer / intensity</li>';
      if (d.has_any_pan_tilt) html += '<li>Pan / tilt (moving heads)</li>';
      html += '</ul></div>';
      if (wrap) wrap.innerHTML = html;
    })
    .catch(e => { if (wrap) wrap.innerHTML = `<div class="qs-error">Analysis failed: ${e}</div>`; });
}

/* ── Step 4: VC Preview ────────────────────────────────────────────────── */
function qsLoadPreview() {
  const wrap = document.getElementById('qs-vc-preview');
  if (wrap) wrap.innerHTML = '<div class="qs-loading">Generating VC layout preview…</div>';
  _qsApi('GET', '/preview')
    .then(d => {
      if (d.error) { wrap.innerHTML = `<div class="qs-error">${d.error}</div>`; return; }
      let html = '<div class="qs-preview">';
      html += _qsRenderVcTree(d.vc_tree || d);
      html += '</div>';
      if (wrap) wrap.innerHTML = html;
    })
    .catch(e => { if (wrap) wrap.innerHTML = `<div class="qs-error">Preview failed: ${e}</div>`; });
}

function _qsRenderVcTree(node) {
  if (!node) return '';
  let html = '';
  if (node.type === 'frame') {
    html += `<div class="qs-vc-frame"><div class="qs-vc-frame-title">${node.name || 'Frame'}</div>`;
    if (node.children) node.children.forEach(c => html += _qsRenderVcTree(c));
    html += '</div>';
  } else if (node.type === 'button') {
    const cls = node.function_type === 'Chaser' ? 'qs-vc-btn-chaser' : 'qs-vc-btn-scene';
    html += `<div class="qs-vc-btn ${cls}">${node.name || 'Button'}</div>`;
  } else if (Array.isArray(node)) {
    node.forEach(c => html += _qsRenderVcTree(c));
  } else if (node.frames) {
    node.frames.forEach(c => html += _qsRenderVcTree(c));
  }
  return html;
}

/* ── Step 5: Summary & Export ──────────────────────────────────────────── */
function qsLoadSummary() {
  _qsApi('GET', '/status').then(d => {
    const wrap = document.getElementById('qs-summary');
    if (!wrap) return;
    const rig = d.rig || [];
    const total_ch = rig.reduce((s, f) => s + (f.channels || 0), 0);
    let html = '<div class="qs-summary-box">';
    html += '<h4>✓ Ready to Export</h4>';
    html += `<p><b>Fixtures:</b> ${rig.length} total (${total_ch} DMX channels)</p>`;
    html += '</div>';
    wrap.innerHTML = html;
  });
}

function qsExport() {
  const btn = document.getElementById('qs-btn-export');
  if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }

  fetch('/api/quickstart/generate', { method: 'POST' })
    .then(r => {
      if (!r.ok) return r.json().then(d => { throw new Error(d.error || 'Export failed'); });
      return r.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'quick_start.qxw';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Export .qxw'; }
    })
    .catch(e => {
      alert('Export failed: ' + e.message);
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Export .qxw'; }
    });
}
