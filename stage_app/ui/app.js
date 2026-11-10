/* QLC+ Stage Monitor: the window.  Talks only to its own control server (stage_app/control.py). */
'use strict';

const TOKEN = document.querySelector('meta[name="token"]').content;
const LANG_NAMES = {en: 'English', it: 'Italiano', fr: 'Français', de: 'Deutsch', es: 'Español',
  pt: 'Português', ja: '日本語', zh: '中文'};
let WORDS = {};
let S = null;            // the last state
let qrFor = '';
let busy = false;

const $ = id => document.getElementById(id);

function t(s, ...args) {
  let out = WORDS[s] || s;
  args.forEach((a, i) => { out = out.split('{' + i + '}').join(String(a)); });
  return out;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function api(path, body) {
  const opt = {headers: {'X-Token': TOKEN, 'Content-Type': 'application/json'}};
  if (body !== undefined) { opt.method = 'POST'; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (d.state) draw(d.state);
    throw new Error(d.error || 'Something went wrong.');
  }
  return d;
}

function toast(msg) {
  const box = $('toast');
  box.textContent = msg;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 4000);
}

async function setLang(lang) {
  WORDS = lang === 'en' ? {} : await api('/api/i18n?lang=' + encodeURIComponent(lang));
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-t]').forEach(e => {
    if (!e.dataset.en) e.dataset.en = e.textContent.trim();
    e.textContent = t(e.dataset.en);
  });
  document.querySelectorAll('[data-t-ph]').forEach(e => {
    if (!e.dataset.enPh) e.dataset.enPh = e.placeholder;
    e.placeholder = t(e.dataset.enPh);
  });
  if (S) draw(S);
}

// ── drawing ─────────────────────────────────────────────────────────────────
function drawPage(s) {
  const box = $('page');
  box.textContent = '';
  const inp = $('folder');
  if (document.activeElement !== inp) inp.value = s.folder || '';
  $('pick').hidden = !s.can_pick;
  if (s.error) { box.append(el('div', 'err', t(s.error))); return; }
  if (!s.page) { box.append(el('div', 'hint', t('Choose the folder that the Stage Monitor of QLC+ Swiss Knife exported (the stage_monitor folder next to the show).'))); return; }
  const p = s.page;
  box.append(el('div', 'title', p.title || t('Stage Monitor')));
  const ul = el('ul');
  p.lists.forEach(l => ul.append(el('li', '', t('{0}: {1} songs', l.label, l.songs) + (l.mode === 'control' ? ' · ' + t('with Previous and Next buttons') : ''))));
  box.append(ul);
  if (p.show_name) box.append(el('div', 'hint', t('Exported from {0}', p.show_name)));
}

const QLC = {
  unknown: ['', 'Checking QLC+…', ''],
  off: ['bad', 'QLC+ is not running', 'Start QLC+ with web access (qlcplus -w) and open the show.'],
  no_web: ['bad', 'QLC+ runs without web access', 'Close QLC+ and start it again with web access (qlcplus -w). The tablet cannot reach it now.'],
  not_qlc: ['bad', 'Another program uses port {0}', 'QLC+ answers on port {0} when it runs with web access. Close the other program, or export the page from Swiss Knife with another QLC+ port.'],
  other_show: ['warn', 'QLC+ has another show open', 'Not found in QLC+: {1}. Open the show this page was exported from.'],
  ready: ['ok', 'QLC+ is ready', 'Web access on port {0}; every cue list of the page is in the open show.'],
};

function drawQlc(s) {
  const q = s.qlc || {state: 'unknown'};
  const [cls, head, hint] = QLC[q.state] || QLC.unknown;
  $('qlc-dot').className = 'dot ' + cls;
  $('qlc-head').textContent = t(head, q.port);
  let h = t(hint, q.port, (q.missing_labels || []).join(', '));
  if (q.state === 'other_show' && s.page && s.page.show_name) h += ' ' + t('The page comes from {0}.', s.page.show_name);
  if (q.state === 'ready' && !s.page) h = t('Web access on port {0}.', q.port);
  $('qlc-hint').textContent = h;
}

function urlRow(u, withQr, role) {
  const row = el('div', 'row');
  const inp = el('input', 'url');
  inp.readOnly = true;
  inp.value = u;
  inp.addEventListener('focus', () => inp.select());
  const copy = el('button', 'btn btn-sm', t('Copy'));
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(u); toast(t('Copied')); }
    catch (e) { inp.focus(); inp.select(); }
  });
  const open = el('button', 'btn btn-sm', t('Open here'));
  open.title = t('Open the page in this computer\'s browser');
  open.addEventListener('click', () => act(async () => { await api('/api/open', {role: role || ''}); }));
  row.append(inp, copy, open);
  if (withQr) {
    const b = el('button', 'btn btn-sm', t('QR code'));
    b.addEventListener('click', () => { qrFor = u; drawServer(S); });
    row.append(b);
  }
  return row;
}

