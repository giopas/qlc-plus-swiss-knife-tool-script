/**
 * session.js
 * ==========
 * Session / project file (.qsk) support for QLC+ Swiss Knife.
 *
 * A .qsk file is a small JSON that remembers:
 *   - workspace path
 *   - dictionary path
 *   - per-slot setlist file paths (with assignments + timing)
 *   - brightness QXF forced assignments
 *
 * The file is saved to / loaded from the user's computer entirely client-side
 * (download for save, FileReader for load) so no server-side file I/O is
 * needed for the .qsk itself.  Applying the paths (loading the workspace etc.)
 * goes through the normal API endpoints.
 */

'use strict';

// ── Module-level state ────────────────────────────────────────────────────────

const _sess = {
  filename:         null,   // name of the .qsk file (for display only)
  dirty:            false,  // true when session has changed since last save
  workspace:        null,
  dictionary:       null,
  slot_paths:       {},     // slot_id -> path (synced from server)
  brightness_forced: {},
  showbook_qxf_dir: null,   // path to QXF folder for Show Book
  showbook_sections: null,  // array of selected section IDs (null = all)
  porter_source:    null,   // path to source .qxw for Function Porter
};

// ── Init (called from app.js after DOM ready) ─────────────────────────────────

function initSession() {
  _renderSessionBadge();
  _renderSessionList();
  window.addEventListener('beforeunload', _onBeforeUnload);

  // Track dictionary path changes
  const dictInp = document.getElementById('dict-path');
  if (dictInp) {
    dictInp.addEventListener('change', () => {
      const v = dictInp.value.trim();
      if (v && v !== _sess.dictionary) {
        _sess.dictionary = v;
        _markDirty();
      }
    });
  }
}


// ── Session badge in header ───────────────────────────────────────────────────

function _renderSessionBadge() {
  const badge = document.getElementById('session-badge');
  if (!badge) return;
  if (_sess.filename) {
    badge.textContent = (_sess.dirty ? '● ' : '') + _sess.filename;
    badge.title = _sess.dirty
      ? 'Session has unsaved changes — click 📋 to save'
      : `Session: ${_sess.filename}`;
  } else {
    badge.textContent = _sess.dirty ? '● unsaved session' : '';
    badge.title = _sess.dirty ? 'Session has unsaved changes — click 📋 to save' : '';
  }
}


// ── Session list on Start page ────────────────────────────────────────────────

function _renderSessionList() {
  const wrap = document.getElementById('session-list');
  if (!wrap) return;
  try {
    const recents = JSON.parse(localStorage.getItem('sk-recents') || '[]');
    const sessions = recents.filter(r => r.type === 'qsk');
    if (!sessions.length) {
      wrap.innerHTML = '<div class="session-list-empty">No saved sessions yet. ' +
        'Load a workspace, then save a session to see it here.</div>';
      return;
    }
    wrap.innerHTML = sessions.map(r => {
      const name = r.path.split(/[\\/]/).pop();
      const ago  = typeof _timeAgo === 'function' ? _timeAgo(r.ts) : '';
      const active = _sess.filename === name ? ' session-item-active' : '';
      return `<div class="session-item${active}" onclick="sessionLoadFromPath('${r.path.replace(/'/g, "\\'")}')">
        <svg class="ic"><use href="/static/icons.svg#clipboard"/></svg>
        <span class="session-item-name">${name}</span>
        <span class="session-item-ago">${ago}</span>
      </div>`;
    }).join('');
  } catch {}
}


// ── Modal open / close ────────────────────────────────────────────────────────

function sessionOpenModal() {
  _syncFromServer().then(() => {
    _renderModal();
    document.getElementById('session-modal').classList.add('open');
    document.getElementById('session-overlay').classList.add('open');
  });
}

function sessionCloseModal() {
  document.getElementById('session-modal').classList.remove('open');
  document.getElementById('session-overlay').classList.remove('open');
}


// ── Browse for a .qsk file via native picker ─────────────────────────────────

