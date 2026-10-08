/* =============================================================================
   mcp.js — "Connect to Claude" (v2.9.0)
   The folders Claude may use through the MCP server, and the snippet to paste
   into Claude's settings.  The server itself is `QLC Swiss Knife --mcp`.
   ============================================================================= */

'use strict';

let _mcp = null;

async function mcpLoad() {
  try { _mcp = await (await fetch('/api/mcp/config')).json(); } catch { return; }
  const ul = document.getElementById('mcp-folders');
  ul.innerHTML = '';
  if (!_mcp.folders.length) {
    const li = document.createElement('li');
    li.className = 'mcp-none';
    li.textContent = t('No folder yet.');
    ul.appendChild(li);
  }
  _mcp.folders.forEach(f => {
    const li = document.createElement('li');
    const sp = document.createElement('span');
    sp.textContent = f; sp.className = 'mcp-path'; sp.title = f;
    const b = document.createElement('button');
    b.className = 'sc-link'; b.textContent = t('Remove');
    b.onclick = () => mcpSetFolders(_mcp.folders.filter(x => x !== f));
    li.append(sp, b);
    ul.appendChild(li);
  });
  document.getElementById('mcp-snippet').textContent = _mcp.snippet;
  document.getElementById('mcp-cc').textContent = _mcp.claude_code;
  document.getElementById('mcp-cfgpath').textContent = _mcp.claude_desktop_config;
}

async function mcpToggle(open) {
  const card = document.getElementById('mcp-card');
  const show = open === undefined ? card.hidden : open;
  card.hidden = !show;
  if (show) { document.getElementById('mcp-msg').textContent = ''; await mcpLoad(); }
}

async function mcpSetFolders(list) {
  const msg = document.getElementById('mcp-msg');
  try {
    await fetch('/api/mcp/folders', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                     body: JSON.stringify({folders: list})});
  } catch { msg.textContent = t('Could not save the list.'); }
  await mcpLoad();
}

async function mcpAddFolder() {
  let d;
  try {
    d = await (await fetch('/api/picker/pick', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                body: JSON.stringify({title: 'Folder to share with Claude', folder: true})})).json();
  } catch { return; }
  if (d.path) await mcpSetFolders([...(_mcp ? _mcp.folders : []), d.path]);
}

async function mcpCopy(id, btn) {
  const text = document.getElementById(id).textContent;
  try { await navigator.clipboard.writeText(text); }
  catch {
    const r = document.createRange(); r.selectNodeContents(document.getElementById(id));
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    try { document.execCommand('copy'); } catch { /* selected: Ctrl+C */ }
  }
  const old = btn.textContent;
  btn.textContent = t('Copied');
  setTimeout(() => { btn.textContent = old; }, 1500);
}

async function mcpInstallBundle() {
  const msg = document.getElementById('mcp-install-msg');
  msg.textContent = t('Preparing…');
  let d;
  try {
    d = await (await fetch('/api/mcp/install-bundle', {method: 'POST'})).json();
  } catch { msg.textContent = t('Could not prepare the file.'); return; }
  if (d.error) { msg.textContent = d.error; return; }
  msg.textContent = d.opened
    ? t('Claude Desktop should now ask to install it. Choose the folders with your shows, then Install.')
    : t('The file is in your Downloads folder ({0}): double-click it to open it in Claude Desktop.', d.path);
}
