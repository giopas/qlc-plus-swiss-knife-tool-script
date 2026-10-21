// =============================================================================
// Guided routes (WORKPLAN 2.6): a strip of steps above the tools for a job
// that takes several tools — e.g. adapt a show to a new venue.  Any step, any
// order; a step is ticked when its tool changed the show, or by hand.
// The strip only guides: every tool still works on the show in progress.
// =============================================================================

const ROUTES = {
  new: {
    title: 'Start a new show',
    steps: [
      { tool: 'quickstart', label: 'The rig',     hint: 'Quick Start (or Fixtures for the rig alone) — fixtures, patch, groups, first looks and console; Save as new file…, then Open it as the show' },
      { tool: 'stage',    label: 'Groups', tab: 'groups', hint: 'Stage & Meshes › Groups — the fixture groups the looks are built on' },
      { tool: 'looks',    label: 'Looks',         hint: 'Look Builder — looks and chasers for the groups' },
      { tool: 'vceditor', label: 'Console',       hint: 'VC Visual Editor — pages, buttons, the setlist CueList' },
      { tool: 'stage',    label: 'Stage',         hint: 'Stage & Meshes — the stage, band and set pieces' },
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — the songs into the CueList' },
      { tool: 'showbook', label: 'Paperwork',     hint: 'Show Paperwork — patch sheet, tech rider, crew checklist' },
      { tool: 'doctor',   label: 'Final check',   hint: 'Workspace Doctor — nothing left to fix, then Save as new file…' },
    ],
  },
  adapt: {
    title: 'Adapt a show to a new venue',
    steps: [
      { tool: 'reducer',  label: 'Keep the rig',  hint: 'Rig Reducer — keep the fixtures the venue has, re-patch' },
      { tool: 'doctor',   label: 'Clean up',      hint: 'Workspace Doctor — fix what the old show carries' },
      { tool: 'porter',   label: 'Bring functions', optional: true, hint: 'Function Porter — looks, chasers, fixtures or groups from another show (skip if not needed)' },
      { tool: 'stage',    label: 'Groups', tab: 'groups', hint: 'Stage & Meshes › Groups — the fixture groups the looks are built on' },
      { tool: 'looks',    label: 'Looks',         hint: 'Look Builder — looks and chasers for the new groups' },
      { tool: 'vceditor', label: 'Console',       hint: 'VC Visual Editor — pages, buttons, the setlist CueList' },
      { tool: 'stage',    label: 'Stage',         hint: 'Stage & Meshes — the venue stage, band and set pieces' },
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — tonight’s songs into the CueList' },
      { tool: 'doctor',   label: 'Final check',   hint: 'Workspace Doctor — nothing left to fix, then Save as new file…' },
    ],
  },
  wizard: {
    title: 'Finish a QLC+ wizard show',
    steps: [
      { tool: 'doctor',   label: 'Check',         hint: 'Workspace Doctor — what the Show Wizard left (I005, I007, D020); fix the rest' },
      { tool: 'wizard',   label: 'Repair',        hint: 'Wizard Repair — lost effects, buttons for what is off the console, group grids, palettes that do nothing, PANIC RESET' },
      { tool: 'vceditor', label: 'Console',       hint: 'VC Visual Editor — move or rename the new buttons, add a setlist page' },
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — tonight’s songs into the CueList' },
      { tool: 'showbook', label: 'Paperwork',     hint: 'Show Paperwork — patch sheet, tech rider, crew checklist' },
      { tool: 'doctor',   label: 'Final check',   hint: 'Workspace Doctor — nothing left to fix, then Save as new file…' },
    ],
  },
  upgrade: {
    title: 'Upgrade a show to QLC+ 5.3',
    steps: [
      { tool: 'doctor',   label: 'Check',         hint: 'Workspace Doctor — fix what the show carries before adding to it' },
      { tool: 'upgrade',  label: 'Upgrade',       hint: 'Upgrade to QLC+ 5.3 — folders, palettes, an All Fixtures group, positions, a page per group, locked fixtures' },
      { tool: 'vceditor', label: 'Console',       hint: 'VC Visual Editor — look at the Groups page, move or rename what you like' },
      { tool: 'doctor',   label: 'Final check',   hint: 'Workspace Doctor — nothing left to fix (I008 lists what QLC+ 5.2.2 would ignore), then Save as new file…' },
    ],
  },
  gig: {
    title: 'Get ready for the gig',
    steps: [
      { tool: 'setlist',  label: 'Setlist',       hint: 'Setlist — tonight’s songs into the CueList' },
      { tool: 'triggers', label: 'Keys & MIDI',   hint: 'Trigger Manager — no clashes, every button reachable' },
      { tool: 'doctor',   label: 'Check',         hint: 'Workspace Doctor — nothing left to fix, then Save as new file…' },
      { tool: 'cabling',  label: 'Cabling',       hint: 'Cabling — the DMX cables for tonight: kit, places, plan, pick list and labels' },
      { tool: 'showbook', label: 'Paperwork',     hint: 'Show Paperwork — tech rider for the venue, crew checklist (with the cabling)' },
    ],
  },
};

