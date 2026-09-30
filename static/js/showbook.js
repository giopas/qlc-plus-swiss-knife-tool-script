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
  { id: 'rider',       label: 'Tech rider (fixture types)', icon: '🎟' },
  { id: 'stage_plan',  label: 'Stage plot',     icon: '🗺' },
  { id: 'checklist',   label: 'Load-in checklist', icon: '✅' },
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
  { id: 'doctor',      label: 'Doctor summary', icon: '🩺' },
];

// ── Init ────────────────────────────────────────────────────────────────────

// Presets by reader (Show Paperwork, 1.9) — mirror of core/showbook.PRESETS
const _SB_PRESETS = {
  rider:     ['rider', 'stage_plan'],
  checklist: ['checklist', 'stage_plan'],
  operator:  ['summary', 'patch', 'functions', 'scenes', 'chasers', 'collections', 'efx',
              'shows', 'scripts', 'vc_layout', 'doctor'],
};
const _SB_VENUE_SAFE = new Set(['rider', 'stage_plan', 'checklist', 'patch']);
let _sbPresets = new Set(['operator']);

function showbookInit() {
  _sbBuildSectionPicker();
  _sbApplyPresets();
}

function _sbVenueOnly() {
  return _sbPresets.size > 0 && [..._sbPresets].every(p => p === 'rider' || p === 'checklist');
}

/** Pick who the paper is for; ⇧-click adds / removes a preset. */
function sbPreset(p, ev) {
  if (p === 'custom') _sbPresets = new Set();
  else if (ev && ev.shiftKey) { _sbPresets.has(p) ? _sbPresets.delete(p) : _sbPresets.add(p); }
  else _sbPresets = new Set([p]);
  _sbBuildSectionPicker();
  _sbApplyPresets();
  invalidateShowbook();
}

function _sbApplyPresets() {
  document.querySelectorAll('.sb-preset').forEach(b =>
    b.classList.toggle('active', b.dataset.p === 'custom' ? _sbPresets.size === 0 : _sbPresets.has(b.dataset.p)));
  const venue = _sbVenueOnly();
  const want = new Set([..._sbPresets].flatMap(p => _SB_PRESETS[p] || []));
  document.querySelectorAll('#sb-section-checks input[type=checkbox]').forEach(c => {
    if (_sbPresets.size) c.checked = want.has(c.value);
    c.disabled = venue && !_SB_VENUE_SAFE.has(c.value);
    c.closest('label')?.classList.toggle('sb-locked', c.disabled);
  });
  const note = document.getElementById('sb-venue-note');
  if (note) note.hidden = !venue;
}

function _sbBody(extra) {
  return Object.assign({
    sections: _sbSelectedSections(),
    presets: [..._sbPresets],
    qxf_dir: (document.getElementById('sb-qxf-path')?.value || '').trim() || null,
    show_name: typeof getShowName === 'function' ? (getShowName() || null) : null,
    date: typeof getEventDate === 'function' ? (getEventDate() || null) : null,
    paper: document.getElementById('sb-paper')?.value || 'A4 Landscape',
  }, extra || {});
}