async function sessionBrowseFile() {
  if (typeof nativePick !== 'function') {
    _showStatus('Native file picker not available', 'warn');
    return;
  }
  const path = await nativePick(
    'Open session file',
    [{ label: 'QLC+ Swiss Knife Session', exts: ['.qsk'] }]
  );
  if (path) {
    sessionLoadFromPath(path);
  }
}


// ── Sync state from server ────────────────────────────────────────────────────

async function _syncFromServer() {
  try {
    const r = await fetch('/api/session/export');
    if (!r.ok) return;
    const data = await r.json();
    _sess._serverData = data;   // keep full response for modal rendering
    if (data.workspace)          _sess.workspace         = data.workspace;
    if (data.dictionary)         _sess.dictionary        = data.dictionary;
    if (data.slot_paths)         _sess.slot_paths        = data.slot_paths;
    if (data.brightness_forced)  _sess.brightness_forced = data.brightness_forced;
  } catch (e) { /* silent */ }

  // Pull current dict value from DOM if not yet tracked
  const dictInp = document.getElementById('dict-path');
  if (dictInp?.value?.trim() && !_sess.dictionary)
    _sess.dictionary = dictInp.value.trim();
}


// ── Render modal content ──────────────────────────────────────────────────────

function _renderModal() {
  const body = document.getElementById('session-modal-body');
  if (!body) return;

  const data         = _sess._serverData || {};
  const wsPath       = _sess.workspace      || '';
  const dictPath     = _sess.dictionary     || _getDomDictPath();
  const forced       = _sess.brightness_forced || {};
  const forcedCount  = data.brightness_count ?? Object.keys(forced).length;
  const slotPaths    = _sess.slot_paths || {};
  const slotCount    = Object.keys(slotPaths).length;
  const uploadMode   = data.ws_upload_mode;
  const origName     = data.ws_original_name || '';
  const wsLoaded     = data.ws_loaded;

  // Workspace row note
  let wsNote = '';
  let wsPlaceholder = 'Paste full path to .qxw file…';
  let wsValue = wsPath;
  if (uploadMode && !wsPath) {
    wsNote = `<span class="sess-upload-note">⚠ Loaded via upload (<em>${_esc(origName)}</em>) — paste the full file path below to remember it for next time</span>`;
    wsPlaceholder = origName ? `Full path to ${origName}` : 'Full path to workspace .qxw…';
  } else if (!wsLoaded) {
    wsNote = `<span class="sess-upload-note sess-muted">No workspace loaded</span>`;
  }

  body.innerHTML = `
    <p class="sess-hint">All fields are optional — fill in only the paths you want remembered. You can paste paths directly without re-loading the files.</p>

    <div class="sess-row">
      <div class="sess-row-label">🎬 Workspace</div>
      <div class="sess-row-body">
        ${wsNote}
        <div class="sess-path-row">
          <input id="sess-inp-workspace" class="sess-path-input" type="text"
                 value="${_esc(wsValue)}" placeholder="${_esc(wsPlaceholder)}"
                 spellcheck="false" oninput="_sessInputChanged()">
          ${wsValue ? `<button class="btn btn-surface btn-sm" onclick="sessionChangeWorkspace()" title="Pre-fill the header path input with this path">📂 Use</button>` : ''}
        </div>
      </div>
    </div>

    <div class="sess-row">
      <div class="sess-row-label">📖 Dictionary</div>
      <div class="sess-row-body">
        <div class="sess-path-row">
          <input id="sess-inp-dictionary" class="sess-path-input" type="text"
                 value="${_esc(dictPath)}" placeholder="Paste full path to descriptions .txt…"
                 spellcheck="false" oninput="_sessInputChanged()">
          <button class="btn btn-surface btn-sm" onclick="sessionPickDictionary(null)"
                  title="Browse for a descriptions .txt file">📂</button>
        </div>
      </div>
    </div>

    <div class="sess-row">
      <div class="sess-row-label">🎵 Setlist slots</div>
      <div class="sess-row-body sess-readonly">
        ${slotCount
          ? `<span class="sess-ok">✓ ${slotCount} slot file path${slotCount !== 1 ? 's' : ''} remembered — restored automatically when session is loaded</span>`
            + Object.entries(slotPaths).map(([sid, p]) =>
                `<div class="sess-field-hint sess-muted" style="margin-top:3px">Slot ${_esc(sid)}: ${_truncPath(p)}</div>`
              ).join('')
          : `<span class="sess-muted">No slot files saved yet — use "Save Slot File" in the Setlist tab</span>`}
      </div>
    </div>

    <div class="sess-row">
      <div class="sess-row-label">💡 QXF overrides</div>
      <div class="sess-row-body sess-readonly">
        ${forcedCount
          ? `<span class="sess-ok">✓ ${forcedCount} fixture${forcedCount !== 1 ? 's' : ''} with forced QXF — will be saved automatically</span>`
          : `<span class="sess-muted">None</span>`}
      </div>
    </div>

    ${_sess.filename ? `<p class="sess-file-note">Session file: <strong>${_esc(_sess.filename)}</strong></p>` : ''}
  `;
}

