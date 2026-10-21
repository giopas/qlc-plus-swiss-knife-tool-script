/* =============================================================================
   kit.js: the page kit's few lines of JS (DESIGN_v2.md section 8, WORKPLAN 3.9.0)

   skActionBar({chip, summary, secondary, primary, why})   (chip, summary, labels, disabled and hidden may be functions)
       draws the sticky action bar into <div data-actionbar> (or opts.target):
       a chip that names what the main button does, a live summary, at most one
       Secondary and one Primary.  A disabled Primary shows why, in words, next
       to it, from its data-why.  Returns {el, update()}; call update() when the
       numbers change: the summary, the label and the disabled state are read again.

   skSegmented({options, value, onchange})  a segmented control (modes)
   skEmpty({text, button})                   the "open a show first" state
   skDone(message, {undo, history})          the "Applied. …  Undo · History" toast

   Text is set with textContent (no HTML from callers).  Words go through the
   i18n observer like any other text on the page.  Nothing here knows a tool.
   ============================================================================= */

'use strict';

/** The four verbs that write, and the chip each one wears (DESIGN_v2 section 6). */
const SK_CHIPS = {
  apply:    { text: 'Changes the show in progress',          cls: 'kit-chip-apply' },
  new:      { text: 'Writes a new file',                     cls: 'kit-chip-new' },
  export:   { text: 'Does not change the show',              cls: 'kit-chip-export' },
  settings: { text: 'Saved in your settings',                cls: 'kit-chip-settings' },
  beside:   { text: 'Saved next to the show',                cls: 'kit-chip-settings' },
  replace:  { text: 'Replaces the earlier page, after asking', cls: 'kit-chip-replace' },
};

(() => {
  const val = (v) => (typeof v === 'function' ? v() : v);

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function button(spec, cls) {
    const b = el('button', 'btn ' + cls);
    b.type = 'button';
    b.setAttribute('data-kit-role', cls.indexOf('accent') >= 0 ? 'primary' : 'secondary');
    if (spec.onclick) b.addEventListener('click', spec.onclick);
    return b;
  }

  function skActionBar(opts) {
    opts = opts || {};
    const host = typeof opts.target === 'string' ? document.querySelector(opts.target)
      : (opts.target || document.querySelector('[data-actionbar]'));
    if (!host) return null;

    const bar = el('div', 'kit-actionbar');
    const row = el('div', 'kit-actionbar-row');
    const left = el('div', 'kit-actionbar-left');
    const right = el('div', 'kit-actionbar-right');
    const chipEl = el('span', 'kit-chip');
    const summaryEl = el('span', 'kit-summary');
    const whyEl = el('div', 'kit-why');
    whyEl.id = 'kit-why-' + Math.random().toString(36).slice(2, 8);
    whyEl.setAttribute('role', 'status');            // read out when it changes
    whyEl.setAttribute('aria-live', 'polite');
    whyEl.hidden = true;

    left.append(chipEl, summaryEl);
    const sec = opts.secondary ? button(opts.secondary, 'btn-secondary') : null;
    const pri = opts.primary ? button(opts.primary, 'btn-accent') : null;   // at most one of each
    if (sec) right.append(sec);
    if (pri) right.append(pri);
    row.append(left, right);
    bar.append(row, whyEl);
    host.replaceChildren(bar);

    function update() {
      const spec = val(opts.chip);                       // a chip name, {kind, text} or a function giving one
      const chip = typeof spec === 'string' ? SK_CHIPS[spec] : spec;
      const known = chip && (chip.text || SK_CHIPS[chip.kind]);
      chipEl.className = 'kit-chip ' + ((chip && (chip.cls || (SK_CHIPS[chip.kind] || {}).cls)) || '');
      chipEl.textContent = known ? (chip.text || SK_CHIPS[chip.kind].text) : '';
      chipEl.hidden = !known;
      summaryEl.textContent = val(opts.summary) || '';
      for (const [b, spec] of [[sec, opts.secondary], [pri, opts.primary]]) {
        if (!b) continue;
        b.textContent = val(spec.label) || '';
        b.disabled = !!val(spec.disabled);
        b.hidden = !!val(spec.hidden);
      }
      // a disabled Primary says why: data-why on the button, the same words beside it
      const why = pri && pri.disabled && !pri.hidden ? (val(opts.why) || (opts.primary && val(opts.primary.why)) || '') : '';
      if (pri) {
        if (why) {
          pri.setAttribute('data-why', why);
          pri.setAttribute('data-tooltip', why);             // the tooltip is only a backup
          pri.setAttribute('aria-describedby', whyEl.id);
        } else {
          pri.removeAttribute('data-why');
          pri.removeAttribute('data-tooltip');
          pri.removeAttribute('aria-describedby');
        }
      }
      whyEl.textContent = why;
      whyEl.hidden = !why;
    }

    update();
    return { el: bar, update };
  }

  function skSegmented(opts) {
    const box = el('div', 'kit-seg');
    box.setAttribute('role', 'group');
    let value = opts.value;
    const buttons = new Map();
    function paint() { buttons.forEach((b, v) => b.setAttribute('aria-pressed', String(v === value))); }
    for (const o of opts.options || []) {
      const b = el('button', null, o.label);
      b.type = 'button';
      b.addEventListener('click', () => {
        if (o.value === value) return;
        value = o.value; paint();
        if (opts.onchange) opts.onchange(value);
      });
      buttons.set(o.value, b); box.append(b);
    }
    paint();
    return { el: box, get value() { return value; }, set(v) { value = v; paint(); } };
  }

  function skEmpty(opts) {
    const box = el('div', 'kit-empty');
    box.append(el('p', null, opts.text || 'Open a show to use this tool.'));
    if (opts.button) {
      const b = button(opts.button, 'btn-accent');
      b.textContent = opts.button.label || 'Open a show…';
      box.append(b);
    }
    return box;
  }

  let doneEl = null, doneTimer = 0;
  function skDone(message, opts) {
    opts = opts || {};
    if (!doneEl) {
      doneEl = el('div', 'kit-done');
      doneEl.setAttribute('role', 'status');
      doneEl.setAttribute('aria-live', 'polite');
      document.body.appendChild(doneEl);
    }
    doneEl.replaceChildren(el('span', null, message));
    for (const [label, fn] of [['Undo', opts.undo], ['History', opts.history]]) {
      if (!fn) continue;
      const b = el('button', null, label);
      b.type = 'button';
      b.addEventListener('click', () => { doneEl.hidden = true; fn(); });
      doneEl.append(b);
    }
    doneEl.hidden = false;
    clearTimeout(doneTimer);
    doneTimer = setTimeout(() => { doneEl.hidden = true; }, opts.ms || 6000);
    return doneEl;
  }

  Object.assign(window, { skActionBar, skSegmented, skEmpty, skDone, SK_CHIPS });
})();
