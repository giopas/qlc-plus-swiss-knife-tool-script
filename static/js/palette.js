// =============================================================================
// Command palette — ⌘K / Ctrl+K (v2.2 UI review): go to any tool or action by
// typing a few letters.  No library: a list, a filter, the arrow keys.
// =============================================================================

const _CP_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
let _cpItems = [], _cpHits = [], _cpSel = 0;

function _cpTools() {
  const out = [];
  let grp = 'home';
  document.querySelectorAll('.side-nav .sn-group-label, .side-nav .sn-item[id^="sn-"]').forEach(el => {
    if (el.classList.contains('sn-group-label')) {
      grp = `${el.querySelector('.sn-gnum')?.textContent.trim() || ''} · ${el.querySelector('.sn-gtxt')?.textContent.trim() || ''}`;
      return;
    }
    const id = el.id.slice(3);
    out.push({ label: el.dataset.tip || el.textContent.trim(), sub: grp, kind: 'tool',
               desc: el.dataset.desc || '', run: () => go(id) });
  });
  return out;
}

function _cpActions() {
  const on = typeof _show !== 'undefined' && _show.active;
  const a = [
    { label: '↶ Undo the last change', sub: 'show', when: on, run: () => showUndo() },
    { label: '↷ Redo', sub: 'show', when: on && _show.redo, run: () => showRedo() },
    { label: '🕘 History of the show', sub: 'show', when: on, run: () => showHistoryToggle(true) },
    { label: '💾 Save as new file…', sub: 'show', when: on, run: () => showSave() },
    { label: '📋 Save the recipe…', sub: 'do it again', when: on, run: () => showSaveRecipe() },
    { label: '★ Save the changes as a profile…', sub: 'do it again', when: on, run: () => startProfiles().then(() => {
      const n = document.getElementById('sh-prof-new'); if (n) { n.hidden = false; document.getElementById('sh-prof-name')?.focus(); } }) },
    { label: '📂 Open a show…', sub: 'file', run: () => browseWorkspace() },
    { label: '↻ Reload the show from disk', sub: 'file', when: on, run: () => reloadFromDisk() },
    { label: '🔍 Check the show (Workspace Doctor)', sub: 'check', when: on, run: () => { go('doctor'); if (typeof doctorCheck === 'function') doctorCheck(); } },
    { label: '▶ Route: adapt a show to a new venue', sub: 'guided route', run: () => routeStart('adapt') },
    { label: '▶ Route: get ready for the gig', sub: 'guided route', run: () => routeStart('gig') },
    { label: '◐ Change the theme (dark / grey / light)', sub: 'view', run: () => cycleTheme() },
    { label: '? Help for this tool', sub: 'wiki', run: () => document.querySelector('.screen.active .help-btn')?.click() },
  ];
  return a.filter(x => x.when === undefined || x.when).map(x => ({ ...x, kind: 'action' }));
}

async function _cpProfiles() {
  try {
    const d = await (await fetch('/api/profile/list')).json();
    return (d.profiles || []).map(p => ({ label: `▶ Apply profile “${p.name}”`, sub: `profile · ${p.steps} steps`, kind: 'action',
      desc: p.description || '', run: async () => { await startProfiles(); if (typeof _show !== 'undefined' && _show.active) showApplyProfile(p.path); } }));
  } catch { return []; }
}

/** Letters of q in order (fuzzy); a match at a word start scores higher. */
function _cpScore(q, text) {
  const t = text.toLowerCase();
  if (!q) return 1;
  const at = t.indexOf(q);
  if (at >= 0) return 100 - at + (at === 0 || /\W/.test(t[at - 1]) ? 50 : 0);
  let i = 0, s = 0, last = -2;
  for (let j = 0; j < t.length && i < q.length; j++) {
    if (t[j] === q[i]) { s += (j === last + 1 ? 3 : 1) + (j === 0 || /\W/.test(t[j - 1]) ? 4 : 0); last = j; i++; }
  }
  return i === q.length ? s : 0;
}

