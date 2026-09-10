/* =============================================================================
   showbook.js — Show Book frontend
   =============================================================================
   Section-selectable preview + PDF / CSV export.
   ============================================================================= */

'use strict';

let _sbLoaded   = false;   // true after first successful preview
let _sbDoc      = null;    // last document model from /api/showbook/preview
let _sbBusy     = false;

const _SB_SECTIONS = [
  { id: 'summary',     label: 'Summary',       icon: '📊' },
  { id: 'patch',       label: 'Patch List',     icon: '🔌' },
  { id: 'functions',   label: 'Function Index', icon: '📋' },
  { id: 'scenes',      label: 'Scenes',         icon: '🎬' },
  { id: 'chasers',     label: 'Chasers',        icon: '🔄' },
  { id: 'collections', label: 'Collections',    icon: '📦' },
  { id: 'efx',         label: 'EFX',            icon: '✨' },
  { id: 'shows',       label: 'Shows',          icon: '🎭' },
  { id: 'scripts',     label: 'Scripts',        icon: '📝' },
  { id: 'vc_layout',   label: 'VC Layout',      icon: '🖼' },
];

// ── Init ────────────────────────────────────────────────────────────────────

function showbookInit() {
  _sbBuildSectionPicker();
}

function invalidateShowbook() {
  _sbLoaded = false;
  _sbDoc = null;
  const preview = document.getElementById('sb-preview');
  if (preview) preview.innerHTML = '<div class="porter-placeholder">Generate a preview to see your Show Book here.</div>';
}

// ── Section picker ──────────────────────────────────────────────────────────

function _sbBuildSectionPicker() {
  const wrap = document.getElementById('sb-section-checks');
  if (!wrap || wrap.childElementCount > 0) return;

  wrap.innerHTML = _SB_SECTIONS.map(s =>
    `<label class="sb-check-label">
       <input type="checkbox" value="${s.id}" checked>
       <span>${s.icon} ${s.label}</span>
     </label>`
  ).join('');
}

function _sbSelectedSections() {
  const checks = document.querySelectorAll('#sb-section-checks input[type=checkbox]:checked');
  return Array.from(checks).map(c => c.value);
}

function sbSelectAll() {
  document.querySelectorAll('#sb-section-checks input[type=checkbox]')
    .forEach(c => c.checked = true);
}

function sbSelectNone() {
  document.querySelectorAll('#sb-section-checks input[type=checkbox]')
    .forEach(c => c.checked = false);
}

// ── QXF directory ───────────────────────────────────────────────────────────

async function sbBrowseQxf() {
  const path = await nativePick(
    'Select QXF fixture definition folder',
    [],   // directory pick — no file filter
    ''
  );
  if (path) {
    const inp = document.getElementById('sb-qxf-path');
    if (inp) inp.value = path;
    // Track in session
    if (typeof _sess !== 'undefined') {
      _sess.showbook_qxf_dir = path;
      if (typeof _markDirty === 'function') _markDirty();
    }
  }
}

// ── Generate preview ────────────────────────────────────────────────────────

async function sbGenerate() {
  if (_sbBusy) return;

  const sections = _sbSelectedSections();
  if (!sections.length) {
    _sbStatus('Select at least one section.', 'error');
    return;
  }

  const qxfDir = (document.getElementById('sb-qxf-path')?.value || '').trim();

  _sbBusy = true;
  _sbStatus('Generating preview…');

  try {
    const res = await fetch('/api/showbook/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sections,
        qxf_dir: qxfDir || null,
      }),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      _sbStatus(data.error || 'Preview failed.', 'error');
      return;
    }

    _sbDoc = data.document;
    _sbLoaded = true;
    _sbRenderPreview(_sbDoc);
    _sbStatus('Preview ready — scroll down to review, then export.');
  } catch (e) {
    _sbStatus('Network error: ' + e.message, 'error');
  } finally {
    _sbBusy = false;
  }
}

// ── Render preview ──────────────────────────────────────────────────────────