const _ROUTE_KEY = 'sk.route';
let _route = null;          // { id, done: [bool…], skip: [bool…], seen: {tool: n}, cur }

function _routeLoad() {
  try {
    const r = JSON.parse(localStorage.getItem(_ROUTE_KEY) || 'null');
    if (r && ROUTES[r.id]) {
      const n = ROUTES[r.id].steps.length;
      r.done = Array.from({ length: n }, (_x, i) => !!(r.done || [])[i]);
      r.skip = Array.from({ length: n }, (_x, i) => !!(r.skip || [])[i]);
      _route = r;
    }
  } catch { _route = null; }
}
function _routeSave() {
  try {
    if (_route) localStorage.setItem(_ROUTE_KEY, JSON.stringify(_route));
    else localStorage.removeItem(_ROUTE_KEY);
  } catch { /* per-browser convenience only */ }
}

/* ── Where a tool is (3.4.0) ─────────────────────────────────────────────────
   A tool with steps of its own (Quick Start, Function Porter) or a panel open
   on top of it (the Look Builder's effect panel) says so here:
     toolPosition('porter', { steps: ['Load', …], cur: 1, go: i => … })
     toolPosition('quickstart', { …, finish: { verb: 'Save', run: async () => ok } })
     toolPosition('looks', { crumb: ['Rainbow'], modal: true, back: () => … })
     toolPosition('looks', null)               // back to the tool itself
   Inside a route, the route strip shows it on a second row under the current
   step, and the footer's main button says where it goes; outside a route, the
   tool's own .tool-stepper shows its steps with the same look.            */
const _toolPos = {};
function toolPosition(tool, pos) {
  if (pos) _toolPos[tool] = pos; else delete _toolPos[tool];
  routeRender();
}
function toolStepGo(tool, i) {
  const p = _toolPos[tool];
  if (p && p.go) p.go(i);
}
function toolBack(tool) {
  const p = _toolPos[tool];
  if (p && p.back) p.back();
}

const _rEsc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const _rTr = (s, ...v) => (typeof t === 'function' ? t(s, ...v) : s.replace(/\{(\d+)\}/g, (_x, i) => v[+i] ?? ''));

/** The shared stepper: one look for the route and for a tool's own steps.
 *  items: [{ label, state: 'done'|'cur'|'skip'|'todo', go: "js", tick: "js"|null, tip }] */
function stepperHTML(items, cls) {
  return `<ol class="stp ${cls || ''}">` + items.map((it, i) => {
    const mark = it.state === 'done' ? '✓' : it.state === 'skip' ? '–' : String(i + 1);
    const num = it.tick
      ? `<button type="button" class="stp-n" onclick="${it.tick}" title="${_rEsc(it.state === 'done' ? 'Done: click to untick' : 'Tick it as done')}">${mark}</button>`
      : `<span class="stp-n" aria-hidden="true">${mark}</span>`;
    return `<li class="stp-i st-${it.state}"${it.state === 'cur' ? ' aria-current="step"' : ''}>${num}` +
      `<button type="button" class="stp-l" onclick="${it.go}"${it.tip ? ` title="${_rEsc(it.tip)}"` : ''}>${_rEsc(it.label)}</button></li>`;
  }).join('') + `</ol>`;
}

/** "Next: Placement →", the footer label inside a tool's own steps. */
function stepNextLabel(label) { return _rTr('Next: {0} →', _rTr(label)); }

function _toolName(tool) {
  const b = document.getElementById('sn-' + tool);
  const lbl = b && (b.querySelector('.sn-lbl') || b);
  return lbl ? lbl.textContent.trim() : tool;
}