function _sessInputChanged() {
  _markDirty();
}

// Pull current path values out of the modal inputs (used at save time)
function _collectModalPaths() {
  return {
    workspace:  (document.getElementById('sess-inp-workspace')  || {}).value?.trim() || null,
    dictionary: (document.getElementById('sess-inp-dictionary') || {}).value?.trim() || null,
  };
}

function _getDomDictPath() {
  return (document.getElementById('dict-path') || {}).value?.trim() || '';
}


// ── "Change workspace" — pre-fill path input and close modal ─────────────────

function sessionChangeWorkspace() {
  const ws = _sess.workspace || '';
  const inp = document.getElementById('path-input');
  if (inp && ws) {
    inp.value = ws;
    inp.focus();
    inp.select();
  }
  sessionCloseModal();
}


// ── Browse for dictionary ─────────────────────────────────────────────────────

async function sessionPickDictionary(fallbackInput) {
  // Try native OS picker — returns the real filesystem path
  const current = (document.getElementById('sess-inp-dictionary') || {}).value?.trim() || '';
  const initDir = _parentDir(current);
  const path = await nativePick(
    'Select descriptions dictionary (.txt)',
    [{ label: 'Text files', exts: ['.txt'] }],
    initDir
  );
  if (path) {
    const field = document.getElementById('sess-inp-dictionary');
    if (field) field.value = path;
    _markDirty();
    return;
  }
  // Native picker not available or cancelled — show filename from file input as hint
  if (fallbackInput) {
    const file = fallbackInput.files && fallbackInput.files[0];
    if (file) {
      const field = document.getElementById('sess-inp-dictionary');
      if (field && !field.value.trim()) {
        field.value = file.name;
        field.placeholder = 'Path unknown — paste the full path here';
      }
      _markDirty();
    }
  }
}


// ── Browse for setlist backup ─────────────────────────────────────────────────

// sessionPickSetlist removed — slot paths are now tracked per slot via
// "Save Slot File" / "Load Slot File" buttons in the Setlist tab.


// ── Save session (download .qsk) ──────────────────────────────────────────────
//
// A session (.qsk) remembers everything needed to pick up where you left off:
//   workspace, dictionary, setlist slot files, show name + date,
//   Brightness (forced QXFs + slider values), Function Porter and QXW Merger
//   files, Show Book QXF folder + sections, PDF paper sizes.
// Not saved on purpose: unsaved edits inside the workspace (VC editor, Trigger
// Manager, Setlist) — those belong in a new .qxw via each tool's 💾 button.

function _absPath(p) {
  p = (p || '').trim();
  return (p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p)) ? p : null;
}

function _collectToolState() {
  const val = id => (document.getElementById(id) || {}).value || '';
  const tools = {
    porter: { source: _absPath(val('porter-src-path')), target: _absPath(val('porter-tgt-path')) },
    merger: { source: _absPath(val('merger-src-path')), destination: _absPath(val('merger-dst-path')) },
    showbook: {
      qxf_dir: _absPath(val('sb-qxf-path')) || _sess.showbook_qxf_dir || null,
      sections: Array.from(document.querySelectorAll('#sb-section-checks input[type=checkbox]:checked'))
                     .map(c => c.value),
    },
    paper: { fixtures: val('fix-pdf-paper'), checklist: val('chk-pdf-paper'), techrider: val('tr-pdf-paper') },
  };
  if (typeof _brtScales !== 'undefined' && Object.keys(_brtScales).length) {
    tools.brightness = { scales: _brtScales, manual: _brtManual, linked: _brtLinked };
  } else if (_sess.tools && _sess.tools.brightness) {
    tools.brightness = _sess.tools.brightness;     // restored but tab not opened yet
  }
  return tools;
}