function _sbRenderPreview(doc) {
  const wrap = document.getElementById('sb-preview');
  if (!wrap) return;

  const parts = [];
  const secs = doc.sections || {};

  // Summary
  if (secs.summary) {
    const s = secs.summary;
    parts.push(`<div class="sb-section" id="sb-sec-summary">
      <h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📊 Summary <span class="sb-toggle-icon">▾</span></h3>
      <div class="sb-section-body">
      <div class="sb-stats">
        <span><b>Fixtures:</b> ${s.fixture_count}</span>
        <span><b>Functions:</b> ${s.function_count}</span>
        <span><b>VC Widgets:</b> ${s.vc_widget_count}</span>
        <span><b>Universes:</b> ${s.universe_count}</span>
      </div>
      <div class="sb-type-breakdown">${
        Object.entries(s.function_types || {}).sort()
          .map(([t, c]) => `<span class="sb-type-chip">${t}: ${c}</span>`).join('')
      }</div>
      </div>
    </div>`);
  }

  // Patch
  if (secs.patch) {
    parts.push(_sbTable('🔌 Patch List', secs.patch,
      ['ID', 'Name', 'Model', 'Mode', 'Patch', 'Groups'],
      p => [p.id, p.name, p.model, p.mode, p.patch, p.groups],
      'sb-sec-patch'));
  }

  // Function Index (clickable rows)
  if (secs.functions) {
    parts.push(_sbFunctionIndex(secs.functions));
  }

  // Scenes
  if (secs.scenes) {
    parts.push(_sbScenes(secs.scenes));
  }

  // Chasers
  if (secs.chasers) {
    parts.push(_sbChasers(secs.chasers));
  }

  // Collections
  if (secs.collections) {
    parts.push(_sbCollections(secs.collections));
  }

  // EFX
  if (secs.efx) {
    parts.push(_sbEfx(secs.efx));
  }

  // Shows
  if (secs.shows) {
    parts.push(_sbShows(secs.shows));
  }

  // Scripts
  if (secs.scripts) {
    parts.push(_sbScripts(secs.scripts));
  }

  // VC Layout
  if (secs.vc_layout) {
    parts.push(_sbTable('🖼 VC Layout', secs.vc_layout,
      ['ID', 'Type', 'Caption', 'Func ID', 'Function', 'Frame'],
      w => [w.id, w.type, w.caption, w.function_id, w.function_name, w.frame],
      'sb-sec-vclayout'));
  }

  wrap.innerHTML = parts.join('') || '<div class="porter-placeholder">No sections to display.</div>';
}

// ── Collapse / expand helpers ──────────────────────────────────────────────

function sbToggleSection(h3) {
  const body = h3.nextElementSibling;
  if (!body) return;
  const icon = h3.querySelector('.sb-toggle-icon');
  if (body.classList.contains('sb-collapsed')) {
    body.classList.remove('sb-collapsed');
    if (icon) icon.textContent = '▾';
  } else {
    body.classList.add('sb-collapsed');
    if (icon) icon.textContent = '▸';
  }
}

function sbToggleItem(el) {
  const detail = el.nextElementSibling;
  if (!detail || !detail.classList.contains('sb-item-body')) return;
  const icon = el.querySelector('.sb-toggle-icon');
  if (detail.classList.contains('sb-collapsed')) {
    detail.classList.remove('sb-collapsed');
    if (icon) icon.textContent = '▾';
  } else {
    detail.classList.add('sb-collapsed');
    if (icon) icon.textContent = '▸';
  }
}

function sbExpandAll() {
  document.querySelectorAll('#sb-preview .sb-collapsed').forEach(el => el.classList.remove('sb-collapsed'));
  document.querySelectorAll('#sb-preview .sb-toggle-icon').forEach(el => el.textContent = '▾');
}

function sbCollapseAll() {
  document.querySelectorAll('#sb-preview .sb-section-body, #sb-preview .sb-item-body').forEach(el => el.classList.add('sb-collapsed'));
  document.querySelectorAll('#sb-preview .sb-toggle-icon').forEach(el => el.textContent = '▸');
}

// ── Navigate from Function Index to detail ─────────────────────────────────

