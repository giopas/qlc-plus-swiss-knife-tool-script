/* =============================================================================
   update.js — "a newer version is out" (v2.8.0)
   Once at start the app asks GitHub for the latest release (switch it off with
   the box under the menu).  A header badge opens the card: what is new, and
   Update and restart (packaged app) or what to do (run from sources).
   ============================================================================= */

'use strict';

let _upd = null;

async function updInit() {
  let d;
  try { d = await (await fetch('/api/update/check')).json(); } catch { return; }
  _updApply(d);
}

function _updApply(d) {
  _upd = d;
  const cb = document.getElementById('upd-enabled');
  if (cb) cb.checked = !!d.enabled;
  const m = document.getElementById('upd-now-msg');
  if (m && d.error) m.textContent = _net.state === 'offline' ? t('Could not check for updates: this computer is offline.') : d.error;
  const b = document.getElementById('update-badge');
  if (d.newer) {
    document.getElementById('update-badge-v').textContent = `v${d.latest} available`;
    if (b) b.hidden = false;
  } else if (b) b.hidden = true;
}

/** "Check now": ask GitHub again, ignoring the answer remembered from the last hours. */
async function updCheckNow() {
  const m = document.getElementById('upd-now-msg');
  if (m) m.textContent = t('Checking…');
  let d;
  try { d = await (await fetch('/api/update/check?force=1')).json(); }
  catch { if (m) m.textContent = t('Could not check for updates.'); return; }
  _updApply(d);
  if (d.error) { netCheck(true); if (m) m.textContent = _net.state === 'offline' ? t('Could not check for updates: this computer is offline.') : d.error; return; }
  if (d.newer) { if (m) m.textContent = ''; updToggle(true); }
  else if (m) m.textContent = t('You have the latest version (v{0}).', d.current);
}

function updToggle(open) {
  const card = document.getElementById('upd-card');
  if (!card || !_upd || !_upd.newer) return;
  const show = open === undefined ? card.hidden : open;
  card.hidden = !show;
  if (!show) return;
  document.getElementById('upd-title').textContent = `Swiss Knife v${_upd.latest} is out`;
  document.getElementById('upd-sub').textContent = _upd.pending
    ? t('You have v{0}. The download for this computer is still being prepared on GitHub (about 15 minutes after a release). Press Check now in a few minutes, or open the release page.', _upd.current)
    : _upd.can_install
    ? `You have v${_upd.current}. Update and restart downloads the new version, checks it and starts it again — your shows and settings are not touched.`
    : (_upd.frozen
        ? `You have v${_upd.current}. Download the new version from the release page.`
        : `You have v${_upd.current}, run from the sources: update with  git pull  (then restart), or download the release.`);
  document.getElementById('upd-notes').innerHTML = _updNotes(_upd.notes || '');
  document.getElementById('upd-install').hidden = !(_upd.can_install && _upd.asset);
  document.getElementById('upd-msg').textContent = '';
}

// The release notes are Markdown: headings, bold, italics, code and bullets are shown as such
// (3.14.1; they were shown as raw text).  The text is escaped first, so nothing in it can run.
function _updNotes(md) {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, '$1<i>$2</i>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  return md.split('\n').filter(l => !/^\s*-{3,}\s*$/.test(l)).map(l => {
    const h = l.match(/^#{1,6}\s+(.*)$/);
    if (h) return `<b class="upd-h">${inline(h[1])}</b>`;
    const li = l.match(/^\s*[-*]\s+(.*)$/);
    if (li) return `<span class="upd-li">• ${inline(li[1])}</span>`;
    return inline(l);
  }).join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

async function updOpen() {
  try {
    await fetch('/api/update/open', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                     body: JSON.stringify({url: _upd && _upd.url})});
  } catch { /* the page link is also in the card text */ }
}

async function updInstall() {
  const msg = document.getElementById('upd-msg');
  const btn = document.getElementById('upd-install');
  if (_show && _show.active && _show.unsaved && !confirm('The show in progress has unsaved changes. Update and restart anyway? (They would be lost — Save as new file… first.)')) return;
  btn.disabled = true;
  msg.textContent = 'Downloading…';
  try {
    const r = await fetch('/api/update/install', {method: 'POST'});
    const d = await r.json();
    msg.textContent = d.message || (r.ok ? 'Done.' : 'Failed.');
    if (!r.ok) btn.disabled = false;
  } catch {
    msg.textContent = 'The app is restarting…';
  }
}

async function updSetEnabled(on) {
  try {
    await fetch('/api/update/settings', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                         body: JSON.stringify({check: !!on})});
  } catch { /* stays as it was */ }
  if (!on) { const b = document.getElementById('update-badge'); if (b) b.hidden = true; }
  else updInit();
}

setTimeout(updInit, 1500);

/* ── 3.11.0: is this computer online? ───────────────────────────────────────
   Claude Desktop needs the internet even when the MCP server is connected (the
   server runs here, Claude does not).  Green: claude.ai answers.  Orange:
   something answers but not claude.ai, or slowly.  Red: offline. */
let _net = { state: 'unknown' };
const NET_TEXT = {
  online: 'Internet: online. Claude can be reached.',
  limited: 'Internet: limited. This network works, but claude.ai does not answer, or answers slowly. Claude may not work.',
  offline: 'Internet: offline. Claude needs the internet, even when the MCP is connected.',
  unknown: 'Internet: not checked yet.',
};
async function netCheck(force) {
  try { _net = await (await fetch('/api/net/status' + (force ? '?force=1' : ''))).json(); }
  catch { _net = { state: 'unknown' }; }
  const txt = t(NET_TEXT[_net.state] || NET_TEXT.unknown);
  document.querySelectorAll('[data-net]').forEach(el => {
    el.className = 'net-dot net-' + (_net.state || 'unknown');
    el.title = txt; el.setAttribute('aria-label', txt);
  });
  const line = document.getElementById('net-text');
  if (line) line.textContent = txt;
}
setTimeout(() => netCheck(false), 1200);
setInterval(() => { if (!document.hidden) netCheck(false); }, 30000);
window.addEventListener('online', () => netCheck(true));
window.addEventListener('offline', () => netCheck(true));
