/**
 * Wizard Repair (3.1.0).
 *
 * Finishes a show made by the QLC+ 5.3 Show Wizard, in the show in progress.
 * /api/wizard/analyse says what each step would do; the ticked steps go to
 * /api/wizard/repair (✓ Apply to the show, a step in the History).
 */

let _wz = null;               // analyse() result
let _wzSel = new Set();

const _WZ_TEXT = {
  chasers:  ['Effects the wizard lost',
             'QLC+ 5.3.0 builds the step scenes of Color Rainbow, Split Color and Strobe Chase but not the chaser. The chaser is built from them, with the timing the wizard meant.'],
  palettes: ['Palettes that do nothing on some fixtures',
             'A Shutter palette asks for one exact strobe preset, a Color palette sets colour mixing only. Fixtures that can’t take them get the values that do the same: their own strobe range, the nearest slot of their colour wheel.'],
  panic:    ['PANIC RESET on every page',
             'The wizard gives only Blackout, which leaves effects running. A PANIC RESET script stops everything and puts every fixture at rest, with a red button next to Blackout on each page of the wizard’s frame.'],
  buttons:  ['Buttons for what is off the console',
             'RGB matrices, musician positions, Audience Sweep, Dimmer Full and Half, Blinder Hit and the rebuilt effects get buttons on their group’s page, in rows, where there is room.'],
  grids:    ['Group grids that follow the stage',
             'A group’s grid is what RGB matrices run across. Rows go from the front to the back; a side column becomes its own row, so a chase runs the same way on both sides.'],
  hide:     ['Hide the page-switch fixtures',
             'The 1-channel dimmers that switch the frame’s pages are hidden in the 2D and 3D views.'],
  lock:     ['Lock the fixtures in 2D and 3D',
             'Placed fixtures can’t be dragged by mistake (QLC+ 5.3; QLC+ 5.2.2 ignores it).'],
  captions: ['Captions on the gobo buttons',
             'The gobo picture buttons get the gobo’s name, for lists and the web interface. The name is drawn over the picture.'],
};

function wizardInit() {
  if (!_wz) wizardAnalyse();
}

function invalidateWizard() {
  _wz = null; _wzSel = new Set();
  const el = document.getElementById('wz-steps');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace made with the QLC+ Show Wizard.</div>';
  _wzSync();
  if (document.getElementById('scr-wizard')?.classList.contains('active')) wizardAnalyse();
}

async function wizardAnalyse() {
  try {
    const r = await fetch('/api/wizard/analyse');
    const d = await r.json();
    if (!r.ok) { _wz = null; _wzSync(); return; }
    _wz = d;
    _wzSel = new Set(d.steps.filter(s => s.count > 0 && d.defaults.includes(s.id)).map(s => s.id));
    _wzRender();
  } catch (e) { /* no workspace */ }
}

function _wzChosen() {
  return _wz ? _wz.steps.filter(s => _wzSel.has(s.id) && s.count > 0).map(s => s.id) : [];
}

function wizardTick(id, on) {
  if (on) _wzSel.add(id); else _wzSel.delete(id);
  _wzSync();
}

function _wzRender() {
  const el = document.getElementById('wz-steps');
  if (!el || !_wz) return;
  if (!_wz.wizard) {
    el.innerHTML = '<div class="porter-placeholder">This show was not made with the QLC+ Show Wizard: there is nothing for this tool to repair. The Workspace Doctor checks it.</div>';
    _wzSync();
    return;
  }
  el.innerHTML = _wz.steps.map(s => {
    const [title, desc] = _WZ_TEXT[s.id] || [s.id, ''];
    const none = s.count === 0;
    const items = (s.items || []).slice(0, 12).map(x => `<li>${_esc(x)}</li>`).join('')
      + ((s.items || []).length > 12 ? `<li>${_esc(`and ${s.items.length - 12} more`)}</li>` : '');
    const nopage = (s.no_page || []).length
      ? `<div class="wz-note">${_esc('No page in the wizard’s frame for: ' + s.no_page.join(', '))}</div>` : '';
    return `<div class="wz-step${none ? ' wz-none' : ''}">
      <label class="wz-head">
        <input type="checkbox" ${_wzSel.has(s.id) ? 'checked' : ''} ${none ? 'disabled' : ''}
               onchange="wizardTick('${s.id}', this.checked)">
        <span class="wz-title">${_esc(title)}</span>
        <span class="doc-chip${none ? '' : ' doc-warning'}">${none ? _esc('nothing to do') : s.count}</span>
      </label>
      <div class="wz-desc">${_esc(desc)}</div>
      ${items ? `<ul class="wz-items">${items}</ul>` : ''}${nopage}
    </div>`;
  }).join('');
  _wzSync();
}

function _wzSync() {
  const s = document.getElementById('wz-summary');
  const b = document.getElementById('wz-go');
  const chosen = _wzChosen();
  if (b) b.disabled = !chosen.length;
  if (s) s.innerHTML = _wz && _wz.wizard
    ? `<span class="doc-chip">${_esc(`${_wz.steps.filter(x => x.count > 0).length} repair(s) possible`)}</span>`
    : '';
  if (!chosen.length) { setOutcome('wizard', ''); return; }
  setOutcome('wizard', chosen.map(id => (_WZ_TEXT[id] || [id])[0]));
}