function _toolItems(tool, p) {
  return p.steps.map((lbl, i) => ({
    label: lbl,
    state: i === p.cur ? 'cur' : (p.done ? p.done[i] : i < p.cur) ? 'done' : 'todo',
    go: `toolStepGo('${tool}', ${i})`, tick: null,
  }));
}

document.addEventListener('sk-lang', () => routeRender());

/** Start a route (from the Start card) and open its first step. */
function routeStart(id) {
  if (!ROUTES[id]) return;
  const n = ROUTES[id].steps.length;
  _route = { id, done: Array(n).fill(false), skip: Array(n).fill(false), seen: {} };
  _routeSave();
  routeRender();
  routeGo(0);
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
  if (_route.done[i]) _route.skip[i] = false;
  _routeSave();
  routeRender();
}

/** The step on screen: the one last opened if it is this tool, else the
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

/** The next step to open after `cur`: the first one after it still to do,
 *  else the first one still to do anywhere; -1 when there is none. */
function _routeNextIdx(cur) {
  const steps = ROUTES[_route.id].steps;
  const open = k => k !== cur && !_route.done[k] && !_route.skip[k];
  let n = steps.findIndex((s, k) => k > cur && open(k));
  if (n < 0) n = steps.findIndex((s, k) => open(k));
  return n;
}

/** The footer's route button: finish the tool's last step if it has a way
 *  to (Quick Start saves and opens the show), tick this step, open the next. */
async function routeForward() {
  if (!_route) return;
  const steps = ROUTES[_route.id].steps;
  const cur = _routeCurrent();
  if (cur < 0) return;
  const p = _toolPos[steps[cur].tool];
  if (!_route.done[cur] && p && p.finish) {
    const ok = await p.finish.run();
    if (!ok || !_route) return;
  }
  _route.done[cur] = true;
  _route.skip[cur] = false;
  _routeSave();
  const n = _routeNextIdx(cur);
  if (n >= 0) { routeGo(n); return; }
  routeRender();
  if (typeof showSave === 'function' && typeof _show !== 'undefined' && _show.active) showSave();
  setStatus(_rTr('Route done: {0}. Keep the show with Save as new file… in the header.', _rTr(ROUTES[_route.id].title)), 'ok');
}

/** Kept for the old "Done, next ›" (and anything that still calls it). */
function routeNext() { routeForward(); }

/** "Skip this step": leave it unticked and open the next one. */
function routeSkip() {
  if (!_route) return;
  const cur = _routeCurrent();
  if (cur < 0) return;
  _route.skip[cur] = true;
  _route.done[cur] = false;
  _routeSave();
  const n = _routeNextIdx(cur);
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
      const cur = _routeCurrent();
      let k = (cur >= 0 && steps[cur].tool === tool && !_route.done[cur]) ? cur
        : steps.findIndex((s, j) => s.tool === tool && !_route.done[j]);
      if (k >= 0) { _route.done[k] = true; _route.skip[k] = false; dirty = true; }
    }
    _route.seen[tool] = n || 0;
  });
  if (dirty) _routeSave();
  routeRender();
}

