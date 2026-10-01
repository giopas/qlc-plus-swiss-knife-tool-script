// =============================================================================
// Guided routes (WORKPLAN 2.6): a strip of steps above the tools for a job
// that takes several tools — e.g. adapt a show to a new venue.  Any step, any
// order; a step is ticked when its tool changed the show, or by hand.
// The strip only guides: every tool still works on the show in progress.
// =============================================================================

const ROUTES = {
  adapt: {
    title: 'Adapt a show to a new venue',
    steps: [
      { tool: 'reducer',  label: 'Keep the rig',  hint: 'Rig Reducer — keep the fixtures the venue has, re-patch' },
      { tool: 'doctor',   label: 'Clean up',      hint: 'Workspace Doctor — fix what the old show carries' },
      { tool: 'porter',   label: 'Bring functions', hint: 'Function Porter — looks, chasers, fixtures or groups from another show (skip if not needed)' },
      { tool: 'stage',    label: 'Groups', tab: 'groups', hint: 'Stage & Meshes › Groups — the fixture groups the looks are built on' },
      { tool: 'looks',    label: 'Looks',         hint: 'Look Builder — looks and chasers for the new groups' },
      { tool: 'vceditor', label: 'Console',       hint: 'VC Visual Editor — pages, buttons, the setlist CueList' },
      { tool: 'stage',    label: 'Stage',         hint: 'Stage & Meshes — the venue stage, band and set pieces' },
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — tonight’s songs into the CueList' },
      { tool: 'doctor',   label: 'Final check',   hint: 'Workspace Doctor — nothing left to fix, then 💾 Save as new file…' },
    ],
  },
  gig: {
    title: 'Get ready for the gig',
    steps: [
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — tonight’s songs into the CueList' },
      { tool: 'triggers', label: 'Keys & MIDI',   hint: 'Trigger Manager — no clashes, every button reachable' },
      { tool: 'doctor',   label: 'Check',         hint: 'Workspace Doctor — nothing left to fix, then 💾 Save as new file…' },
      { tool: 'showbook', label: 'Paperwork',     hint: 'Show Paperwork — tech rider for the venue, crew checklist' },
    ],
  },
};

const _ROUTE_KEY = 'sk.route';
let _route = null;          // { id, done: [bool…] }

function _routeLoad() {
  try { const r = JSON.parse(localStorage.getItem(_ROUTE_KEY) || 'null'); if (r && ROUTES[r.id]) _route = r; }
  catch { _route = null; }
}
function _routeSave() {
  try {
    if (_route) localStorage.setItem(_ROUTE_KEY, JSON.stringify(_route));
    else localStorage.removeItem(_ROUTE_KEY);
  } catch { /* per-browser convenience only */ }
}

/** Start a route (from the Start card) and open its first step. */
function routeStart(id) {
  if (!ROUTES[id]) return;
  _route = { id, done: ROUTES[id].steps.map(() => false), seen: {} };
  _routeSave();
  routeRender();
  go(ROUTES[id].steps[0].tool);
}

function routeClose() {
  _route = null;
  _routeSave();
  routeRender();
}

function routeGo(i) {
  if (!_route) return;
  _route.cur = i;
  _routeSave();
  const s = ROUTES[_route.id].steps[i];
  go(s.tool);
  if (s.tab && s.tool === 'stage' && typeof stageTab === 'function') {
    stageTab(s.tab);
    setTimeout(() => stageTab(s.tab), 400);     // after the screen has loaded its state
  }
}

function routeToggle(i, ev) {
  if (ev) ev.stopPropagation();
  if (!_route) return;
  _route.done[i] = !_route.done[i];
  _routeSave();
  routeRender();
}

/** The step on screen: the one last clicked if it is this tool, else the
 *  first step of this tool not yet done. */
function _routeCurrent() {
  if (!_route) return -1;
  const steps = ROUTES[_route.id].steps;
  const scr = typeof _activeScreenId === 'function' ? _activeScreenId() : '';
  if (_route.cur != null && steps[_route.cur] && steps[_route.cur].tool === scr) return _route.cur;
  let i = steps.findIndex((s, k) => s.tool === scr && !_route.done[k]);
  if (i < 0) i = steps.findIndex(s => s.tool === scr);
  return i;
}

function routeNext() {
  if (!_route) return;
  const steps = ROUTES[_route.id].steps;
  const cur = _routeCurrent();
  if (cur >= 0) _route.done[cur] = true;
  let n = steps.findIndex((s, k) => k > cur && !_route.done[k]);
  if (n < 0) n = steps.findIndex((s, k) => !_route.done[k]);
  _routeSave();
  if (n >= 0) routeGo(n); else routeRender();
}

/** A tool that changed the show ticks its step (the first not yet done).
 *  Called by the show bar after each refresh. */
function routeSync(changedTools) {
  if (!_route) return;
  const steps = ROUTES[_route.id].steps;
  _route.seen = _route.seen || {};
  let dirty = false;
  Object.entries(changedTools || {}).forEach(([tool, n]) => {
    if ((n || 0) > (_route.seen[tool] || 0)) {
      const k = steps.findIndex((s, j) => s.tool === tool && !_route.done[j]);
      if (k >= 0) { _route.done[k] = true; dirty = true; }
    }
    _route.seen[tool] = n || 0;
  });
  if (dirty) _routeSave();
  routeRender();
}

function routeRender() {
  const el = document.getElementById('route-strip');
  if (!el) return;
  if (!_route) { el.hidden = true; el.innerHTML = ''; return; }
  const r = ROUTES[_route.id];
  const cur = _routeCurrent();
  const nDone = _route.done.filter(Boolean).length;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  el.hidden = false;
  el.innerHTML =
    `<span class="rs-title" title="A guide, not a lock: any step, any order — every tool works on the show in progress">▶ ${esc(r.title)} <small>${nDone}/${r.steps.length}</small></span>` +
    `<ol class="rs-steps">` +
    r.steps.map((s, i) =>
      `<li class="rs-step${i === cur ? ' cur' : ''}${_route.done[i] ? ' done' : ''}" onclick="routeGo(${i})" title="${esc(s.hint)}">` +
      `<span class="rs-tick" onclick="routeToggle(${i}, event)" title="${_route.done[i] ? 'Done — click to untick' : 'Tick when done (or skipped)'}">${_route.done[i] ? '✓' : i + 1}</span>` +
      `<span class="rs-lbl">${esc(s.label)}</span></li>`).join('') +
    `</ol>` +
    `<button class="btn btn-surface btn-sm" onclick="routeNext()" title="Tick this step and open the next one">Done, next ›</button>` +
    `<button class="rs-close" onclick="routeClose()" title="Close the route (the show is not affected)">✕</button>`;
}

document.addEventListener('DOMContentLoaded', () => { _routeLoad(); routeRender(); });