function _sbScrollToFunc(id, type) {
  // Map function type to section anchor prefix
  const prefix = {
    'Scene': 'sb-scene-',
    'Chaser': 'sb-chaser-',
    'Collection': 'sb-col-',
    'EFX': 'sb-efx-',
    'Show': 'sb-show-',
    'Script': 'sb-script-',
  }[type];
  if (!prefix) return;

  const target = document.getElementById(prefix + id);
  if (!target) return;

  // Expand the parent section if collapsed
  const section = target.closest('.sb-section');
  if (section) {
    const body = section.querySelector('.sb-section-body');
    if (body && body.classList.contains('sb-collapsed')) {
      body.classList.remove('sb-collapsed');
      const icon = section.querySelector('h3 .sb-toggle-icon');
      if (icon) icon.textContent = '▾';
    }
  }
  // Expand the item itself if collapsed
  const itemBody = target.nextElementSibling;
  if (itemBody && itemBody.classList.contains('sb-item-body') && itemBody.classList.contains('sb-collapsed')) {
    itemBody.classList.remove('sb-collapsed');
    const icon = target.querySelector('.sb-toggle-icon');
    if (icon) icon.textContent = '▾';
  }

  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  // Brief highlight
  target.classList.add('sb-highlight');
  setTimeout(() => target.classList.remove('sb-highlight'), 1500);
}

// ── Preview render helpers ──────────────────────────────────────────────────

function _sbTable(title, rows, headers, cellsFn, sectionId) {
  if (!rows.length) return `<div class="sb-section"${sectionId ? ` id="${sectionId}"` : ''}><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">${title} <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No items.</div></div></div>`;

  const maxRows = 100;
  const shown = rows.slice(0, maxRows);
  const truncNote = rows.length > maxRows
    ? `<div class="sb-trunc">Showing ${maxRows} of ${rows.length} — full data in export.</div>` : '';

  return `<div class="sb-section"${sectionId ? ` id="${sectionId}"` : ''}>
    <h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">${title} <span class="sb-toggle-icon">▾</span></h3>
    <div class="sb-section-body">
    <div class="sb-table-wrap"><table class="sb-table">
      <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
      <tbody>${shown.map(r => {
        const cells = cellsFn(r);
        return `<tr>${cells.map(c => `<td>${_esc(c)}</td>`).join('')}</tr>`;
      }).join('')}</tbody>
    </table></div>${truncNote}
    </div>
  </div>`;
}

function _sbFunctionIndex(funcs) {
  if (!funcs.length) return `<div class="sb-section" id="sb-sec-functions"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📋 Function Index <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No items.</div></div></div>`;

  const maxRows = 100;
  const shown = funcs.slice(0, maxRows);
  const truncNote = funcs.length > maxRows
    ? `<div class="sb-trunc">Showing ${maxRows} of ${funcs.length} — full data in export.</div>` : '';

  // Clickable types — those that have a detail section
  const clickable = new Set(['Scene', 'Chaser', 'Collection', 'EFX', 'Show', 'Script']);

  return `<div class="sb-section" id="sb-sec-functions">
    <h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📋 Function Index <span class="sb-toggle-icon">▾</span></h3>
    <div class="sb-section-body">
    <div class="sb-table-wrap"><table class="sb-table">
      <thead><tr><th>ID</th><th>Name</th><th>Type</th><th>Description</th></tr></thead>
      <tbody>${shown.map(f => {
        const isLink = clickable.has(f.type);
        const cls = isLink ? ' class="sb-fn-link"' : '';
        const click = isLink ? ` onclick="_sbScrollToFunc(${_esc(f.id)}, '${_esc(f.type)}')"` : '';
        return `<tr${cls}${click}><td>${_esc(f.id)}</td><td>${_esc(f.name)}</td><td>${_esc(f.type)}</td><td>${_esc(f.description)}</td></tr>`;
      }).join('')}</tbody>
    </table></div>${truncNote}
    </div>
  </div>`;
}