function routeRender() {
  if (typeof renderStart === 'function') renderStart();
  const el = document.getElementById('route-strip');
  const sub = document.getElementById('route-sub');
  if (!el) return;
  document.querySelectorAll('.screen.in-route-step').forEach(s => s.classList.remove('in-route-step'));
  _renderToolSteppers();
  if (!_route) {
    el.hidden = true; el.innerHTML = '';
    if (sub) { sub.hidden = true; sub.innerHTML = ''; }
    _routeFooter(-1);
    return;
  }
  const r = ROUTES[_route.id];
  const cur = _routeCurrent();
  const nDone = _route.done.filter(Boolean).length;
  const allDone = nDone === r.steps.length || _routeNextIdx(-1) < 0;
  const items = r.steps.map((s, i) => ({
    label: s.label,
    state: _route.done[i] ? 'done' : i === cur ? 'cur' : _route.skip[i] ? 'skip' : 'todo',
    go: `routeGo(${i})`, tick: `routeToggle(${i}, event)`, tip: s.hint,
  }));
  if (cur >= 0) items[cur].state = 'cur';
  if (cur >= 0) items[cur].done = _route.done[cur];
  const pos = cur >= 0 ? _rTr('step {0} of {1}', cur + 1, r.steps.length) : _rTr('{0} of {1} done', nDone, r.steps.length);
  const opt = cur >= 0 && r.steps[cur].optional && !_route.done[cur];
  el.hidden = false;
  el.innerHTML =
    `<span class="rs-title" title="${_rEsc(_rTr('A guide, not a lock: any step, any order. Every tool works on the show in progress.'))}">▶ ${_rEsc(_rTr(r.title))}</span>` +
    `<span class="rs-pos" data-i18n="off">${_rEsc(allDone ? _rTr('all done') : pos)}</span>` +
    stepperHTML(items, 'stp-route') +
    (cur >= 0 && !_route.done[cur]
      ? `<button type="button" class="${opt ? 'btn btn-surface btn-sm rs-skip-btn' : 'rs-skip'}" onclick="routeSkip()" title="Leave this step unticked and open the next one">${opt ? 'Not needed? Skip it' : 'Skip this step'}</button>`
      : '') +
    `<button type="button" class="rs-close" onclick="routeClose()" title="Leave the route (the show is not affected)" aria-label="Leave the route">✕</button>`;
  if (cur >= 0 && _route.done[cur]) el.querySelector('.stp-route .st-cur').classList.add('is-done');
  // a narrow window: the steps stay on one line and scroll, with the current one in view
  const ol = el.querySelector('.stp-route');
  if (ol) {
    const c = ol.querySelector('.st-cur');
    if (c && ol.scrollWidth > ol.clientWidth)
      ol.scrollLeft = Math.max(0, c.offsetLeft - ol.offsetLeft - (ol.clientWidth - c.offsetWidth) / 2);
    ol.classList.toggle('ovf-r', ol.scrollLeft + ol.clientWidth < ol.scrollWidth - 2);
    ol.classList.toggle('ovf-l', ol.scrollLeft > 2);
    ol.onscroll = () => {
      ol.classList.toggle('ovf-r', ol.scrollLeft + ol.clientWidth < ol.scrollWidth - 2);
      ol.classList.toggle('ovf-l', ol.scrollLeft > 2);
    };
  }

  // the second row: where you are inside the tool of the current step
  if (sub) {
    if (cur < 0) { sub.hidden = true; sub.innerHTML = ''; }
    else {
      const s = r.steps[cur];
      const scr = document.getElementById('scr-' + s.tool);
      if (scr) scr.classList.add('in-route-step');
      const p = _toolPos[s.tool];
      const name = _toolName(s.tool);
      let html = `<span class="rsub-lbl" data-i18n="off">` + _rEsc(_rTr('{0}, in', _rTr(s.label))) + ' ' +
        (p && p.crumb ? `<button type="button" class="rsub-tool" onclick="toolBack('${s.tool}')">${_rEsc(name)}</button>` : `<b>${_rEsc(name)}</b>`) +
        (p && p.steps ? ':' : '') + `</span>`;
      if (p && p.steps) html += stepperHTML(_toolItems(s.tool, p), 'stp-tool');
      else if (p && p.crumb) html += p.crumb.map(c => `<span class="rsub-sep">›</span><span class="rsub-crumb">${_rEsc(c)}</span>`).join('');
      sub.innerHTML = html;
      sub.hidden = false;
      // line the row up under the current step, which opens into it like a tab
      const curEl = el.querySelector('.stp-route .st-cur');
      sub.style.paddingLeft = '';
      if (curEl) {
        const x = curEl.getBoundingClientRect().left - el.getBoundingClientRect().left;
        const kids = [...sub.children];
        const need = kids.reduce((w, k) => w + k.getBoundingClientRect().width, 0) + 12 * kids.length + 32;
        const room = el.getBoundingClientRect().width - need;
        if (x > 0 && x < room + 16) sub.style.paddingLeft = Math.round(x) + 'px';
      }
    }
  }
  _routeFooter(cur);
}

/** Outside a route, a tool with steps shows them in its own .tool-stepper. */
function _renderToolSteppers() {
  document.querySelectorAll('.tool-stepper[data-tool]').forEach(box => {
    const tool = box.dataset.tool;
    const p = _toolPos[tool];
    if (!p || !p.steps) { box.innerHTML = ''; return; }
    box.innerHTML = stepperHTML(_toolItems(tool, p), 'stp-tool') +
      `<span class="ts-pos" data-i18n="off">${_rEsc(_rTr('step {0} of {1}', p.cur + 1, p.steps.length))}</span>`;
  });
}

