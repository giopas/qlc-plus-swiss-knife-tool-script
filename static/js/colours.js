// =============================================================================
// Copy Colours (3.23.0): one fixture takes the colours another shows, in every
// look of the show in progress. The colour is translated when the two are
// different types (RGB, RGBW, a colour wheel); the fixture keeps its own
// brightness unless asked otherwise.
// =============================================================================

let _ccFx = null;                 // the show's fixtures (from /api/colours/fixtures)
let _ccRows = [{ target: '', source: '' }];
let _ccTimer = null, _ccSeq = 0;

function coloursInit() {
  if (!_ccFx) _ccLoad();
}

function invalidateColours() {
  _ccFx = null; _ccRows = [{ target: '', source: '' }];
  const el = document.getElementById('cc-rows');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace to list its fixtures.</div>';
  const p = document.getElementById('cc-preview');
  if (p) p.innerHTML = '';
  setOutcome('colours', '');
  const b = document.getElementById('cc-go'); if (b) b.disabled = true;
  if (document.getElementById('scr-colours')?.classList.contains('active')) _ccLoad();
}

async function _ccLoad() {
  try {
    const r = await fetch('/api/colours/fixtures');
    const d = await r.json();
    if (!r.ok) return;
    _ccFx = d.fixtures;
    _ccRender();
  } catch (e) { /* no workspace */ }
}

function _ccLabel(f) {
  return `${f.name} · ${f.model}` + (f.known ? '' : ` (${t('no .qxf')})`);
}

function _ccOptions(selected, exclude, colourOnly) {
  const opts = [`<option value="">${t('Choose a fixture…')}</option>`];
  for (const f of _ccFx) {
    if (f.id === exclude) continue;
    const ok = f.known && f.colour;
    opts.push(`<option value="${_esc(f.id)}" ${f.id === selected ? 'selected' : ''} ${!ok && colourOnly ? 'disabled' : ''}>${_esc(_ccLabel(f))}</option>`);
  }
  return opts.join('');
}

function _ccRender() {
  const el = document.getElementById('cc-rows');
  if (!el || !_ccFx) return;
  if (!_ccFx.length) { el.innerHTML = '<div class="porter-placeholder">This show has no fixtures.</div>'; return; }
  el.innerHTML = _ccRows.map((r, i) => `
    <div class="cc-row">
      <select class="filter-input cc-sel" aria-label="${t('Fixture that changes')}" onchange="coloursSet(${i}, 'target', this.value)">${_ccOptions(r.target, r.source, true)}</select>
      <span class="cc-takes">${t('takes the colours of')}</span>
      <select class="filter-input cc-sel" aria-label="${t('Fixture it copies')}" onchange="coloursSet(${i}, 'source', this.value)">${_ccOptions(r.source, r.target, true)}</select>
      <button class="btn btn-surface btn-sm btn-ghost" onclick="coloursRemove(${i})" title="${t('Remove this line')}" aria-label="${t('Remove this line')}" ${_ccRows.length < 2 ? 'disabled' : ''}>✕</button>
    </div>`).join('');
  _ccAuto();
}

function coloursSet(i, field, value) {
  _ccRows[i][field] = value;
  _ccRender();
}

function coloursAdd() {
  _ccRows.push({ target: '', source: '' });
  _ccRender();
}

function coloursRemove(i) {
  _ccRows.splice(i, 1);
  if (!_ccRows.length) _ccRows.push({ target: '', source: '' });
  _ccRender();
}

function _ccPlan() {
  const seen = new Set();
  const pairs = _ccRows.filter(r => r.target && r.source && r.target !== r.source && !seen.has(r.target) && seen.add(r.target))
    .map(r => ({ target: r.target, source: r.source }));
  const brightness = document.querySelector('input[name="cc-bright"]:checked')?.value || 'keep';
  const add = !!document.getElementById('cc-add')?.checked;
  return { pairs, brightness, add };
}

function coloursOptionsChanged() { _ccAuto(); }

function _ccAuto() {
  clearTimeout(_ccTimer);
  const b = document.getElementById('cc-go');
  const plan = _ccPlan();
  const dup = _ccRows.filter(r => r.target).length !== new Set(_ccRows.filter(r => r.target).map(r => r.target)).size;
  if (!plan.pairs.length) {
    if (b) b.disabled = true;
    document.getElementById('cc-preview').innerHTML =
      '<div class="porter-placeholder">Choose the fixture that changes and the fixture whose colours it takes: what Apply will do shows here.</div>';
    setOutcome('colours', 'nothing yet — choose two fixtures', '', 'Apply will do');
    return;
  }
  if (dup) setStatus('A fixture is chosen twice on the left: only its first line counts.', 'warn');
  setOutcome('colours', 'working it out…', '', 'Apply will');
  _ccTimer = setTimeout(() => coloursPreview(true), 300);
}

async function coloursPreview(auto) {
  const el = document.getElementById('cc-preview');
  const b = document.getElementById('cc-go');
  const seq = ++_ccSeq;
  try {
    const r = await fetch('/api/colours/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(_ccPlan()),
    });
    const d = await r.json();
    if (seq !== _ccSeq) return;
    if (!r.ok) { setOutcome('colours', d.error || 'no preview', 'error', ''); if (b) b.disabled = true; return; }
    const newBad = d.doctor.new_errors.length;
    el.innerHTML = `<h3 class="rr-h">${t('What Apply will do')}</h3>
      ${d.blocked ? '<div class="rr-block">The result has new Doctor errors — Apply is refused until they are gone.</div>' : ''}
      <ul class="cc-lines">${d.lines.map(x => `<li>${_esc(x)}</li>`).join('')}</ul>`;
    const chips = [];
    chips.push(d.total ? skPlural(d.total, '{0} look changes', '{0} looks change') : t('nothing to change'));
    chips.push(newBad ? { text: t('{0} new Doctor error(s)', newBad), kind: 'error' } : { text: '✓ no new Doctor errors', kind: 'ok' });
    setOutcome('colours', chips, newBad ? 'error' : '');
    if (b) b.disabled = !d.total || d.blocked;
    if (!auto) setStatus('Preview ready.', 'ok');
  } catch (e) {
    setStatus('Network error: ' + e.message, 'error');
  }
}

async function coloursApply() {
  const d = await showApply('/api/colours/apply', _ccPlan(), 'Copying the colours…');
  if (d) coloursPreview(true);
}