function _cpMark(text, q) {
  const esc = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  if (!q) return esc(text);
  const t = text.toLowerCase(), at = t.indexOf(q);
  if (at >= 0) return esc(text.slice(0, at)) + '<b>' + esc(text.slice(at, at + q.length)) + '</b>' + esc(text.slice(at + q.length));
  let i = 0, out = '';
  for (const ch of text) {
    if (i < q.length && ch.toLowerCase() === q[i]) { out += '<b>' + esc(ch) + '</b>'; i++; } else out += esc(ch);
  }
  return out;
}

function _cpRender() {
  const q = (document.getElementById('cp-input')?.value || '').trim().toLowerCase();
  _cpHits = _cpItems.map(it => ({ it, s: Math.max(_cpScore(q, it.label), _cpScore(q, it.sub) * .5, _cpScore(q, it.desc || '') * .3) }))
    .filter(x => x.s > 0).sort((a, b) => (b.s - a.s) || 0).slice(0, 14).map(x => x.it)
    .sort((a, b) => (a.kind === b.kind ? 0 : a.kind === 'tool' ? -1 : 1));      // tools, then actions
  if (!q) _cpHits = _cpItems.filter(x => x.kind === 'tool').slice(0, 7).concat(_cpItems.filter(x => x.kind === 'action').slice(0, 7));
  _cpSel = Math.min(_cpSel, Math.max(0, _cpHits.length - 1));
  const list = document.getElementById('cp-list');
  let html = '', kind = '';
  _cpHits.forEach((it, i) => {
    if (it.kind !== kind) { kind = it.kind; html += `<li class="cp-sec">${kind === 'tool' ? 'Tools' : 'Actions'}</li>`; }
    html += `<li class="cp-row${i === _cpSel ? ' on' : ''}" data-i="${i}" title="${(it.desc || '').replace(/"/g, '&quot;')}">
      <span>${_cpMark(it.label, q)}</span><small>${_cpMark(it.sub || '', '')}</small></li>`;
  });
  list.innerHTML = html || '<li class="cp-none">Nothing matches — try another word</li>';
  list.querySelectorAll('.cp-row').forEach(li => {
    li.onmousemove = () => { if (_cpSel !== +li.dataset.i) { _cpSel = +li.dataset.i; _cpRender(); } };
    li.onclick = () => _cpRun(+li.dataset.i);
  });
  list.querySelector('.cp-row.on')?.scrollIntoView({ block: 'nearest' });
}

function _cpRun(i) {
  const it = _cpHits[i];
  cpClose();
  if (it) setTimeout(() => it.run(), 0);
}

async function cpOpen() {
  const box = document.getElementById('cp');
  if (!box) return;
  _cpItems = _cpTools().concat(_cpActions());
  box.hidden = false;
  const inp = document.getElementById('cp-input');
  inp.value = ''; _cpSel = 0;
  _cpRender();
  inp.focus();
  const prof = await _cpProfiles();
  if (prof.length && !box.hidden) { _cpItems = _cpItems.concat(prof); _cpRender(); }
}

function cpClose() {
  const box = document.getElementById('cp');
  if (box) box.hidden = true;
}

function _cpKey(e) {
  if (e.key === 'ArrowDown') { _cpSel = Math.min(_cpSel + 1, _cpHits.length - 1); _cpRender(); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { _cpSel = Math.max(_cpSel - 1, 0); _cpRender(); e.preventDefault(); }
  else if (e.key === 'Enter') { _cpRun(_cpSel); e.preventDefault(); }
  else if (e.key === 'Escape') { cpClose(); e.preventDefault(); }
}

document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    const box = document.getElementById('cp');
    if (box && !box.hidden) cpClose(); else cpOpen();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const k = document.getElementById('cp-kbd');
  if (k) k.textContent = _CP_MAC ? '⌘K' : 'Ctrl K';
});