async function sessionSave() {
  await _syncFromServer();

  const modal = document.getElementById('session-modal');
  if (modal && modal.classList.contains('open')) {
    const inp = _collectModalPaths();
    if (inp.workspace)  _sess.workspace  = inp.workspace;
    if (inp.dictionary) _sess.dictionary = inp.dictionary;
  }

  const srv = _sess._serverData || {};
  const data = {
    version:           1,
    workspace:         _sess.workspace || null,
    dictionary:        _sess.dictionary || null,
    slot_paths:        _sess.slot_paths || {},
    brightness_forced: _sess.brightness_forced || {},
    show_name:         srv.show_name || '',
    event_date:        srv.event_date || '',
    tools:             _collectToolState(),
  };

  const filename = _sess.filename || _suggestFilename();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const savedName = await saveFileWithPicker(
    blob, filename,
    [{ description: 'QLC+ Swiss Knife session', accept: { 'application/json': ['.qsk'] } }],
    'Save session as'
  );
  if (!savedName) return;  // user cancelled

  _sess.filename = savedName;
  _sess.tools = data.tools;
  _clearDirty();
  await fetch('/api/session/mark-saved', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_file: savedName }),
  });
  await _postUpdateField('tools', data.tools);
  const fullPath = saveFileWithPicker.lastPath;
  if (fullPath && typeof _addRecent === 'function') _addRecent(fullPath, 'qsk');
  _renderSessionList();
  sessionCloseModal();
  _showStatus(`💾 Session saved: ${savedName}`);
}


// ── Load session: one code path for "Open .qsk", recents and drag & drop ─────

async function sessionLoad(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  input.value = '';
  let data;
  try { data = JSON.parse(await file.text()); }
  catch (e) { _showStatus('⚠ Could not parse session file: ' + e.message); return; }
  if (!data || data.version !== 1) { _showStatus('⚠ Not a valid .qsk session file.'); return; }

  sessionCloseModal();
  _showStatus('⏳ Loading session…');
  try {
    const r = await fetch('/api/session/apply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session: data }),
    });
    await _afterSessionApplied(await r.json(), data, file.name);
  } catch (e) {
    _showStatus('⚠ Failed to apply session: ' + e.message);
  }
}

