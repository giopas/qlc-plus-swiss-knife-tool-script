/* =============================================================================
   tooltip.js — hover tooltips that always fit the window (v3.0.1)

   The CSS tooltips ([data-tooltip]::after) were cut off by panes that clip
   their content and by the top of the window.  This draws one tooltip in a
   layer above everything, placed above the element, or below it when there
   is no room, and kept inside the window.  The text is read at hover time,
   so translated tooltips (i18n.js) show translated.  Disabled buttons do not
   receive mouse events in every web view: they keep the CSS tooltip.
   ============================================================================= */

'use strict';

(() => {
  const GAP = 8, EDGE = 8;
  let tip = null, cur = null;

  function layer() {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'sk-tip';
      tip.setAttribute('role', 'tooltip');
      document.body.appendChild(tip);
    }
    return tip;
  }

  function show(el) {
    const text = el.getAttribute('data-tooltip');
    if (!text) return;
    const t = layer();
    t.textContent = text;
    t.style.left = '0px'; t.style.top = '0px';
    t.classList.add('on');
    const r = el.getBoundingClientRect();
    const w = t.offsetWidth, h = t.offsetHeight;
    const vw = window.innerWidth, vh = window.innerHeight;
    let top = r.top - h - GAP;
    if (top < EDGE) top = r.bottom + GAP;                        // no room above: below
    if (top + h > vh - EDGE) top = Math.max(EDGE, vh - h - EDGE);
    let left = r.left + r.width / 2 - w / 2;
    left = Math.max(EDGE, Math.min(left, vw - w - EDGE));
    t.style.left = Math.round(left) + 'px';
    t.style.top = Math.round(top) + 'px';
    cur = el;
  }

  function hide() {
    if (tip) tip.classList.remove('on');
    cur = null;
  }

  document.documentElement.classList.add('js-tt');
  document.addEventListener('mouseover', e => {
    const el = e.target.closest && e.target.closest('[data-tooltip]');
    if (el === cur) return;
    if (!el || el.disabled) { hide(); return; }
    show(el);
  });
  document.addEventListener('mouseout', e => {
    if (cur && !(e.relatedTarget && cur.contains(e.relatedTarget))) hide();
  });
  ['mousedown', 'scroll', 'keydown', 'blur'].forEach(ev => window.addEventListener(ev, hide, true));
})();
