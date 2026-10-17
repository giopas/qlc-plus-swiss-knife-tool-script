/**
 * Stage Monitor (3.5.0).
 *
 * A page for a tablet on stage that shows the current and the next cue of the
 * chosen CueLists, live from QLC+.  /api/stagemon/lists reads the show (only
 * reads it); every change here is kept in <show>.stage.json; Export writes
 * index.html + serve_stage.py; Serve shares the folder on the network.
 */

let _sm = null;              // {lists, config, missing, new, folder, server, ...}
let _smOpen = new Set();     // CueList ids whose step table is open
let _smSaveT = null;

function stagemonInit() {
  if (!_sm) stagemonLoad();
  else _smStatus();
}

// the cards keep show names untranslated (data-i18n="off"): draw them again in a new language
document.addEventListener('sk-lang', () => { if (_sm) _smRender(); });

function invalidateStagemon() {
  _sm = null;
  const el = document.getElementById('sm-lists');
  if (el) el.innerHTML = '<div class="porter-placeholder">Open a workspace with a CueList on its Virtual Console.</div>';
  if (document.getElementById('scr-stagemon')?.classList.contains('active')) stagemonLoad();
}

async function stagemonLoad() {
  try {
    const r = await fetch('/api/stagemon/lists');
    const d = await r.json();
    if (!r.ok) { _sm = null; _smSync(); return; }
    _sm = d;
    _smRender();
  } catch (e) { /* no workspace */ }
}

const _smCfg = () => _sm.config;
const _smItem = id => _smCfg().lists.find(x => x.id === String(id));
const _smList = id => _sm.lists.find(x => x.id === String(id));

function _smWhere(cl) {
  const parts = [...cl.path];
  if (cl.frame_page) parts.push(cl.frame_page.name || `page ${cl.frame_page.page + 1}`);
  return parts.join(' › ');
}

function _smRender() {
  if (!_sm) return;
  const cfg = _smCfg();
  const el = document.getElementById('sm-lists');
  const note = document.getElementById('sm-notice');
  const warn = [];
  if (_sm.missing.length)
    warn.push(_esc(`Gone from the show since the last export: ${_sm.missing.map(m => m.label || m.id).join(', ')}`));
  if (_sm.new.length && _sm.saved)
    warn.push(_esc(`New in the show, not on the page yet: ${_sm.new.map(id => (_smList(id) || {}).caption || id).join(', ')}`));
  note.innerHTML = warn.map(w => `<div class="sm-warn">${w}</div>`).join('');

  if (!_sm.lists.length) {
    el.innerHTML = `<div class="porter-placeholder">${_esc('This show has no CueList on its Virtual Console. Add one with the Setlist or the VC Visual Editor.')}</div>`;
    _smSettings(); _smSync(); return;
  }
  // chosen lists first, in the page's order; then the others in the show's order
  const chosen = cfg.lists.map(x => _smList(x.id)).filter(Boolean);
  const others = _sm.lists.filter(c => !_smItem(c.id));
  el.innerHTML = [...chosen, ...others].map(cl => {
    const it = _smItem(cl.id);
    const on = !!it;
    const pos = on ? cfg.lists.indexOf(it) : -1;
    const ch = cl.chaser ? _esc(cl.chaser.name) : `<span class="doc-error">${_esc(t('no chaser'))}</span>`;
    const ins = Object.entries(cl.inputs || {}).map(([k, v]) => `${_esc(k)}: ${_esc(v.join(', '))}`).join(' · ');
    const hidden = on ? Object.values(it.steps).filter(s => s.hide).length : 0;
    let cfgHtml = '';
    if (on) {
      cfgHtml = `<div class="sm-cfg">
        <input class="field-input" maxlength="80" value="${_esc(it.label)}" placeholder="${_esc(cl.caption || 'Label on the page')}" data-i18n="${cl.caption ? 'off' : ''}"
               oninput="stagemonList('${cl.id}', 'label', this.value)" title="Label on the page (the CueList's caption when empty)">
        <select class="field-input" style="width:auto" onchange="stagemonList('${cl.id}', 'mode', this.value)"
                title="Read-only: the tablet only shows the cues; nothing on it changes the show. Control: the page also has Previous and Next buttons that move this cue list in QLC+, like the pedal, each after a long press.">
          <option value="read"${it.mode === 'read' ? ' selected' : ''}>${_esc('Read-only: shows the cues')}</option>
          <option value="control"${it.mode === 'control' ? ' selected' : ''}>${_esc('Control: adds Previous / Next (hold)')}</option>
        </select>
        <button class="btn btn-surface btn-sm sm-ord" onclick="stagemonMove('${cl.id}', -1)" ${pos <= 0 ? 'disabled' : ''} title="Earlier on the page">↑</button>
        <button class="btn btn-surface btn-sm sm-ord" onclick="stagemonMove('${cl.id}', 1)" ${pos >= cfg.lists.length - 1 ? 'disabled' : ''} title="Later on the page">↓</button>
        <button class="btn btn-surface btn-sm" onclick="stagemonSteps('${cl.id}')">${_smOpen.has(cl.id) ? '▾' : '▸'} <span>${_esc('Steps')}</span>${hidden ? ` <span>${_esc(`(${hidden} hidden)`)}</span>` : ''}</button>
      </div>`;
      if (_smOpen.has(cl.id)) cfgHtml += _smStepsTable(cl, it);
    }
    return `<div class="sm-cl${on ? ' on' : ''}">
      <label class="sm-cl-h">
        <input type="checkbox" ${on ? 'checked' : ''} ${cl.chaser ? '' : 'disabled'} onchange="stagemonTick('${cl.id}', this.checked)">
        <span class="sm-cap" data-i18n="off">${_esc(cl.caption || `CueList ${cl.id}`)}</span>
        <span class="doc-chip">${_esc(`${cl.steps.length} steps`)}</span>
        <span class="doc-chip" title="Widget ID">#${_esc(cl.id)}</span>
      </label>
      <div class="sm-meta" data-i18n="off">${_esc(_smWhere(cl))} · ${ch}${ins ? `<br>${ins}` : ''}</div>
      ${cfgHtml}
    </div>`;
  }).join('');
  _smSettings();
  _smSync();
}