async function sessionLoadFromPath(path) {
  if (!path) return;
  if (_sess.dirty) {
    const oldName = (_sess.filename || 'current session').replace(/\.qsk$/i, '');
    if (confirm(`You have unsaved session changes for "${oldName}".\n\nSave before switching?`)) {
      await sessionSave();
    }
  }
  _showStatus('⏳ Loading session…');
  try {
    const r = await fetch('/api/session/load-from-path', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const result = await r.json();
    if (!r.ok) { _showStatus('⚠ ' + (result.error || 'Failed to load session')); return; }
    if (typeof _addRecent === 'function') _addRecent(path, 'qsk');
    await _afterSessionApplied(result, result.session || {}, result.session_file || path.split(/[\\/]/).pop());
  } catch (e) {
    _showStatus('⚠ Failed to load session: ' + e.message);
  }
}

/** Shared by every way of opening a session: sync state, refresh UI, restore tools. */
async function _afterSessionApplied(result, data, filename) {
  const srv = result.session || {};
  _sess.filename          = filename;
  _sess.workspace         = srv.workspace         || data.workspace  || null;
  _sess.dictionary        = srv.dictionary        || data.dictionary || null;
  _sess.slot_paths        = srv.slot_paths        || data.slot_paths || {};
  _sess.brightness_forced = srv.brightness_forced || data.brightness_forced || {};
  _sess.tools             = srv.tools             || data.tools || {};
  _clearDirty();

  // Header, banners and every tab's cache
  if (typeof _refreshAfterLoad === 'function') await _refreshAfterLoad();
  if (typeof _loadShowInfo === 'function') _loadShowInfo();
  if (typeof refreshSlots === 'function') refreshSlots();
  if (typeof selectSlot === 'function' && typeof _selectedSlot !== 'undefined' && _selectedSlot) {
    selectSlot(_selectedSlot);
  }
  if (_sess.dictionary) {
    const d = document.getElementById('dict-path'); if (d) d.value = _sess.dictionary;
    if (typeof setFileChip === 'function') setFileChip('dict-path-name', _sess.dictionary, 'no dictionary loaded');
  }
  await _restoreToolState(_sess.tools);

  const res = result.results || {};
  const matchInfo = res.auto_match && res.auto_match.startsWith('ok')
    ? ` · ${res.auto_match.replace(/^ok\s*/, '')}` : '';
  _showStatus((result.ok ? '✅ Session loaded' : '⚠ Session loaded (with errors)') +
              ` — ${filename}${matchInfo}`);
  _renderSessionBadge();
  _renderSessionList();
}

async function _restoreToolState(t) {
  t = t || {};
  const setVal = (id, v) => { const el = document.getElementById(id); if (el && v) el.value = v; };
  // Show Book
  const sb = t.showbook || {};
  if (sb.qxf_dir) {
    _sess.showbook_qxf_dir = sb.qxf_dir;
    setVal('sb-qxf-path', sb.qxf_dir);
    if (typeof setFileChip === 'function') setFileChip('sb-qxf-name', sb.qxf_dir, 'no folder chosen');
  }
  if (Array.isArray(sb.sections) && sb.sections.length) {
    document.querySelectorAll('#sb-section-checks input[type=checkbox]').forEach(c => {
      c.checked = sb.sections.includes(c.value);
    });
  }
  // PDF paper sizes
  const pp = t.paper || {};
  setVal('fix-pdf-paper', pp.fixtures); setVal('chk-pdf-paper', pp.checklist); setVal('tr-pdf-paper', pp.techrider);
  // Brightness sliders: applied when the Brightness tab (re)loads its fixtures
  window._brtPendingRestore = t.brightness || null;
  // Two-file tools: reload their files from disk
  const load = async (side, path, fn) => {
    if (!path || typeof window[fn] !== 'function') return;
    const f = document.getElementById(side + '-file'); if (f) f.value = '';
    document.getElementById(side + '-path').value = path;
    if (typeof setFileChip === 'function') setFileChip(side + '-chip', path);
    try { await window[fn](); } catch { /* reported in the tool's status bar */ }
  };
  const po = t.porter || {}, me = t.merger || {};
  await load('porter-src', po.source, 'porterLoadSrc');
  await load('porter-tgt', po.target, 'porterLoadTgt');
  await load('merger-src', me.source, 'mergerLoadSrc');
  await load('merger-dst', me.destination, 'mergerLoadDst');
}


// ── New session (clear current) ──────────────────────────────────────────────

async function sessionNew() {
  // Prompt to save if dirty
  if (_sess.dirty) {
    const oldName = (_sess.filename || 'current session').replace(/\.qsk$/i, '');
    const save = confirm(
      `You have unsaved session changes for "${oldName}".\n\n` +
      `Save before starting a new session?`
    );
    if (save) {
      await sessionSave();
    }
  }

  try {
    await fetch('/api/session/new', { method: 'POST' });
  } catch { /* ignore */ }

  // Clear client state
  _sess.filename          = null;
  _sess.workspace         = null;
  _sess.dictionary        = null;
  _sess.slot_paths        = {};
  _sess.brightness_forced = {};
  _clearDirty();

  // Clear header
  const wsName = document.getElementById('ws-name');
  if (wsName) {
    wsName.textContent = 'No workspace loaded';
    wsName.className   = 'ws-empty';
  }
  const inp = document.getElementById('path-input');
  if (inp) inp.value = '';

  _renderSessionBadge();
  _renderSessionList();
  _showStatus('New session started');

  // Navigate to start screen
  if (typeof go === 'function') go('start');
}


// ── Track dirty state when paths change ──────────────────────────────────────

/** Call this whenever the workspace is loaded via path input or file picker. */
function sessionOnWorkspaceLoaded(path) {
  if (path && !_isTempPath(path)) {
    const oldWs = _sess.workspace;
    if (oldWs && oldWs !== path && _sess.dirty) {
      // Workspace changed and session has unsaved changes — offer to save
      const oldName = oldWs.split(/[\\/]/).pop().replace(/\.qxw$/i, '');
      _promptSaveBeforeSwitch(oldName);
    }
    if (_sess.workspace !== path) {
      _sess.workspace = path;
      _markDirty();
    }
  }
}

/**
 * Show a dialog offering to save the current session named after the showfile
 * before switching to a new workspace.
 */
function _promptSaveBeforeSwitch(showfileName) {
  const suggestedName = showfileName + '.qsk';
  const save = confirm(
    `You have unsaved session changes for "${showfileName}".\n\n` +
    `Save session as "${suggestedName}" before switching?`
  );
  if (save) {
    // Force the suggested filename to match the showfile
    const prevFilename = _sess.filename;
    _sess.filename = suggestedName;
    sessionSave().catch(() => {}).finally(() => {
      // After save, clear so the new workspace starts fresh
      _sess.filename = null;
    });
  }
}

/** Call this whenever the dictionary is loaded. */
function sessionOnDictionaryLoaded(path) {
  if (path && path !== _sess.dictionary) {
    _sess.dictionary = path;
    _markDirty();
  }
}

/** No-op kept for backward compat — slot paths are now tracked server-side per slot. */
function sessionOnSetlistBackupChanged(path) { /* deprecated */ }

/** Call this whenever brightness forced assignments change. */
function sessionOnForcedAssignmentsChanged() {
  // Will be synced from server on next export
  _markDirty();
}


// ── Before-unload warning ─────────────────────────────────────────────────────

function _onBeforeUnload(e) {
  if (_sess.dirty) {
    e.preventDefault();
    e.returnValue = 'You have unsaved session changes. Leave without saving?';
    return e.returnValue;
  }
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function _markDirty() {
  _sess.dirty = true;
  _renderSessionBadge();
}

function _clearDirty() {
  _sess.dirty = false;
  _renderSessionBadge();
}

function _suggestFilename() {
  const ws = _sess.workspace || '';
  const base = ws.split('/').pop().split('\\').pop().replace(/\.qxw$/i, '') || 'session';
  return base + '.qsk';
}

function _truncPath(p) {
  if (!p) return '<span class="sess-empty">—</span>';
  if (p.length <= 60) return _esc(p);
  const parts = p.replace(/\\/g, '/').split('/');
  const name = parts.pop();
  const prefix = parts.slice(0, 2).join('/');
  return _esc(`${prefix}/…/${name}`);
}

function _esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;');
}

function _extractPath(input) {
  // input.value is typically "C:\fakepath\name.txt" in browsers — not useful.
  // We rely on the user pasting the path into the text field directly.
  // This helper is a no-op for security-sandboxed file inputs.
  return null;
}

function _isTempPath(p) {
  return p && (p.startsWith('/tmp') || p.startsWith('/var/folders') ||
               p.toLowerCase().startsWith('c:\\users\\') && p.includes('\\appdata\\local\\temp'));
}

async function _postUpdateField(field, value) {
  try {
    await fetch('/api/session/update-field', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field, value }),
    });
  } catch (e) { /* silent */ }
}

function _parentDir(filePath) {
  if (!filePath) return '';
  const sep = filePath.includes('/') ? '/' : '\\';
  const parts = filePath.split(sep);
  parts.pop();
  return parts.join(sep) || '';
}

function _showStatus(msg) {
  // Reuse the app-level status bar if present
  if (typeof showStatus === 'function') {
    showStatus(msg);
  } else {
    const el = document.getElementById('status-bar');
    if (el) el.textContent = msg;
  }
}

/** Drag & drop of a .qsk file anywhere on the window (see app.js drop handler). */
function sessionLoadDroppedFile(file) {
  return sessionLoad({ files: [file], value: '' });
}
