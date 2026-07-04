/**
 * session.js
 * ==========
 * Session / project file (.qsk) support for QLC+ Swiss Knife.
 *
 * A .qsk file is a small JSON that remembers:
 *   - workspace path
 *   - dictionary path
 *   - setlist backup path
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
  filename:        null,   // name of the .qsk file (for display only)
  dirty:           false,  // true when session has changed since last save
  workspace:       null,
  dictionary:      null,
  setlist_backup:  null,
  brightness_forced: {},
};

// ── Init (called from app.js after DOM ready) ─────────────────────────────────

function initSession() {
  _renderSessionBadge();
  window.addEventListener('beforeunload', _onBeforeUnload);

  // Track setlist backup path changes (user types or pastes into the field)
  const slInp = document.getElementById('setlist-path');
  if (slInp) {
    slInp.addEventListener('change', () => {
      const v = slInp.value.trim();
      if (v) sessionOnSetlistBackupChanged(v);
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
    if (data.workspace)          _sess.workspace         = data.workspace;
    if (data.dictionary)         _sess.dictionary        = data.dictionary;
    if (data.setlist_backup)     _sess.setlist_backup    = data.setlist_backup;
    if (data.brightness_forced)  _sess.brightness_forced = data.brightness_forced;
  } catch (e) { /* silent */ }
}


// ── Render modal content ──────────────────────────────────────────────────────

function _renderModal() {
  const body = document.getElementById('session-modal-body');
  if (!body) return;

  const ws   = _sess.workspace      || '';
  const dict = _sess.dictionary     || '';
  const sl   = _sess.setlist_backup || '';
  const forced = _sess.brightness_forced || {};
  const forcedCount = Object.keys(forced).length;

  body.innerHTML = `
    <table class="sess-table">
      <tbody>
        <tr>
          <td class="sess-label">🎬 Workspace</td>
          <td class="sess-path" title="${_esc(ws)}">${_truncPath(ws)}</td>
          <td class="sess-actions">
            ${ws ? `<button class="btn btn-surface btn-sm" onclick="sessionChangeWorkspace()">📂 Change…</button>` : ''}
          </td>
        </tr>
        <tr>
          <td class="sess-label">📖 Dictionary</td>
          <td class="sess-path" title="${_esc(dict)}">${_truncPath(dict)}</td>
          <td class="sess-actions">
            <label class="btn btn-surface btn-sm" title="Browse for a descriptions .txt file">
              📂 ${dict ? 'Change…' : 'Browse…'}
              <input type="file" accept=".txt" style="display:none"
                     onchange="sessionPickDictionary(this)">
            </label>
          </td>
        </tr>
        <tr>
          <td class="sess-label">🎵 Setlist backup</td>
          <td class="sess-path" title="${_esc(sl)}">${_truncPath(sl)}</td>
          <td class="sess-actions">
            <label class="btn btn-surface btn-sm" title="Browse for a setlist backup .txt file">
              📂 ${sl ? 'Change…' : 'Browse…'}
              <input type="file" accept=".txt" style="display:none"
                     onchange="sessionPickSetlist(this)">
            </label>
          </td>
        </tr>
        <tr>
          <td class="sess-label">💡 QXF overrides</td>
          <td class="sess-path">${forcedCount ? `${forcedCount} fixture${forcedCount !== 1 ? 's' : ''} with forced QXF` : '—'}</td>
          <td class="sess-actions"></td>
        </tr>
      </tbody>
    </table>

    ${_sess.filename ? `<p class="sess-file-note">Session file: <strong>${_esc(_sess.filename)}</strong></p>` : ''}
  `;
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

async function sessionPickDictionary(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  // We need the path — if the browser exposes webkitRelativePath or
  // a real path isn't available, we fall back to the name only.
  // Most modern desktop browsers expose the full path via input.value,
  // but that's typically something like C:\fakepath\name.txt.
  // The safest approach: send the file content and use the existing
  // /api/dictionary/load endpoint if a path is available, otherwise
  // just record the filename as a label.
  const path = _extractPath(input) || file.name;
  _sess.dictionary = path;
  _markDirty();
  _renderModal();

  // Tell the server to track the path in session state
  await _postUpdateField('dictionary', path);
}


// ── Browse for setlist backup ─────────────────────────────────────────────────

async function sessionPickSetlist(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  const path = _extractPath(input) || file.name;
  _sess.setlist_backup = path;
  _markDirty();
  _renderModal();

  // Populate the setlist path input in the Setlist tab
  const slInp = document.getElementById('setlist-path');
  if (slInp) {
    slInp.value = path;
    // Update server session
    await _postUpdateField('setlist_backup', path);
  }
}


// ── Save session (download .qsk) ──────────────────────────────────────────────

async function sessionSave() {
  await _syncFromServer();

  const data = {
    version:           1,
    workspace:         _sess.workspace      || null,
    dictionary:        _sess.dictionary     || null,
    setlist_backup:    _sess.setlist_backup || null,
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
    _sess.filename         = file.name;
    _sess.workspace        = data.workspace        || null;
    _sess.dictionary       = data.dictionary       || null;
    _sess.setlist_backup   = data.setlist_backup   || null;
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

    // Reflect setlist path in setlist tab
    if (data.setlist_backup) {
      const slInp = document.getElementById('setlist-path');
      if (slInp) slInp.value = data.setlist_backup;
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

/** Call this whenever the setlist backup path changes. */
function sessionOnSetlistBackupChanged(path) {
  if (path && path !== _sess.setlist_backup) {
    _sess.setlist_backup = path;
    _markDirty();
    _postUpdateField('setlist_backup', path);
  }
}

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

function _showStatus(msg) {
  // Reuse the app-level status bar if present
  if (typeof showStatus === 'function') {
    showStatus(msg);
  } else {
    const el = document.getElementById('status-bar');
    if (el) el.textContent = msg;
  }
}
