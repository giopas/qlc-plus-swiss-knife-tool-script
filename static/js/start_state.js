/* =============================================================================
   start_state.js: a Start screen that follows the state (3.9.5, DESIGN_v2.md section 7)

   skStartState(ctx) is a pure function: it picks one of five states by a fixed
   rule order and says what the top zone of Start shows.  renderStart() draws it.
   Every text is a pattern for t(): [pattern, ...parts], so the languages work.

     ctx = { loaded, name, unsaved, doctor: {error, warning, rules}, route: {title, step, total, label} | null }

   Order (the first that fits wins, the rest become small lines under it):
     A no show open · B a route in progress · C the Doctor has errors ·
     D changes not saved · E clean and saved.
   One fact and one button each: no score, no percentage.
   ============================================================================= */

'use strict';

/** One pattern for 1, another for more: ['{0} error', ...] or ['{0} errors', ...] (English plurals; each language has both). */
function _pl(n, one, many, ...parts) { return [n === 1 ? one : many, ...parts]; }

function skStartState(ctx) {
  const c = ctx || {};
  const doc = c.doctor || {};
  const e = doc.error || 0, w = doc.warning || 0;
  const rules = doc.rules || {};
  const wk = Object.keys(rules).filter(k => rules[k].severity === 'warning').length || w;
  const n = c.unsaved || 0;
  const name = c.name || '';

  if (!c.loaded) {
    return {
      state: 'A', tone: 'plain',
      headline: ['Open a show to start'],
      sub: ['Swiss Knife changes a copy. The file you open is never touched.'],
      actions: [],
      notes: [{ text: ['No show yet? Quick Start builds one from your fixtures.'], action: { label: ['Quick Start'], run: 'go:quickstart' } }],
    };
  }

  const errNote = { text: _pl(e, '{0} error to look at.', '{0} errors to look at.', e), action: { label: ['Open the Doctor'], run: 'go:doctor' } };
  const warnNote = { text: _pl(wk, 'Also: {0} kind of warning, it does not block saving.', 'Also: {0} kinds of warning, none blocks saving.', wk), action: { label: ['See them'], run: 'go:doctor' } };
  const saveNote = { text: _pl(n, '{0} change is not saved.', '{0} changes are not saved.', n), action: { label: ['Save as new file…'], run: 'fn:showSave' } };
  const notes = (...list) => list.filter(Boolean);

  if (c.route) {
    const r = c.route;
    return {
      state: 'B', tone: 'route',
      headline: ['You are on step {0} of {1} in {2}: {3}.', r.step, r.total, r.title, r.label],
      sub: null,
      actions: [{ label: ['Continue'], run: 'fn:routeContinue', primary: true }, { label: ['Leave the route'], run: 'fn:routeClose' }],
      notes: notes(e ? errNote : null, n ? saveNote : null),
    };
  }
  if (e) {
    return {
      state: 'C', tone: 'error',
      headline: _pl(e, '{0} has {1} error to look at.', '{0} has {1} errors to look at.', name, e),
      sub: null,
      actions: [{ label: ['Open the Doctor'], run: 'go:doctor', primary: true }],
      notes: notes(w ? warnNote : null, n ? saveNote : null),
    };
  }
  if (n) {
    return {
      state: 'D', tone: 'unsaved',
      headline: _pl(n, '{0} change is not saved.', '{0} changes are not saved.', n),
      sub: null,
      actions: [{ label: ['Save as new file…'], run: 'fn:showSave', primary: true }, { label: ['History'], run: 'fn:showHistoryToggle' }],
      notes: notes(w ? warnNote : null),
    };
  }
  return {
    state: 'E', tone: 'ready',
    headline: ['{0} is ready. What next?', name],
    sub: null, actions: [],
    notes: notes(w ? warnNote : null),
  };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { skStartState };

/* ── drawing (browser only) ─────────────────────────────────────────────── */

function _skT(arr) {
  if (!arr) return '';
  const [pat, ...vars] = arr;
  return typeof t === 'function' ? t(pat, ...vars) : pat.replace(/\{(\d+)\}/g, (_m, i) => vars[+i]);
}

function _skRun(run) {
  if (run.startsWith('go:')) go(run.slice(3));
  else if (run.startsWith('fn:') && typeof window[run.slice(3)] === 'function') window[run.slice(3)]();
}

/** The route step to open when Continue is pressed. */
function routeContinue() {
  if (typeof _route === 'undefined' || !_route) return;
  const i = _skRouteStep();
  if (i >= 0) routeGo(i);
}

/** The step in progress: the one last opened, else the first not done and not skipped. */
function _skRouteStep() {
  if (typeof _route === 'undefined' || !_route || typeof ROUTES === 'undefined' || !ROUTES[_route.id]) return -1;
  const steps = ROUTES[_route.id].steps;
  if (Number.isInteger(_route.cur) && steps[_route.cur] && !_route.done[_route.cur]) return _route.cur;
  const i = steps.findIndex((_s, k) => !_route.done[k] && !_route.skip[k]);
  return i;
}

function skStartContext() {
  const show = (typeof _show !== 'undefined' && _show) || {};
  let route = null;
  if (typeof _route !== 'undefined' && _route && typeof ROUTES !== 'undefined' && ROUTES[_route.id]) {
    const i = _skRouteStep();
    if (i >= 0) {
      const R = ROUTES[_route.id];
      route = { title: _skT([R.title]), step: i + 1, total: R.steps.length, label: _skT([R.steps[i].label]) };
    }
  }
  return {
    loaded: !!show.active,
    name: window._wsLabel || show.source_name || '',
    unsaved: show.unsaved || 0,
    doctor: show.doctor || null,
    route,
  };
}

function renderStart() {
  const zone = document.getElementById('start-state');
  if (!zone) return;
  const ctx = skStartContext();
  const st = skStartState(ctx);
  zone.hidden = false;
  zone.dataset.state = st.state;
  zone.className = 'start-state tone-' + st.tone;
  const esc = typeof _esc === 'function' ? _esc : s => String(s);
  const btn = (a, cls) => `<button class="btn btn-sm ${a.primary ? 'btn-accent' : 'btn-surface'}${cls || ''}" data-run="${esc(a.run)}">${esc(_skT(a.label))}</button>`;
  zone.innerHTML =
    `<div class="ss-head" role="status"><b>${esc(_skT(st.headline))}</b>${st.sub ? `<span>${esc(_skT(st.sub))}</span>` : ''}</div>` +
    (st.actions.length ? `<div class="ss-actions">${st.actions.map(a => btn(a)).join('')}</div>` : '') +
    st.notes.map(nt => `<div class="ss-note"><span>${esc(_skT(nt.text))}</span><button class="sc-link" data-run="${esc(nt.action.run)}">${esc(_skT(nt.action.label))}</button></div>`).join('');
  zone.querySelectorAll('[data-run]').forEach(b => b.addEventListener('click', () => _skRun(b.dataset.run)));
  // State A keeps the drop zone and the recents; every other state is about the open show
  const drop = document.getElementById('start-drop-zone');
  if (drop) drop.classList.toggle('u-hidden', ctx.loaded);
  const rec = document.getElementById('recent-list');
  if (rec) rec.classList.toggle('u-hidden', ctx.loaded);
  _skMarkLastTool();
}

/** The tool of each job card last used is marked (localStorage, a per-browser convenience). */
function _skMarkLastTool() {
  let last = '';
  try { last = localStorage.getItem('sk-lasttool') || ''; } catch { /* none */ }
  document.querySelectorAll('.wf-chip').forEach(ch => {
    const m = /go\('(\w+)'\)/.exec(ch.getAttribute('onclick') || '');
    ch.classList.toggle('wf-last', !!m && m[1] === last);
    if (m && m[1] === last) ch.title = _skT(['Last used']);
  });
}

/** Keep the recent entry of the open show up to date: fixtures and Doctor result. */
function skRememberRecent() {
  const path = window._wsPath;
  const show = typeof _show !== 'undefined' ? _show : null;
  if (!path || !show || !show.active) return;
  try {
    const list = JSON.parse(localStorage.getItem('sk-recents') || '[]');
    const r = list.find(x => x.path === path && x.type !== 'qsk');
    if (!r) return;
    const fx = parseInt((document.getElementById('ms-fixtures') || {}).textContent, 10);
    const d = show.doctor ? { error: show.doctor.error || 0, warning: show.doctor.warning || 0 } : null;
    const same = r.fixtures === (Number.isNaN(fx) ? r.fixtures : fx) && JSON.stringify(r.doctor || null) === JSON.stringify(d);
    if (same) return;
    if (!Number.isNaN(fx)) r.fixtures = fx;
    r.doctor = d;
    localStorage.setItem('sk-recents', JSON.stringify(list));
    if (typeof _renderRecents === 'function') _renderRecents();
  } catch { /* per-browser convenience only */ }
}