function _smStepsTable(cl, it) {
  const rows = cl.steps.map(st => {
    const s = it.steps[String(st.index)] || {};
    return `<tr class="${s.hide ? 'sm-hidden' : ''}">
      <td><input type="checkbox" ${s.hide ? '' : 'checked'} title="Show this step on the page"
                 onchange="stagemonStep('${cl.id}', ${st.index}, 'hide', !this.checked)"></td>
      <td class="sm-n">${st.index + 1}</td>
      <td class="sm-fn" data-i18n="off">${_esc(st.name)}${st.note ? `<div class="sm-meta" style="margin:0">${_esc(st.note)}</div>` : ''}</td>
      <td><input class="field-input" maxlength="120" value="${_esc(s.label || '')}" placeholder="${_esc('Name on the page')}"
                 oninput="stagemonStep('${cl.id}', ${st.index}, 'label', this.value)"></td>
    </tr>`;
  }).join('');
  return `<div class="sm-steps"><table>${rows}</table></div>`;
}

function _smSettings() {
  if (!_sm) return;
  const c = _smCfg();
  const set = (id, v) => { const e = document.getElementById(id); if (e && document.activeElement !== e) e.value = v; };
  set('sm-title', c.title);
  set('sm-wsport', c.ws_port);
  set('sm-httpport', c.http_port);
  document.getElementById('sm-next').checked = c.show_next;
  document.getElementById('sm-clock').checked = c.show_clock;
  document.getElementById('sm-numbers').checked = c.show_numbers;
  document.getElementById('sm-notes').checked = c.show_notes;
  document.querySelectorAll('#sm-font button').forEach(b => b.classList.toggle('on', b.dataset.v === c.font));
  set('sm-theme', c.theme);
  set('sm-folder', _sm.folder || '');
  setFileChip('sm-folder-chip', _sm.folder, 'no folder yet');
  _smServer(_sm.server);
}