function drawServer(s) {
  const sv = s.server || {};
  const box = $('server');
  box.textContent = '';
  $('start').hidden = !!sv.running;
  $('stop').hidden = !sv.running;
  $('start').disabled = !s.page || busy;
  if (!sv.running) {
    const ips = sv.addresses || [];
    box.append(el('div', 'hint', ips.length ? t('This computer: {0}', ips.join(', '))
      : t('No network address found. Join or create a Wi-Fi network first (on a Mac: Internet Sharing to Wi-Fi).')));
    if (s.page) box.append(el('div', 'hint', t('The page is served on port {0}.', s.page.http_port)));
    if (sv.error) box.append(el('div', 'err', t(sv.error)));
    return;
  }
  const urls = sv.urls && sv.urls.length ? sv.urls : [`http://localhost:${sv.port}/`];
  box.append(el('div', 'hint', t('Open this address on the tablet, with http://')));
  const list = el('div', 'urls');
  urls.forEach(u => list.append(urlRow(u, true)));
  box.append(list);
  const views = (s.page && s.page.views) || [];
  if (views.length) {
    box.append(el('div', 'hint', t('A view for each player:')));
    const vl = el('div', 'views');
    views.forEach(v => {
      const r = urlRow(urls[0] + '?role=' + encodeURIComponent(v.id), true, v.id);
      r.prepend(el('span', 'view-label', v.label));
      vl.append(r);
    });
    box.append(vl);
  }
  if (!qrFor || !qrFor.startsWith(urls[0])) qrFor = urls[0];
  const qr = el('div', 'qr');
  qr.append(el('div', 'hint', t('Scan with the tablet camera:')));
  const img = el('img');
  img.alt = qrFor;
  img.src = '/api/qr?text=' + encodeURIComponent(qrFor);
  qr.append(img, el('code', '', qrFor));
  box.append(qr);
  if (sv.https_from) box.append(el('div', 'warnbox', t('{0} asked for https://. On that device type the address with http://, as shown above.', sv.https_from)));
}

function drawUpdate(s) {
  const u = s.update;
  $('upd-row').hidden = !u;
  if (!u) { $('sec-update').hidden = true; return; }
  $('upd-on').checked = !!u.enabled;
  $('upd-note').textContent = u.error ? t(u.error) : '';
  const show = !!(u.enabled && u.newer);
  $('sec-update').hidden = !show;
  if (!show) return;
  $('upd-head').textContent = t('QLC+ Stage Monitor {0} is out.', u.latest);
  let hint = t('You have {0}.', u.current);
  const canInstall = u.can_install && u.asset && !u.pending;
  if (u.pending) hint += ' ' + t('The download for this computer is still being prepared on GitHub (about 15 minutes after a release). Check again in a few minutes.');
  else if (!u.frozen) hint += ' ' + t('Run from the sources: update with git pull.');
  else if (u.can_install && !u.asset) hint += ' ' + t('This release has no download for this computer.');
  else if (canInstall) hint += ' ' + t('Update and restart downloads it, checks it and starts the new version; the folder stays chosen.');
  $('upd-hint').textContent = hint;
  $('upd-install').hidden = !canInstall;
  $('upd-install').disabled = busy;
}

function draw(s) {
  S = s;
  drawUpdate(s);
  drawPage(s);
  drawQlc(s);
  drawServer(s);
  $('print').disabled = !s.page || busy;
  $('version').textContent = `${s.app} ${s.version}`;
  const sel = $('lang');
  if (!sel.options.length) {
    s.langs.forEach(l => { const o = el('option', '', LANG_NAMES[l] || l); o.value = l; sel.append(o); });
  }
  sel.value = s.lang;
}

// ── actions ─────────────────────────────────────────────────────────────────
async function act(fn) {
  if (busy) return;
  busy = true;
  try { await fn(); }
  catch (e) { toast(t(e.message)); }
  finally { busy = false; if (S) draw(S); }
}

async function refresh(force) {
  try { draw(await api('/api/state' + (force ? '?force=1' : ''))); }
  catch (e) { /* the next tick */ }
}

$('folder').addEventListener('change', e => act(async () => draw(await api('/api/folder', {folder: e.target.value}))));
$('pick').addEventListener('click', () => act(async () => draw(await api('/api/pick', {}))));
$('recheck').addEventListener('click', () => refresh(true));
$('start').addEventListener('click', () => act(async () => draw(await api('/api/start', {}))));
$('stop').addEventListener('click', () => act(async () => draw(await api('/api/stop', {}))));
$('lang').addEventListener('change', e => act(async () => { draw(await api('/api/lang', {lang: e.target.value})); await setLang(e.target.value); }));
$('print').addEventListener('click', () => act(async () => {
  const d = await api('/api/print', {layout: $('layout').value});
  let msg = d.opened ? t('Saved as {0} in the page folder and opened: print it from there.', d.name)
    : t('Saved as {0} in the page folder.', d.name);
  if (d.unprintable) msg += ' ' + t('Some names use letters the PDF fonts cannot print; they show as ?.');
  $('printed').textContent = msg;
}));

$('upd-on').addEventListener('change', e => act(async () => draw(await api('/api/update/enable', {check: e.target.checked}))));
$('upd-now').addEventListener('click', () => act(async () => {
  const s = await api('/api/update/check', {});
  draw(s);
  if (s.update && !s.update.error && !s.update.newer) toast(t('You already have the latest version.'));
}));
$('upd-open').addEventListener('click', () => act(async () => { await api('/api/update/open', {}); }));
$('upd-install').addEventListener('click', () => act(async () => {
  $('upd-hint').textContent = t('Downloading and checking the new version…');
  const d = await api('/api/update/install', {});
  $('upd-hint').textContent = d.restart ? t('The new version is ready: QLC+ Stage Monitor quits and starts again.') : t(d.message || '');
}));

(async function init() {
  try {
    const s = await api('/api/state');
    await setLang(s.lang);
    draw(s);
  } catch (e) { /* drawn on the next tick */ }
  setInterval(() => { if (!busy) refresh(false); }, 3000);
})();