function _sbScenes(scenes) {
  if (!scenes.length) return '<div class="sb-section" id="sb-sec-scenes"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🎬 Scenes <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No scenes.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-scenes"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🎬 Scene Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  const maxScenes = 50;
  const shown = scenes.slice(0, maxScenes);

  for (const scene of shown) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-scene-${_esc(scene.id)}" onclick="sbToggleItem(this)">Scene #${_esc(scene.id)}: ${_esc(scene.name)}${scene.description ? `<span class="sb-meta">${_esc(scene.description)}</span>` : ''} <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    for (const fx of (scene.fixtures || [])) {
      parts.push(`<div class="sb-fixture-label">${_esc(fx.fixture_name)} (${_esc(fx.fixture_model)})</div>`);
      if (fx.channels && fx.channels.length) {
        parts.push('<div class="sb-table-wrap"><table class="sb-table sb-table-sm">');
        parts.push('<thead><tr><th>Ch#</th><th>Channel</th><th>Raw</th><th>Decoded</th></tr></thead><tbody>');
        for (const ch of fx.channels) {
          parts.push(`<tr><td>${ch.channel_index}</td><td>${_esc(ch.channel_name)}</td><td>${ch.raw_value}</td><td>${_esc(ch.decoded)}</td></tr>`);
        }
        parts.push('</tbody></table></div>');
      }
    }
    parts.push('</div>');
  }
  if (scenes.length > maxScenes) {
    parts.push(`<div class="sb-trunc">Showing ${maxScenes} of ${scenes.length} scenes — full data in export.</div>`);
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _sbChasers(chasers) {
  if (!chasers.length) return '<div class="sb-section" id="sb-sec-chasers"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🔄 Chasers <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No chasers.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-chasers"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🔄 Chaser Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  for (const ch of chasers) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-chaser-${_esc(ch.id)}" onclick="sbToggleItem(this)">Chaser #${_esc(ch.id)}: ${_esc(ch.name)}
      <span class="sb-meta">[${_esc(ch.direction)} / ${_esc(ch.run_order)}]</span>${ch.description ? `<span class="sb-meta">— ${_esc(ch.description)}</span>` : ''} <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    if (ch.steps && ch.steps.length) {
      parts.push('<div class="sb-table-wrap"><table class="sb-table sb-table-sm">');
      parts.push('<thead><tr><th>Step</th><th>Function</th><th>Fade In</th><th>Hold</th><th>Fade Out</th><th>Duration</th></tr></thead><tbody>');
      for (const st of ch.steps) {
        parts.push(`<tr><td>${_esc(st.number)}</td><td>${_esc(st.function_name)}</td><td>${_esc(st.fade_in)}</td><td>${_esc(st.hold)}</td><td>${_esc(st.fade_out)}</td><td>${_esc(st.duration)}</td></tr>`);
      }
      parts.push('</tbody></table></div>');
    }
    parts.push('</div>');
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _sbCollections(collections) {
  if (!collections.length) return '<div class="sb-section" id="sb-sec-collections"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📦 Collections <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No collections.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-collections"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📦 Collection Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  for (const c of collections) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-col-${_esc(c.id)}" onclick="sbToggleItem(this)">Collection #${_esc(c.id)}: ${_esc(c.name)}${c.description ? `<span class="sb-meta">— ${_esc(c.description)}</span>` : ''} <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    if (c.members && c.members.length) {
      parts.push('<div class="sb-table-wrap"><table class="sb-table sb-table-sm">');
      parts.push('<thead><tr><th>#</th><th>Function ID</th><th>Function Name</th></tr></thead><tbody>');
      c.members.forEach((m, i) => {
        parts.push(`<tr><td>${i + 1}</td><td>${_esc(m.function_id)}</td><td>${_esc(m.function_name)}</td></tr>`);
      });
      parts.push('</tbody></table></div>');
    }
    parts.push('</div>');
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _sbEfx(efxList) {
  if (!efxList.length) return '<div class="sb-section" id="sb-sec-efx"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">✨ EFX <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No EFX functions.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-efx"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">✨ EFX Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  for (const e of efxList) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-efx-${_esc(e.id)}" onclick="sbToggleItem(this)">EFX #${_esc(e.id)}: ${_esc(e.name)}
      <span class="sb-meta">[${_esc(e.algorithm)}]</span> <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    if (e.fixtures && e.fixtures.length) {
      parts.push('<div class="sb-table-wrap"><table class="sb-table sb-table-sm">');
      parts.push('<thead><tr><th>Fixture ID</th><th>Fixture Name</th></tr></thead><tbody>');
      for (const fx of e.fixtures) {
        parts.push(`<tr><td>${_esc(fx.fixture_id)}</td><td>${_esc(fx.fixture_name)}</td></tr>`);
      }
      parts.push('</tbody></table></div>');
    }
    parts.push('</div>');
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _sbShows(shows) {
  if (!shows.length) return '<div class="sb-section" id="sb-sec-shows"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🎭 Shows <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No show functions.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-shows"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🎭 Show Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  for (const s of shows) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-show-${_esc(s.id)}" onclick="sbToggleItem(this)">Show #${_esc(s.id)}: ${_esc(s.name)} <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    for (const t of (s.tracks || [])) {
      parts.push(`<div class="sb-fixture-label">Track: ${_esc(t.name)}${t.scene_name ? ' (Scene: ' + _esc(t.scene_name) + ')' : ''}</div>`);
      if (t.show_functions && t.show_functions.length) {
        parts.push('<div class="sb-table-wrap"><table class="sb-table sb-table-sm">');
        parts.push('<thead><tr><th>Function</th><th>Start</th><th>Duration</th></tr></thead><tbody>');
        for (const sf of t.show_functions) {
          parts.push(`<tr><td>${_esc(sf.function_name)}</td><td>${_esc(sf.start_time)}</td><td>${_esc(sf.duration)}</td></tr>`);
        }
        parts.push('</tbody></table></div>');
      }
    }
    parts.push('</div>');
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _sbScripts(scripts) {
  if (!scripts.length) return '<div class="sb-section" id="sb-sec-scripts"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📝 Scripts <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body"><div class="sb-empty">No scripts.</div></div></div>';

  const parts = ['<div class="sb-section" id="sb-sec-scripts"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📝 Script Details <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">'];
  for (const s of scripts) {
    parts.push(`<div class="sb-sub-heading sb-item-toggle" id="sb-script-${_esc(s.id)}" onclick="sbToggleItem(this)">Script #${_esc(s.id)}: ${_esc(s.name)} <span class="sb-toggle-icon">▾</span></div>`);
    parts.push('<div class="sb-item-body">');
    if (s.commands && s.commands.length) {
      parts.push(`<div class="sb-script-cmds">${s.commands.map(c => `<code>${_esc(c)}</code>`).join('<br>')}</div>`);
    }
    parts.push('</div>');
  }
  parts.push('</div></div>');
  return parts.join('');
}

function _esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Export ───────────────────────────────────────────────────────────────────

async function sbExportPdf() {
  if (_sbBusy) return;
  _sbBusy = true;
  _sbStatus('Generating PDF…');

  try {
    const sections = _sbSelectedSections();
    const qxfDir = (document.getElementById('sb-qxf-path')?.value || '').trim();
    const base = typeof getShowfileBase === 'function' ? getShowfileBase() : 'showbook';

    const res = await fetch('/api/showbook/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sections,
        qxf_dir: qxfDir || null,
        filename: `${base}_ShowBook.pdf`,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      _sbStatus(err.error || 'PDF export failed.', 'error');
      return;
    }

    const blob = await res.blob();
    const fname = res.headers.get('X-Suggested-Filename') || `${base}_ShowBook.pdf`;
    const saved = await saveFileWithPicker(blob, fname,
      [{ description: 'PDF', accept: { 'application/pdf': ['.pdf'] } }],
      'Save Show Book PDF');
    if (saved) _sbStatus(`Saved: ${saved}`);
    else _sbStatus('Export cancelled.');
  } catch (e) {
    _sbStatus('Export error: ' + e.message, 'error');
  } finally {
    _sbBusy = false;
  }
}

async function sbExportCsv() {
  if (_sbBusy) return;
  _sbBusy = true;
  _sbStatus('Generating CSV archive…');

  try {
    const sections = _sbSelectedSections();
    const qxfDir = (document.getElementById('sb-qxf-path')?.value || '').trim();
    const base = typeof getShowfileBase === 'function' ? getShowfileBase() : 'showbook';

    const res = await fetch('/api/showbook/export/csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sections,
        qxf_dir: qxfDir || null,
        filename: `${base}_ShowBook.zip`,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      _sbStatus(err.error || 'CSV export failed.', 'error');
      return;
    }

    const blob = await res.blob();
    const fname = res.headers.get('X-Suggested-Filename') || `${base}_ShowBook.zip`;
    const saved = await saveFileWithPicker(blob, fname,
      [{ description: 'ZIP Archive', accept: { 'application/zip': ['.zip'] } }],
      'Save Show Book CSV');
    if (saved) _sbStatus(`Saved: ${saved}`);
    else _sbStatus('Export cancelled.');
  } catch (e) {
    _sbStatus('Export error: ' + e.message, 'error');
  } finally {
    _sbBusy = false;
  }
}

// ── Status ──────────────────────────────────────────────────────────────────

function _sbStatus(msg, level) {
  const el = document.getElementById('sb-status');
  if (!el) return;
  el.textContent = msg;
  el.className = 'status-bar ' + (level === 'error' ? 'status-error' : level === 'warn' ? 'status-warn' : 'status-info');
}