function _smSync() {
  const go = document.getElementById('sm-go');
  const pv = document.getElementById('sm-preview');
  const n = _sm ? _smCfg().lists.length : 0;
  if (go) go.disabled = !n;
  if (pv) pv.disabled = !n;
  const s = document.getElementById('sm-summary');
  if (s) s.innerHTML = _sm
    ? `<span class="doc-chip">${_esc(`${_sm.lists.length} cue list(s) in the show`)}</span> <span class="doc-chip">${_esc(`${n} on the page`)}</span>`
    : '';
  if (!_sm || !n) { setOutcome('stagemon', ''); return; }
  setOutcome('stagemon', [_esc('index.html'), _esc('serve_stage.py')], '', 'Export will write');
}

// ── edits (kept in <show>.stage.json) ────────────────────────────────────────
function _smChanged(redraw = false) {
  if (redraw) _smRender(); else _smSync();
  clearTimeout(_smSaveT);
  _smSaveT = setTimeout(_smSave, 400);
}

async function _smSave() {
  if (!_sm) return;
  try {
    const r = await fetch('/api/stagemon/config', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({config: _smCfg()}),
    });
    const d = await r.json();
    const el = document.getElementById('sm-saved');
    if (el) el.textContent = d.saved ? `Settings kept in ${d.sidecar}` : (d.note || d.error || '');
  } catch (e) { /* kept in the page until the next try */ }
}

function stagemonSet(key, value) {
  if (!_sm) return;
  _smCfg()[key] = value;
  _smSettings();
  _smChanged();
}

function stagemonTick(id, on) {
  const c = _smCfg();
  if (on && !_smItem(id)) c.lists.push({id: String(id), label: '', mode: 'read', steps: {}});
  if (!on) { c.lists = c.lists.filter(x => x.id !== String(id)); _smOpen.delete(String(id)); }
  _smChanged(true);
}

function stagemonList(id, key, value) {
  const it = _smItem(id);
  if (!it) return;
  it[key] = value;
  _smChanged(key === 'mode');
}

function stagemonMove(id, delta) {
  const L = _smCfg().lists;
  const i = L.findIndex(x => x.id === String(id));
  const j = i + delta;
  if (i < 0 || j < 0 || j >= L.length) return;
  [L[i], L[j]] = [L[j], L[i]];
  _smChanged(true);
}

function stagemonSteps(id) {
  id = String(id);
  if (_smOpen.has(id)) _smOpen.delete(id); else _smOpen.add(id);
  _smRender();
}

function stagemonStep(id, index, key, value) {
  const it = _smItem(id);
  if (!it) return;
  const k = String(index);
  const s = Object.assign({}, it.steps[k]);
  if (key === 'hide') { if (value) s.hide = true; else delete s.hide; }
  if (key === 'label') { if (String(value).trim()) s.label = value; else delete s.label; }
  if (Object.keys(s).length) it.steps[k] = s; else delete it.steps[k];
  _smChanged(key === 'hide');
}

// ── folder, preview, export, serve ───────────────────────────────────────────
async function stagemonPickFolder() {
  const p = await nativePick('Folder for the Stage Monitor page', [], _sm && _sm.folder ? _sm.folder.replace(/[\\/][^\\/]*$/, '') : '', true);
  if (p) stagemonFolder(p);
  else if (nativePick.unavailable) document.getElementById('sm-folder')?.focus();
}

function stagemonFolder(p) {
  if (!_sm) return;
  _sm.folder = String(p || '').trim();
  _smSettings();
}

function _smLang() {
  return (typeof I18N !== 'undefined' && I18N.lang) || 'en';
}

async function stagemonPreview() {
  if (!_sm) return;
  try {
    // In the app's own window the server opens your browser (that window opens no new windows);
    // in a browser the preview opens in a new tab of that same browser, wherever Swiss Knife runs.
    const r = await fetch('/api/stagemon/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: _smCfg(), lang: _smLang(), open: true}),
    });
    const d = await r.json();
    if (!r.ok) { setStatus(d.error || 'Preview failed', 'error'); return; }
    if (d.opened) setStatus('Preview opened in your browser.');
    else window.open(d.url, '_blank');
  } catch (e) { setStatus('Preview failed', 'error'); }
}

// Replacing an earlier export is the one place Swiss Knife writes over files: it asks first.
const _SM_REPLACE = 'The folder already has a Stage Monitor page from an earlier export:\n\n{0}\n\n'
  + 'Replace these files? This is the only time Swiss Knife writes over files. They are the Stage Monitor\'s own; '
  + 'the show and every other file in the folder stay as they are.';

