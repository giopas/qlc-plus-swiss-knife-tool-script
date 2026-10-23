/* A read-only picture of a Show (3.10.0): rows are tracks, bars are items.
 * Used by the Setlist (next to the Show pill) and the Doctor (findings about a Show).
 * It only reads; QLC+ has its own timeline editor for fine work. */

function _spEsc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function _spClock(ms) { const s = ms / 1000, m = Math.floor(s / 60); return m + ':' + (s - m * 60).toFixed(1).padStart(4, '0'); }
const _SP_HEX = /^#[0-9a-fA-F]{6}$/;

// The bars as HTML (every value is escaped; a colour must be #rrggbb).
function showPicHtml(pic) {
  const scale = Math.max(pic.length_ms || 0, 1);
  const pct = ms => (100 * ms / scale).toFixed(3) + '%';
  const rows = (pic.tracks || []).map(tr => {
    const bars = (tr.items || []).map(it => {
      const bad = it.status === 'missing';
      const tip = `${it.name || t('(missing function)')} · ${it.type || ''} · ${_spClock(it.start)}–${_spClock(it.start + it.duration)}`
        + (it.file ? ` · ${it.file}` : '') + (bad ? ` · ${t('not found')}` : '');
      const colour = !bad && _SP_HEX.test(it.color) ? ` style="background:${it.color}"` : '';
      return `<div class="sbd-seg${bad ? ' sbd-seg-bad' : ''}" data-sp-l="${pct(it.start)}" data-sp-w="${pct(it.duration)}"${colour} data-tooltip="${_spEsc(tip)}"><span>${_spEsc(it.name || '?')}</span></div>`;
    }).join('');
    return `<div class="sbd-bar-row${tr.mute ? ' sp-muted' : ''}"><span class="sbd-bar-lbl sp-lbl">${_spEsc(tr.name)}${tr.mute ? ' · ' + _spEsc(t('muted')) : ''}</span><div class="sbd-bar">${bars}</div></div>`;
  }).join('');
  if (!rows) return `<div class="sbd-hint">${_spEsc(t('This Show has nothing on its timeline.'))}</div>`;
  return rows + `<div class="sbd-bar-row"><span class="sbd-bar-lbl sp-lbl"></span><div class="sbd-ruler"><span>0:00.0</span><span>${_spEsc(_spClock(scale))}</span></div></div>`;
}

// Bar positions are data attributes turned into styles here, so the markup carries no inline style.
function _spPlace(root) {
  root.querySelectorAll('[data-sp-l]').forEach(el => { el.style.left = el.dataset.spL; el.style.width = el.dataset.spW; });
}

async function showPicOpen(id) {
  const box = document.getElementById('showpic-body');
  const modal = document.getElementById('showpic-modal');
  if (!box || !modal) return;
  let pic;
  try { pic = await (await fetch('/api/showpic/' + encodeURIComponent(id))).json(); } catch (e) { pic = { error: String(e) }; }
  document.getElementById('showpic-title').textContent = pic.error ? t('Show') : pic.name;
  if (pic.error) { box.innerHTML = `<div class="sbd-err">${_spEsc(pic.error)}</div>`; }
  else {
    const meta = [t('Total {0}', _spClock(pic.length_ms)), pic.song ? t('made by the Song Builder') : '', pic.cut ? t('Only the first part of a very long Show is drawn.') : '']
      .filter(Boolean).join(' · ');
    box.innerHTML = `<div class="sbd-hint">${_spEsc(meta)}</div><div class="sbd-bars">${showPicHtml(pic)}</div>`;
    _spPlace(box);
  }
  modal.classList.remove('sbd-hidden');
  const close = document.getElementById('showpic-close');
  if (close) close.focus();
}

function showPicClose() {
  const m = document.getElementById('showpic-modal');
  if (m) m.classList.add('sbd-hidden');
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') showPicClose(); });

// A Picture button carries the Show's id as data (never inside a handler), so a hostile id cannot run.
document.addEventListener('click', e => {
  const b = e.target.closest && e.target.closest('[data-showpic]');
  if (!b) return;
  e.preventDefault();
  e.stopPropagation();
  showPicOpen(b.dataset.showpic);
}, true);