/** The footer's route button: the one way forward inside a route.
 *  Inside a tool's own steps the tool's Next moves on; at its last step, or
 *  once the step is ticked, this button says where it goes and is the main
 *  one (the tool's own main button turns secondary). */
function _routeFooter(cur) {
  document.querySelectorAll('.rs-go').forEach(b => b.remove());
  document.querySelectorAll('.rs-demoted').forEach(b => b.classList.remove('rs-demoted'));
  if (!_route || cur < 0) return;
  const steps = ROUTES[_route.id].steps;
  const tool = steps[cur].tool;
  const scr = document.getElementById('scr-' + tool);
  if (!scr) return;
  const foot = [...scr.querySelectorAll('.out-footer')].filter(f => f.offsetParent !== null).pop();
  if (!foot) return;
  const p = _toolPos[tool];
  if (p && p.modal) return;                                    // a panel is open: it finishes itself
  const done = _route.done[cur];
  if (!done && p && p.steps && p.cur < p.steps.length - 1) return;   // the tool's own Next moves on
  const n = _routeNextIdx(cur);
  const finish = !done && p && p.finish;
  let label;
  if (n < 0) label = finish ? _rTr('{0} and finish the route', _rTr(p.finish.verb)) : _rTr('Finish the route');
  else {
    const to = `${n + 1} ${_rTr(steps[n].label)}`;
    label = finish ? _rTr('{0} and go on: {1} ›', _rTr(p.finish.verb), to) : _rTr('Go on: {0} ›', to);
  }
  const strong = done || !!finish;
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn rs-go ' + (strong ? 'btn-accent' : 'btn-surface');
  b.setAttribute('data-i18n', 'off');
  b.textContent = label;
  b.title = _rTr(finish && p.finish.tip ? p.finish.tip : 'Tick this step of the route and open the next one');
  b.onclick = routeForward;
  if (strong) foot.querySelectorAll('.btn-accent').forEach(x => x.classList.add('rs-demoted'));
  foot.appendChild(b);
}

/** Start screen: each route card lists its steps (from ROUTES, so they never
 *  drift apart); the profile card lists the saved profiles. */
function routeCards() {
  document.querySelectorAll('.rt-steps[data-route]').forEach(ol => {
    const r = ROUTES[ol.dataset.route];
    if (r) ol.innerHTML = r.steps.map((s, i) => `<li title="${s.hint.replace(/"/g, '&quot;')}">${i + 1}. ${s.label}</li>`).join('');
  });
  document.querySelectorAll('[data-route-meta]').forEach(el => {
    const r = ROUTES[el.dataset.routeMeta];
    if (r) el.textContent = `${r.steps.length} steps` + (el.dataset.routeMeta === 'adapt' ? ' · the Pub test took 12 minutes' : '');
  });
  fetch('/api/profile/list').then(r => r.json()).then(d => {
    const ps = d.profiles || [];
    const n = document.getElementById('rt-prof-n');
    if (n) n.textContent = ps.length ? `${ps.length} saved profile${ps.length > 1 ? 's' : ''}` : 'no profiles yet';
    const ol = document.getElementById('rt-prof-list');
    if (ol) ol.innerHTML = ps.length
      ? ps.slice(0, 4).map(p => `<li title="${(p.description || '').replace(/"/g, '&quot;')}">${p.name.replace(/</g, '&lt;')} — ${p.steps} step${p.steps === 1 ? '' : 's'}</li>`).join('')
      : '<li>History › ★ Save as a profile… after changing a show</li>';
  }).catch(() => {});
}

/** Start card "Do it again with a profile": the History's Do it again box. */
async function startProfiles(fromNothing) {
  if (!fromNothing && (typeof _show === 'undefined' || !_show.active)) { setStatus('Open the show to apply the profile to first (Open…) — or ▶ Start a show from a profile that keeps its own rig.', 'warn'); return; }
  await showHistoryToggle(true);
  const d = document.getElementById('sh-again');
  if (d) { d.open = true; d.scrollIntoView({ block: 'nearest' }); }
}

document.addEventListener('DOMContentLoaded', () => { _routeLoad(); routeRender(); routeCards(); });