async function stagemonExport(replace = false) {
  if (!_sm) return;
  try {
    const r = await fetch('/api/stagemon/export', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: _smCfg(), folder: _sm.folder, lang: _smLang(), replace}),
    });
    const d = await r.json();
    if (r.status === 409 && d.replace && !replace) {
      const files = d.replace.map(f => '   ' + f).join('\n');
      if (confirm(t(_SM_REPLACE, files))) return stagemonExport(true);
      setStatus('Export cancelled: the earlier page was kept.', 'warn');
      return;
    }
    if (!r.ok) { setStatus(d.error || 'Export failed', 'error'); return; }
    _sm.folder = d.folder;
    _sm.saved = !!d.sidecar;
    _sm.missing = [];
    _smSettings();
    setOutcome('stagemon', [_esc(d.replaced && d.replaced.length
      ? `Exported to ${d.folder.split(/[\\/]/).pop()}, replacing ${d.replaced.length} file(s)`
      : `Exported to ${d.folder.split(/[\\/]/).pop()}`)], 'ok', '');
    setStatus(d.server && d.server.running
      ? `Stage Monitor page written: ${d.page}. The tablet gets it when the page is reloaded.`
      : 'Page exported. At the gig, double-click Start Stage Monitor in that folder (QLC+ must run with -w).');
  } catch (e) { setStatus('Export failed', 'error'); }
}

async function stagemonServe() {
  if (!_sm) return;
  const r = await fetch('/api/stagemon/serve', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({folder: _sm.folder, port: _smCfg().http_port}),
  });
  const d = await r.json();
  if (!r.ok) setStatus(d.error || 'Could not serve the page', 'error');
  _sm.server = d.server; _smServer(d.server);
}

async function stagemonOpenFolder() {
  const r = await fetch('/api/stagemon/open-folder', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({folder: _sm ? _sm.folder : ''}),
  });
  const d = await r.json();
  if (!r.ok) setStatus(d.error || 'Could not open the folder', 'error');
}

async function stagemonStop() {
  const r = await fetch('/api/stagemon/stop', {method: 'POST'});
  const d = await r.json();
  if (_sm) _sm.server = d.server;
  _smServer(d.server);
}

async function _smStatus() {
  try {
    const d = await (await fetch('/api/stagemon/status')).json();
    if (_sm) _sm.server = d.server;
    _smServer(d.server);
  } catch (e) { /* later */ }
}

let _smPoll = null;
function _smServer(sv) {
  clearTimeout(_smPoll);
  if (sv && sv.running && !sv.https_from && document.getElementById('scr-stagemon')?.classList.contains('active'))
    _smPoll = setTimeout(_smStatus, 4000);
  const el = document.getElementById('sm-server');
  if (!el || !sv) return;
  document.getElementById('sm-serve').hidden = sv.running;
  document.getElementById('sm-stop').hidden = !sv.running;
  if (sv.running) {
    const urls = sv.urls.length ? sv.urls : [`http://localhost:${sv.port}/`];
    el.innerHTML = `<div>${_esc('Serving — open on the tablet:')}</div>` + urls.map(u =>
      `<div class="sm-url"><code>${_esc(u)}</code><button class="btn btn-surface btn-sm" onclick="navigator.clipboard && navigator.clipboard.writeText('${_esc(u)}')">${_esc('Copy')}</button></div>`).join('');
    if (sv.https_from) el.innerHTML += `<div class="sm-warn">${_esc(`${sv.https_from} asked for https://. On that device type the address with http://, as shown above.`)}</div>`;
    el.innerHTML += `<div class="sm-meta" style="margin:6px 0 0">${_esc('At the gig only QLC+ (with -w) and this server are needed. Without Swiss Knife: double-click Start Stage Monitor in the folder.')}</div>`;
  } else {
    const ips = sv.addresses || [];
    const where = ips.length ? _esc(`This computer: ${ips.join(', ')}`)
      : _esc('No network address found. Join or create a Wi-Fi network first.');
    el.innerHTML = `<div class="sm-meta" style="margin:0">${where}</div>`
      + (sv.error ? `<div class="sm-warn">${_esc(sv.error)}</div>` : '');
  }
}
