/* =============================================================================
   i18n.js — the interface in English, Italiano or Français (v2.7.0)

   The interface is translated by the English text itself: static/i18n/<lang>.json
   maps an English string to its translation.  A string with a changing part is
   a pattern: {0}, {1} … are the parts in order ("{0} functions").  Text,
   tooltips and placeholders are swapped as the page is drawn (a MutationObserver
   follows what the tools build), so no tool needed changing.  What has no
   translation stays English.  Only the interface is translated: shows, reports,
   PDFs and the wiki stay as they are.
   ============================================================================= */

'use strict';

const I18N = (() => {
  const LANGS = [['en', 'English'], ['it', 'Italiano'], ['fr', 'Français']];
  const ATTRS = ['title', 'placeholder', 'data-tip', 'data-desc', 'data-tooltip', 'aria-label', 'alt'];
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'NOSCRIPT']);
  let lang = 'en';
  let dict = Object.create(null);        // normalised English → translation
  let patterns = [];                     // [{re, tpl, n}]
  let observer = null;
  const norm = s => String(s).replace(/ /g, ' ').replace(/\s+/g, ' ').trim();

  function _compile(d) {
    const ex = Object.create(null), pats = [];
    for (const [k, v] of Object.entries(d)) {
      if (!v || k.startsWith('_')) continue;
      const key = norm(k);
      if (/\{\d+\}/.test(key)) {
        const parts = key.split(/\{\d+\}/);
        const lit = parts.join('').replace(/\s/g, '').length;
        if (!lit) continue;                 // a pattern of nothing but parts would match everything
        const re = new RegExp('^' + parts.map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('(.*?)') + '$', 's');
        pats.push({ re, tpl: v, lit });
      } else {
        ex[key] = v;
      }
    }
    pats.sort((a, b) => b.lit - a.lit);  // the most specific pattern first
    return [ex, pats];
  }

  /** Translate one string (the whole text of a node, an attribute, a message). */
  function t(s, ...vars) {
    if (s == null) return s;
    const str = String(s);
    let out = str;
    if (lang !== 'en') {
      const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(str);
      const core = norm(m[2]);
      if (core) {
        let tr = dict[core];
        if (tr === undefined) {
          for (const p of patterns) {
            const mm = p.re.exec(core);
            if (mm) { tr = p.tpl.replace(/\{(\d+)\}/g, (_x, i) => mm[+i + 1] ?? ''); break; }
          }
        }
        if (tr === undefined) {              // a numbered label: "1. The rig", "2) Setlist"
          const pm = /^(\d+[.)]\s+)(.+)$/.exec(core);
          if (pm) { const rest = t(pm[2]); if (rest !== pm[2]) tr = pm[1] + rest; }
        }
        if (tr !== undefined) out = m[1] + tr + m[3];
      }
    }
    return vars.length ? out.replace(/\{(\d+)\}/g, (_x, i) => vars[+i] ?? '') : out;
  }

  // ── DOM ────────────────────────────────────────────────────────────────────
  function _skip(el) {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      if (SKIP_TAGS.has(e.tagName) || e.getAttribute('data-i18n') === 'off' || e.isContentEditable) return true;
    }
    return false;
  }

  function _text(node) {
    const rec = node.__i18n;
    if (rec && node.nodeValue === rec.out) return;        // our own change
    const src = node.nodeValue;
    if (!src || !src.trim()) return;
    const par = node.parentElement;
    if (par && _skip(par)) return;
    const out = t(src);
    if (out !== src || rec) {
      if (par && par.tagName === 'OPTION' && !par.hasAttribute('value')) par.setAttribute('value', norm(src));
      node.__i18n = { src, out };
      node.nodeValue = out;
    } else {
      node.__i18n = { src, out: src };
    }
  }

  function _attrs(el) {
    if (_skip(el)) return;
    const rec = el.__i18na || (el.__i18na = {});
    for (const a of ATTRS) {
      if (!el.hasAttribute(a)) continue;
      const cur = el.getAttribute(a), r = rec[a];
      if (r && cur === r.out) continue;
      const out = t(cur);
      rec[a] = { src: cur, out };
      if (out !== cur) el.setAttribute(a, out);
    }
  }

  function _walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { _text(root); return; }
    if (root.nodeType !== 1 || SKIP_TAGS.has(root.tagName)) return;
    _attrs(root);
    for (let n = root.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) _text(n);
      else if (n.nodeType === 1) _walk(n);
    }
  }

  /** After a language switch: every node again, from the English it came from. */
  function _reapply() {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let n = w.nextNode(); n; n = w.nextNode()) nodes.push(n);
    for (const n of nodes) {
      if (n.nodeType === 3) {
        const rec = n.__i18n;
        if (rec && n.nodeValue === rec.out) n.nodeValue = rec.src;   // back to English first
        n.__i18n = undefined;
        _text(n);
      } else {
        const rec = n.__i18na;
        if (rec) for (const a of Object.keys(rec)) if (n.getAttribute(a) === rec[a].out) n.setAttribute(a, rec[a].src);
        n.__i18na = undefined;
        _attrs(n);
      }
    }
    document.documentElement.lang = lang;
    document.title = t('⚡ QLC+ Swiss Knife');
  }

  function _observe() {
    if (observer) return;
    observer = new MutationObserver(recs => {
      for (const r of recs) {
        if (r.type === 'childList') r.addedNodes.forEach(n => _walk(n));
        else if (r.type === 'characterData') _text(r.target);
        else if (r.type === 'attributes') _attrs(r.target);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTRS });
  }

  function _load(code) {
    if (code === 'en') return {};
    try {                                  // synchronous: the page is never seen half-translated
      const x = new XMLHttpRequest();
      x.open('GET', `/static/i18n/${code}.json?v=${window.__ASSET_V || ''}`, false);
      x.send();
      if (x.status === 200) return JSON.parse(x.responseText);
    } catch { /* stays English */ }
    return {};
  }

  function set(code, remember = true) {
    if (!LANGS.some(l => l[0] === code)) code = 'en';
    lang = code;
    [dict, patterns] = _compile(_load(code));
    if (remember) { try { localStorage.setItem('sk-lang', code); } catch { /* per-browser convenience only */ } }
    _reapply();
    const sel = document.getElementById('lang-select');
    if (sel) sel.value = code;
  }

  function init() {
    let code = 'en';
    try { code = localStorage.getItem('sk-lang') || 'en'; } catch { /* default */ }
    // dialogs: alert / confirm / prompt speak the language too
    const _a = window.alert.bind(window), _c = window.confirm.bind(window), _p = window.prompt.bind(window);
    window.alert = m => _a(t(m));
    window.confirm = m => _c(t(m));
    window.prompt = (m, d) => _p(t(m), d);
    set(code, false);
    _observe();
  }

  return { init, set, t, get lang() { return lang; }, LANGS, _compile };
})();

/** Short form for code that builds a message: t('Saved {0}', name) */
function t(s, ...vars) { return I18N.t(s, ...vars); }

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => I18N.init());
else I18N.init();
