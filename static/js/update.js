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
  _upd = d;
  const cb = document.getElementById('upd-enabled');
  if (cb) cb.checked = !!d.enabled;
  if (d.newer) {
    const b = document.getElementById('update-badge');
    document.getElementById('update-badge-v').textContent = `v${d.latest} available`;
    if (b) b.hidden = false;
  }
}

function updToggle(open) {
  const card = document.getElementById('upd-card');
  if (!card || !_upd || !_upd.newer) return;
  const show = open === undefined ? card.hidden : open;
  card.hidden = !show;
  if (!show) return;
  document.getElementById('upd-title').textContent = `Swiss Knife v${_upd.latest} is out`;
  document.getElementById('upd-sub').textContent = _upd.can_install
    ? `You have v${_upd.current}. Update and restart downloads the new version, checks it and starts it again — your shows and settings are not touched.`
    : (_upd.frozen
        ? `You have v${_upd.current}. Download the new version from the release page.`
        : `You have v${_upd.current}, run from the sources: update with  git pull  (then restart), or download the release.`);
  document.getElementById('upd-notes').textContent = _upd.notes || '';
  document.getElementById('upd-install').hidden = !(_upd.can_install && _upd.asset);
  document.getElementById('upd-msg').textContent = '';
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
