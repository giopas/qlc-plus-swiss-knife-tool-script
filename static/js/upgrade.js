/**
 * Upgrade to QLC+ 5.3 (3.2.0).
 *
 * Gives a show made with QLC+ 5.0 to 5.2 what QLC+ 5.3 offers, in the show
 * in progress.  /api/upgrade/analyse says what each step would do; the ticked
 * steps go to /api/upgrade/apply (✓ Apply to the show, a step in the History).
 */

let _up = null;               // analyse() result
let _upSel = new Set();

const _UP_TEXT = {
  folders:   ['Folders for the functions',
              'Every function with no folder gets one, by what it does: Looks per group, Chasers (each with its own steps), Effects per group, Collections, Setlist, Safety for the PANIC RESET. QLC+ shows them as a tree.'],
  palettes:  ['Palettes',
              'Dimmer Full, Half and Off, the Shutter palettes your fixtures can take, and a Color palette for each colour your looks use, named like the QLC+ Show Wizard’s. Your scenes keep their own values.'],
  allgroup:  ['An All Fixtures group',
              'A group with every light, laid out from the stage, when no group holds the whole rig.'],
  grids:     ['Group grids that follow the stage',
              'A group’s grid is what RGB matrices run across. Rows go from the front to the back; a side column becomes its own row. This changes how your matrices run, so it is not ticked by default.'],
  positions: ['Positions on the stage',
              'Position3D palettes for moving heads: the stage centre, the audience and each musician model placed on the stage. QLC+ 5.3 works out pan and tilt for every fixture.'],
  frame:     ['A page per group',
              'A new Virtual Console page with one frame and a page for each group: an intensity slider, the group’s looks (one at a time), its effects, and an XY pad that aims the moving heads at the floor.'],
  hide:      ['Hide the page-switch fixtures',
              'The 1-channel dimmers that switch frame pages are hidden in the 2D and 3D views.'],
  lock:      ['Lock the fixtures in 2D and 3D',
              'Placed fixtures can’t be dragged by mistake.'],
};

function upgradeInit() {
  if (!_up) upgradeAnalyse();
}

function invalidateUpgrade() {
  _up = null; _upSel = new Set();
  const el = document.getElementById('up-steps');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace made with QLC+ 5.</div>';
  _upSync();
  if (document.getElementById('scr-upgrade')?.classList.contains('active')) upgradeAnalyse();
}

function _upTarget() {
  return document.getElementById('up-target')?.value || '5.3';
}

function upgradeTarget(_v) {
  upgradeAnalyse();
}

async function upgradeAnalyse() {
  try {
    const r = await fetch('/api/upgrade/analyse?target=' + encodeURIComponent(_upTarget()));
    const d = await r.json();
    if (!r.ok) { _up = null; _upSync(); return; }
    _up = d;
    _upSel = new Set(d.steps.filter(s => s.count > 0 && d.defaults.includes(s.id) && _upUsable(s)).map(s => s.id));
    _upRender();
  } catch (e) { /* no workspace */ }
}

function _upUsable(s) {
  return !(s.only53 && _up && _up.target !== '5.3');
}

function _upChosen() {
  return _up ? _up.steps.filter(s => _upSel.has(s.id) && s.count > 0 && _upUsable(s)).map(s => s.id) : [];
}

function upgradeTick(id, on) {
  if (on) _upSel.add(id); else _upSel.delete(id);
  _upSync();
}

function _upRender() {
  const el = document.getElementById('up-steps');
  if (!el || !_up) return;
  const top = _up.wizard
    ? `<div class="wz-note" style="grid-column: 1 / -1; margin-left: 0">${_esc('The QLC+ Show Wizard made this show: Wizard Repair finishes it.')}
         <button class="btn btn-surface btn-sm" onclick="go('wizard')">${_esc('Wizard Repair')}</button></div>`
    : '';
  el.innerHTML = top + _up.steps.map(s => {
    const [title, desc] = _UP_TEXT[s.id] || [s.id, ''];
    const off = !_upUsable(s);
    const none = s.count === 0 || off;
    const items = (s.items || []).slice(0, 12).map(x => `<li>${_esc(x)}</li>`).join('')
      + ((s.items || []).length > 12 ? `<li>${_esc(`and ${s.items.length - 12} more`)}</li>` : '');
    const chip = off ? _esc('QLC+ 5.3 only') : (s.count === 0 ? _esc('nothing to do') : s.count);
    const only = s.only53 && !off ? ` <span class="up-only53">${_esc('QLC+ 5.3')}</span>` : '';
    const note = s.note ? `<div class="wz-note">${_esc(s.note)}</div>` : '';
    return `<div class="wz-step${none ? ' wz-none' : ''}">
      <label class="wz-head">
        <input type="checkbox" ${_upSel.has(s.id) && !off ? 'checked' : ''} ${none ? 'disabled' : ''}
               onchange="upgradeTick('${s.id}', this.checked)">
        <span class="wz-title">${_esc(title)}${only}</span>
        <span class="doc-chip${none ? '' : ' doc-warning'}">${chip}</span>
      </label>
      <div class="wz-desc">${_esc(desc)}</div>
      ${items && !off ? `<ul class="wz-items">${items}</ul>` : ''}${note}
    </div>`;
  }).join('');
  _upSync();
}

function _upSync() {
  const s = document.getElementById('up-summary');
  const b = document.getElementById('up-go');
  const chosen = _upChosen();
  if (b) b.disabled = !chosen.length;
  const ver = _up && _up.version ? _esc(`Version in the file: ${_up.version}`) : _esc('No version in the file');
  if (s) s.innerHTML = _up
    ? `<span class="doc-chip">${ver}</span>`
      + ` <span class="doc-chip">${_esc(`${_up.steps.filter(x => x.count > 0 && _upUsable(x)).length} step(s) possible`)}</span>`
    : '';
  if (!chosen.length) { setOutcome('upgrade', ''); return; }
  setOutcome('upgrade', chosen.map(id => (_UP_TEXT[id] || [id])[0]));
}
