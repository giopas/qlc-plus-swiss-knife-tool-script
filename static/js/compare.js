// =============================================================================
// Compare (WORKPLAN 2.8): the show in progress next to another .qxw, by what
// they do (core/compare.py).  Read-only.
// =============================================================================

let _cmpRes = null;

function compareSetPath(p) {
  p = (p || '').trim();
  if (!p) return;
  document.getElementById('cmp-path').value = p;
  setFileChip('cmp-chip', p);
  compareRun();
}

async function compareBrowse() {
  const p = await nativePick('The other show (.qxw)', [{ label: 'QLC+ Workspace', exts: ['.qxw'] }]);
  if (p) compareSetPath(p);
  else if (nativePick.unavailable) setStatus('Paste the path of the other .qxw in the field and press Enter.', 'warn');
}

async function compareOpened() {
  const st = await _apiJson('/api/status');
  if (!st.loaded || !st.path) { setStatus('No show is open from a file on disk.', 'warn'); return; }
  compareSetPath(st.path);
}

async function compareRun() {
  const path = document.getElementById('cmp-path')?.value || '';
  if (!path) { setStatus('Pick the other show first (📂 Other show…).', 'warn'); return; }
  setStatus('Comparing…', 'ok');
  const r = await fetch('/api/compare/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }) });
  const d = await r.json();
  if (!r.ok) { setStatus(d.error || 'Compare failed.', 'error'); return; }
  _cmpRes = d;
  _cmpRender();
  const t = d.result.total;
  setStatus(d.result.identical ? 'The two shows do the same things.' :
    `${t.same} the same · ${t.different} different · ${t.only_a} only in this show · ${t.only_b} only in the other.`, 'ok');
}

function _cmpRender() {
  const el = document.getElementById('cmp-body');
  if (!el || !_cmpRes) return;
  const R = _cmpRes.result, t = R.total;
  const tot = document.getElementById('cmp-total');
  if (tot) tot.innerHTML = R.identical ? '<span class="cmp-ok">✓ functionally the same</span>' :
    `<span class="doc-chip">${t.same} same</span><span class="doc-chip cmp-d">${t.different} different</span>
     <span class="doc-chip cmp-a">${t.only_a} only here</span><span class="doc-chip cmp-b">${t.only_b} only in the other</span>
     ${(t.unused_a || t.unused_b) ? `<span class="doc-chip cmp-u" title="Functions nothing plays (no button, not in another function) — not counted">${(t.unused_a || 0) + (t.unused_b || 0)} unused, not counted</span>` : ''}`;
  const li = (arr, cls, mark) => arr.map(x => `<li class="${cls}"><span class="cmp-m">${mark}</span>${_esc(x)}</li>`).join('');
  el.innerHTML = `<div class="cmp-head"><b>This show:</b> ${_esc(_cmpRes.a)} &nbsp;·&nbsp; <b>Other:</b> ${_esc(_cmpRes.b)}</div>` +
    _cmpRes.sections.map(([k, label]) => {
      const s = R[k], n = s.different.length + s.only_a.length + s.only_b.length;
      const ua = s.unused_a || [], ub = s.unused_b || [];
      const unused = (arr, where) => arr.length ? `<li class="cmp-u"><span class="cmp-m">·</span>${arr.length} unused, only in ${where}: ${_esc(arr.slice(0, 12).join(', '))}${arr.length > 12 ? ' …' : ''}</li>` : '';
      return `<details class="cmp-sec" ${n && n <= 40 ? 'open' : ''}>
        <summary><b>${_esc(label)}</b>
          <span class="doc-chip">${s.same} same</span>
          ${s.different.length ? `<span class="doc-chip cmp-d">${s.different.length} different</span>` : ''}
          ${s.only_a.length ? `<span class="doc-chip cmp-a">${s.only_a.length} only here</span>` : ''}
          ${s.only_b.length ? `<span class="doc-chip cmp-b">${s.only_b.length} only in the other</span>` : ''}
          ${(ua.length + ub.length) ? `<span class="doc-chip cmp-u">${ua.length + ub.length} unused</span>` : ''}
          ${!n ? '<span class="cmp-ok">✓</span>' : ''}</summary>
        <ul class="cmp-list">${li(s.different, 'cmp-d', '≠')}${li(s.only_a, 'cmp-a', '+')}${li(s.only_b, 'cmp-b', '−')}${unused(ua, 'this show')}${unused(ub, 'the other file')}</ul>
      </details>`;
    }).join('') +
    `<div class="vce-hint">≠ different · + only in this show · − only in the other file · unused = functions nothing plays (no button, not in another function), listed but not counted. Looks are compared by what they light (level and colour) when the fixture definitions are found, else channel by channel.</div>`;
}

async function compareCopy() {
  if (!_cmpRes) { setStatus('Compare first.', 'warn'); return; }
  try { await navigator.clipboard.writeText(_cmpRes.report); setStatus('Report copied.', 'ok'); }
  catch { setStatus('Could not copy — use 💾 Save report…', 'warn'); }
}

async function compareSaveReport() {
  if (!_cmpRes) { setStatus('Compare first.', 'warn'); return; }
  const base = (_cmpRes.a || 'show').replace(/\.qxw$/i, '');
  await saveFileWithPicker(new Blob([_cmpRes.report], { type: 'text/plain' }),
    `${base}_compare_report.txt`, null, 'Save the compare report');
}

function invalidateCompare() { _cmpRes = null; const t = document.getElementById('cmp-total'); if (t) t.innerHTML = ''; }
