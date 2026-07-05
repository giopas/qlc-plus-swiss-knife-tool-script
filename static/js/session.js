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
};

// ── Init (called from app.js after DOM ready) ─────────────────────────────────

function initSession() {
  _renderSessionBadge();
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

async function sessionSave() {
  await _syncFromServer();

  // Collect paths from modal inputs (if modal is open) — user may have typed
  // paths directly without re-loading files
  const modal = document.getElementById('session-modal');
  if (modal && modal.classList.contains('open')) {
    const inp = _collectModalPaths();
    if (inp.workspace)  _sess.workspace  = inp.workspace;
    if (inp.dictionary) _sess.dictionary = inp.dictionary;
  }

  const data = {
    version:           1,
    workspace:         _sess.workspace || null,
    dictionary:        _sess.dictionary || null,
    slot_paths:        _sess.slot_paths || {},
    brightness_forced: _sess.brightness_forced || {},
  };

  const filename = _sess.filename || _suggestFilename();
  const json     = JSON.stringify(data, null, 2);
  const blob     = new Blob([json], { type: 'application/json' });

  // Try showSaveFilePicker first (Chrome/Edge — lets the user choose the path)
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: 'QLC+ Swiss Knife session', accept: { 'application/json': ['.qsk'] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      _sess.filename = handle.name;
      _clearDirty();
      await fetch('/api/session/mark-saved', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_file: handle.name }),
      });
      sessionCloseModal();
      _showStatus(`💾 Session saved: ${handle.name}`);
      return;
    } catch (e) {
      if (e.name === 'AbortError') return;  // user cancelled
      // fall through to fallback
    }
  }

  // Fallback: auto-download
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);

  _sess.filename = filename;
  _clearDirty();
  await fetch('/api/session/mark-saved', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_file: filename }),
  });
  sessionCloseModal();
  _showStatus(`💾 Session saved: ${filename}`);
}


// ── Load session (file input → parse → apply) ─────────────────────────────────

async function sessionLoad(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  input.value = '';

  let data;
  try {
    const text = await file.text();
    data = JSON.parse(text);
  } catch (e) {
    _showStatus('⚠ Could not parse session file: ' + e.message);
    return;
  }

  if (!data || data.version !== 1) {
    _showStatus('⚠ Not a valid .qsk session file.');
    return;
  }

  sessionCloseModal();
  _showStatus('⏳ Loading session…');

  try {
    const r = await fetch('/api/session/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session: data }),
    });
    const result = await r.json();

    // Update client state
    _sess.filename          = file.name;
    _sess.workspace         = data.workspace         || null;
    _sess.dictionary        = data.dictionary        || null;
    _sess.slot_paths        = data.slot_paths        || {};
    _sess.brightness_forced = data.brightness_forced || {};
    _clearDirty();

    // Reflect workspace in header
    if (data.workspace && result.results?.workspace === 'ok') {
      const inp = document.getElementById('path-input');
      if (inp) inp.value = data.workspace;
      const wsName = document.getElementById('ws-name');
      if (wsName) {
        const name = data.workspace.split('/').pop().split('\\').pop();
        wsName.textContent = name;
        wsName.className = 'ws-loaded';
      }
      // Refresh all tab data
      if (typeof invalidateBrightness === 'function') invalidateBrightness();
      if (typeof refreshSlots         === 'function') refreshSlots();
      // Enable reload button
      const rl = document.getElementById('btn-reload');
      if (rl) rl.disabled = false;
    }

    // Build status summary
    const lines = Object.entries(result.results || {}).map(
      ([k, v]) => `  ${k}: ${v}`
    );
    const ok = result.ok;
    _showStatus(
      (ok ? '✅ Session loaded' : '⚠ Session loaded (with errors)') +
      ` — ${file.name}`
    );
    _renderSessionBadge();

  } catch (e) {
    _showStatus('⚠ Failed to apply session: ' + e.message);
  }
}


// ── Track dirty state when paths change ──────────────────────────────────────

/** Call this whenever the workspace is loaded via path input or file picker. */
function sessionOnWorkspaceLoaded(path) {
  if (path && !_isTempPath(path)) {
    if (_sess.workspace !== path) {
      _sess.workspace = path;
      _markDirty();
    }
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
