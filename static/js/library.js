/* =============================================================================
   library.js — the community library (v2.7.0)
   Share templates, palettes, presets, naming profiles, VC styles and Show
   Profiles as one plain file; install what someone shared.  Local files only.
   ============================================================================= */

'use strict';

let _libS = null;           // /api/library/state
let _libPV = null;          // preview of the opened file

async function libInit() {
  const d = await _apiJson('/api/library/state');
  if (d.error) { setStatus(d.error, 'error'); return; }
  _libS = d;
  _libRenderItems();
  const fb = document.getElementById('lib-open-fallback');
  if (fb) fb.style.display = document.body.classList.contains('no-native-picker') ? '' : 'none';
}

function _libKindLabel(id) {
  const k = (_libS?.kinds || []).find(x => x.id === id);
  return k ? k.label : id;
}

function _libRenderItems() {
  const el = document.getElementById('lib-items');
  if (!el || !_libS) return;
  if (!_libS.items.length) {
    el.innerHTML = '<div class="porter-placeholder">You have nothing to share yet. Save a VC page as a template (VC Visual Editor), a palette or preset (Look Builder), or a Show Profile (History › Do it again) — it shows up here.</div>';
    return;
  }
  let out = '', last = '';
  _libS.items.forEach((it, i) => {
    if (it.kind !== last) { out += `<div class="lib-kind">${_esc(_libKindLabel(it.kind))}</div>`; last = it.kind; }
    out += `<label class="lib-row"><input type="checkbox" class="lib-pick" data-i="${i}">
      <span>${_esc(it.name)}</span><span class="vce-hint">${_esc(it.summary)}</span>
      ${it.private ? '<span class="lib-warn" title="This profile names a folder of this computer. Anyone who gets it sees that path.">⚠ has a folder path</span>' : ''}</label>`;
  });
  el.innerHTML = out;
}

async function libSave() {
  const picks = [...document.querySelectorAll('.lib-pick:checked')].map(c => _libS.items[+c.dataset.i]);
  if (!picks.length) { setStatus('Tick at least one item to share.', 'warn'); return; }
  const r = await fetch('/api/library/pack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selection: picks.map(p => ({ kind: p.kind, name: p.name })),
      title: document.getElementById('lib-title').value, author: document.getElementById('lib-author').value,
      description: document.getElementById('lib-desc').value }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Could not make the library file.', 'error'); return; }
  const blob = new Blob([JSON.stringify(d.pack, null, 1)], { type: 'application/json' });
  const name = await saveFileWithPicker(blob, d.filename, null, 'Save the library file');
  if (name) {
    setStatus(`Library file saved (${d.items} item${d.items === 1 ? '' : 's'}): ${name}. Send that one file to anyone — they open it in Library › Get.`, 'ok');
    const n = document.getElementById('lib-save-note'); if (n) n.textContent = '✓ ' + name;
  }
}

async function libOpen() {
  const p = await nativePick('A library file (.qsklib.json)', [{ label: 'Swiss Knife library', exts: ['.json'] }]);
  if (p) return _libRead({ path: p });
  if (nativePick.unavailable) setStatus('Use “Choose file…” to pick the library file.', 'warn');
}

function libOpenInput(inp) {
  const f = inp.files && inp.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = () => _libRead({ text: String(rd.result) });
  rd.readAsText(f);
  inp.value = '';
}

async function _libRead(body) {
  const r = await fetch('/api/library/read', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Could not read the file.', 'error'); _libPV = null; _libRenderPreview(); return; }
  _libPV = d;
  _libRenderPreview();
}

const _LIB_STATUS = { new: 'new', same: 'you have it', exists: 'name taken', reserved: 'built-in name', invalid: 'refused' };

function _libRenderPreview() {
  const el = document.getElementById('lib-preview'), btn = document.getElementById('lib-install-btn');
  if (!el) return;
  const P = _libPV;
  if (!P) {
    el.innerHTML = '<div class="porter-placeholder">Open a <code>.qsklib.json</code> file: you see what is in it and what is new to you before anything is installed.</div>';
    if (btn) btn.disabled = true;
    return;
  }
  const head = `<div class="lib-head"><b>${_esc(P.title || 'Library')}</b>${P.author ? ' · by ' + _esc(P.author) : ''}
    ${P.swiss_knife ? `<span class="vce-hint"> · made with Swiss Knife ${_esc(P.swiss_knife)}</span>` : ''}
    ${P.description ? `<div class="vce-hint">${_esc(P.description)}</div>` : ''}</div>`;
  const rows = P.items.map(it => {
    let pick = '';
    if (it.status === 'new') {
      pick = `<select class="lib-sel" data-i="${it.index}"><option value="install">Install</option><option value="skip">Leave out</option></select>`;
    } else if (it.status === 'exists') {
      pick = `<select class="lib-sel" data-i="${it.index}"><option value="skip">Keep mine</option><option value="replace">Replace mine</option><option value="copy">Keep both</option></select>`;
    } else if (it.status === 'reserved') {
      pick = `<select class="lib-sel" data-i="${it.index}"><option value="skip">Skip</option><option value="copy">Keep it under another name</option></select>`;
    }
    return `<tr><td>${_esc(_libKindLabel(it.kind))}</td><td>${_esc(it.name)}<div class="vce-hint">${_esc(it.summary)}</div>
      ${it.warning ? `<div class="lib-warn">⚠ ${_esc(it.warning)}</div>` : ''}${it.reason ? `<div class="vce-hint">${_esc(it.reason)}</div>` : ''}</td>
      <td><span class="lib-st ${it.status}">${_esc(_LIB_STATUS[it.status] || it.status)}</span></td><td>${pick}</td></tr>`;
  }).join('');
  el.innerHTML = head + `<table class="tbl"><thead><tr><th>Kind</th><th>Item</th><th></th><th>What to do</th></tr></thead><tbody>${rows}</tbody></table>`;
  const any = P.items.some(i => i.status === 'new' || i.status === 'exists' || i.status === 'reserved');
  if (btn) btn.disabled = !any;
}

async function libInstall() {
  if (!_libPV) return;
  const choices = {};
  document.querySelectorAll('.lib-sel').forEach(s => { if (s.value !== 'install') choices[s.dataset.i] = s.value; });
  const r = await fetch('/api/library/install', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choices, default: 'skip' }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Install failed.', 'error'); return; }
  const bits = [];
  if (d.installed) bits.push(`${d.installed} installed`);
  if (d.replaced) bits.push(`${d.replaced} replaced`);
  if (d.copied) bits.push(`${d.copied} kept under another name`);
  if (d.skipped) bits.push(`${d.skipped} skipped`);
  if (d.refused) bits.push(`${d.refused} refused`);
  setStatus('Library: ' + (bits.join(', ') || 'nothing to do') + '.', d.refused ? 'warn' : 'ok');
  _libPV = null;
  _libRenderPreview();
  libInit();
  // what a tool listed before the install is stale now
  ['invalidateLooks', 'invalidateVcEditor'].forEach(f => { if (typeof window[f] === 'function') window[f](); });
}

function libFolders() {
  if (!_libS) return;
  const rows = Object.entries(_libS.folders).map(([k, v]) => `${k}: ${v}`).join('\n');
  const el = document.getElementById('lib-preview');
  if (el) el.innerHTML = `<div class="lib-head"><b>Where your items are</b></div><pre class="vce-hint" style="white-space:pre-wrap;user-select:all">${_esc(rows)}</pre>`;
}