function invalidateShowbook() {
  _sbLoaded = false;
  _sbDoc = null;
  const preview = document.getElementById('sb-preview');
  if (preview) preview.innerHTML = '<div class="porter-placeholder">Pick who it is for, then 🔍 Generate Preview.</div>';
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
  const path = await nativePick('Select QXF fixture definition folder', [], '', true);
  if (path) {
    const inp = document.getElementById('sb-qxf-path');
    if (inp) inp.value = path;
    setFileChip('sb-qxf-name', path, 'no folder chosen');
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
      body: JSON.stringify(_sbBody()),
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

  if (secs.rider) {
    const r = secs.rider;
    parts.push(_sbTable('🎟 Tech rider — fixture types', r.types,
      ['Manufacturer', 'Model', 'Mode', 'Qty', 'Ch', 'Patch range', 'Universe(s)'],
      t => [t.manufacturer, t.model, t.mode, t.quantity, t.channels || '', t.patch_range, t.universes.join(', ')],
      'sb-sec-rider').replace('</table>', `</table><div class="sb-stats"><span><b>Total:</b> ${r.total_fixtures} fixture(s),
        ${r.total_channels} DMX channel(s), ${r.universes.length} universe(s)</span></div>`));
  }
  if (secs.checklist) {
    parts.push(_sbTable('✅ Load-in checklist', secs.checklist,
      ['☐', 'ID', 'Name', 'Model', 'Mode', 'Patch', 'Groups', '3D position'],
      c => ['☐', c.id, c.name, c.model, c.mode, c.patch, c.groups, c.position], 'sb-sec-checklist'));
  }
  if (secs.stage_plan) {
    const sp = secs.stage_plan;
    parts.push(`<div class="sb-section" id="sb-sec-stage"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🗺 Stage plot <span class="sb-toggle-icon">▾</span></h3>
      <div class="sb-section-body"><div class="sb-stats"><span>${sp.placed} of ${sp.fixtures.length} fixture(s) have a 3D position —
      the PDF draws them from above and from the front, on a page of its own.</span></div>
      ${sp.placed < sp.fixtures.length ? '<div class="sb-optional">Fixtures without a position are left out: place them in <a href="#" onclick="go(\'stage\');return false">Stage &amp; Meshes</a>.</div>' : ''}</div></div>`);
  }

  // Summary
  if (secs.summary) {
    const s = secs.summary;
    parts.push(`<div class="sb-section" id="sb-sec-summary">
      <h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">📊 Summary <span class="sb-toggle-icon">▾</span></h3>
      <div class="sb-section-body">
      <div class="sb-stats">
        <span><b>Fixtures:</b> ${s.fixture_count}</span>
        <span><b>Functions:</b> ${s.function_count}</span>
        <span><b>VC Widgets:</b> ${s.vc_widget_count} on ${s.vc_page_count || 0} page(s)</span>
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
  if (secs.vc_layout) parts.push(_sbVcLayout(secs.vc_layout));

  // Doctor
  if (secs.doctor) parts.push(_sbDoctor(secs.doctor));

  wrap.innerHTML = parts.join('') || '<div class="porter-placeholder">No sections to display.</div>';
}

// VC layout: one table per page, frames indented (WORKPLAN 1.3)
function _sbVcLayout(layout) {
  const pages = layout.pages || [];
  const head = '<div class="sb-section" id="sb-sec-vclayout"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🖼 VC Layout <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">';
  if (!pages.length) return head + '<div class="sb-empty">No Virtual Console.</div></div></div>';
  const body = pages.map(pg => `
    <h4 class="sb-subhead">📄 ${_esc(pg.caption)} <small>${_esc(pg.size)}${pg.size ? ' px · ' : ''}${pg.widgets.length} widget(s)</small></h4>
    <div class="sb-table-wrap"><table class="sb-table">
      <thead><tr><th>ID</th><th>Type</th><th>Caption</th><th>Position / size</th><th>Function</th><th>Key / MIDI</th></tr></thead>
      <tbody>${pg.widgets.map(w => `<tr>
        <td>${_esc(w.id)}</td><td>${_esc(w.type)}</td>
        <td style="padding-left:${0.4 + w.depth * 1.1}rem">${w.type === 'Frame' || w.type === 'SoloFrame' ? '▣ ' : ''}${_esc(w.caption)}</td>
        <td>${w.w ? _esc(w.x + ',' + w.y + '  ' + w.w + '×' + w.h) : ''}</td>
        <td>${_esc((w.function_id ? w.function_id + ' ' : '') + (w.function_name || ''))}</td>
        <td>${_esc(w.bindings)}</td></tr>`).join('')}</tbody>
    </table></div>`).join('');
  return head + body + '</div></div>';
}

function _sbDoctor(d) {
  const head = '<div class="sb-section" id="sb-sec-doctor"><h3 class="sb-collapse-toggle" onclick="sbToggleSection(this)">🩺 Workspace Doctor <span class="sb-toggle-icon">▾</span></h3><div class="sb-section-body">';
  const line = `<div class="sb-stats"><span><b>Errors:</b> ${d.errors}</span><span><b>Warnings:</b> ${d.warnings}</span><span><b>Info:</b> ${d.info}</span></div>`;
  if (!d.findings.length) return head + line + '<div class="sb-empty">No errors or warnings.</div></div></div>';
  return head + line + `<div class="sb-table-wrap"><table class="sb-table">
    <thead><tr><th>Code</th><th>Severity</th><th>Location</th><th>Message</th></tr></thead>
    <tbody>${d.findings.map(f => `<tr><td>${_esc(f.code)}</td><td>${_esc(f.severity)}</td><td>${_esc(f.location)}</td><td>${_esc(f.message)}</td></tr>`).join('')}</tbody>
    </table></div></div></div>`;
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
    const base = typeof getShowfileBase === 'function' ? getShowfileBase() : 'showbook';
    const res = await fetch('/api/showbook/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_sbBody()),
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
      'Save the PDF');
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
    const base = typeof getShowfileBase === 'function' ? getShowfileBase() : 'showbook';
    const res = await fetch('/api/showbook/export/csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_sbBody()),
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
      'Save the CSV archive');
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
