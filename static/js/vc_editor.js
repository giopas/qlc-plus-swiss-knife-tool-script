/**
 * vc_editor.js — QLC+ Swiss Knife  VC Layout Editor
 * =====================================================
 * Canvas-based editor for Virtual Console widget positions, sizes, colours.
 * Loads the widget tree from GET /api/vc/tree, lets the user edit and
 * reorder widgets, then applies patches via POST /api/vc/patch and
 * exports a new QXW via POST /api/vc/export-qxw.
 *
 * Public API (called from index.html / app.js):
 *   initVcEditor()          — called once when the VC Editor sub-tab is first shown
 *   vcEditorOnTabShow()     — called every time the sub-tab becomes visible
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

let _vceTree       = null;   // raw tree from /api/vc/tree
let _vcePages      = [];     // top-level frames (pages)
let _vcePage       = null;   // currently displayed page node
let _vceNodes      = {};     // flat id→node map (includes inherited abs coords)
let _vceChanges    = {};     // pending patches: id → {x,y,w,h,bg_color,fg_color,...}

let _vceSel        = new Set();  // selected widget IDs
let _vceHov        = null;       // hovered widget ID

let _vceMode       = 'normal';   // 'normal' | 'mask'
let _vceZoom       = 1.0;
let _vcePanX       = 0;
let _vcePanY       = 0;

// Configurable alignment-mask thresholds (pixels)
let _vceThresholds = [2, 5];     // [minor, major]

// Rubber-band drag state
let _vceDragStart  = null;   // {cx, cy} canvas coords where drag started
let _vceDragRect   = null;   // {x1,y1,x2,y2} current rubber-band rect

let _vceInited     = false;

const VCE_CV_ID    = 'vce-canvas';
const VCE_TYPES    = new Set(['Button','Slider','Knob','SpeedDial','XYPad',
                               'Label','Clock','VUMeter','AudioTrigger',
                               'Animation','Frame','SoloFrame','CueList']);

// Colour palette for buttons and frames
const VCE_BG_PAL = [
  '#1e2030','#2d1e3a','#1e3028','#32280e','#3a1020','#2a0e0e',
  '#2a1e08','#142028','#0e2230','#201e2a','#20180e','#0e1a22',
  '#313244','#45475a','#11111b','#181825',
];
const VCE_FG_PAL = [
  '#cdd6f4','#89b4fa','#f38ba8','#a6e3a1','#f9e2af',
  '#fab387','#cba6f7','#94e2d5','#89dceb','#f5c2e7',
  '#ffffff','#000000',
];

// ── Initialise ────────────────────────────────────────────────────────────────

function initVcEditor() {
  if (_vceInited) return;
  _vceInited = true;
  _vceSetupCanvas();
  _vceRenderProps();
}

async function vcEditorOnTabShow() {
  initVcEditor();
  if (!_vceTree) await _vceLoad();
}

async function _vceLoad() {
  const res = await fetch('/api/vc/tree');
  if (!res.ok) { _vceStatus('Could not load VC tree.', 'error'); return; }
  _vceTree  = await res.json();
  _vcePages = _vceTree.pages || [];
  if (!_vcePages.length) { _vceStatus('No VC pages found.', 'warn'); return; }

  // Populate page selector
  const sel = document.getElementById('vce-page-sel');
  if (sel) {
    sel.innerHTML = _vcePages
      .map((p, i) => `<option value="${i}">${_esc(p.caption || 'Page ' + i)}</option>`)
      .join('');
    sel.onchange = () => _vceSelectPage(+sel.value);
  }
  _vceSelectPage(0);
  _vceStatus(`Loaded ${_vcePages.length} page(s) — ${Object.keys(_vceNodes).length} widgets`, 'ok');
}

function _vceSelectPage(idx) {
  _vcePage = _vcePages[idx] || null;
  _vceSel.clear();
  _vceChanges = {};
  _vceNodes   = {};
  if (_vcePage) _vceFlattenNode(_vcePage, null, 0, 0);
  _vceComputeAlignQuality();
  _vceFitPage();
  _vceRender();
  _vceRenderProps();
}

// Build flat id→node map with absolute canvas coords
function _vceFlattenNode(node, parentId, absX, absY) {
  const nx = absX + (node.x || 0);
  const ny = absY + (node.y || 0);
  const pending = _vceChanges[node.id] || {};
  _vceNodes[node.id] = Object.assign({}, node, pending, {
    _absX: nx, _absY: ny,
    _parentId: parentId,
    _alignQ: 0,
  });
  (node.children || []).forEach(c => _vceFlattenNode(c, node.id, nx, ny));
}

// Re-flatten after edits (preserves _alignQ computed separately)
function _vceReflatten() {
  if (!_vcePage) return;
  // merge pending changes into page tree first
  _vceNodes = {};
  _vceFlattenNode(_vcePage, null, 0, 0);
  // apply changes on top
  Object.entries(_vceChanges).forEach(([id, ch]) => {
    if (_vceNodes[id]) Object.assign(_vceNodes[id], ch, {
      _absX: _vceNodes[id]._absX + ((ch.x || 0) - (_vcePage.id === id ? 0 : ((_vceNodes[id].x || 0) - (ch.x || _vceNodes[id].x || 0)))),
    });
  });
  // Re-flatten properly
  _vceNodes = {};
  // patch the tree nodes with changes so _vceFlattenNode picks them up
  _vceApplyChangesToTree(_vcePage);
  _vceFlattenNode(_vcePage, null, 0, 0);
  _vceComputeAlignQuality();
}

function _vceApplyChangesToTree(node) {
  const ch = _vceChanges[node.id];
  if (ch) {
    if ('x' in ch) node.x = ch.x;
    if ('y' in ch) node.y = ch.y;
    if ('w' in ch) node.w = ch.w;
    if ('h' in ch) node.h = ch.h;
    if ('bg_color' in ch) node.bg_color = ch.bg_color;
    if ('fg_color' in ch) node.fg_color = ch.fg_color;
    if ('font_size' in ch) node.font_size = ch.font_size;
    if ('font_bold' in ch) node.font_bold = ch.font_bold;
  }
  (node.children || []).forEach(c => _vceApplyChangesToTree(c));
}

// ── Alignment quality (for mask mode) ────────────────────────────────────────

function _vceComputeAlignQuality() {
  // Group buttons by parent, then check row/column alignment
  const byParent = {};
  Object.values(_vceNodes).forEach(n => {
    if (n.type === 'Button' || n.type === 'Slider') {
      const pid = n._parentId || '__root__';
      (byParent[pid] = byParent[pid] || []).push(n);
    }
  });

  Object.values(byParent).forEach(siblings => {
    // Group by approximate row (Y within threshold[1])
    const rowGap  = _vceThresholds[1];
    const rows    = [];
    [...siblings].sort((a,b) => a.y - b.y).forEach(n => {
      const row = rows.find(r => Math.abs(r.refY - n.y) <= rowGap);
      if (row) row.nodes.push(n);
      else rows.push({ refY: n.y, nodes: [n] });
    });

    rows.forEach(row => {
      const ys = row.nodes.map(n => n.y);
      const hs = row.nodes.map(n => n.h);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const minH = Math.min(...hs), maxH = Math.max(...hs);
      const ySpread = maxY - minY;
      const hSpread = maxH - minH;

      row.nodes.forEach(n => {
        let q = 0;
        const dy = Math.abs(n.y - minY);
        const dh = Math.abs(n.h - minH);
        if (dy > _vceThresholds[1] || dh > _vceThresholds[1]) q = 3;
        else if (dy > _vceThresholds[0] || dh > _vceThresholds[0]) q = 2;
        else if (dy > 0 || dh > 0) q = 1;
        if (q > (_vceNodes[n.id]?._alignQ || 0)) {
          if (_vceNodes[n.id]) _vceNodes[n.id]._alignQ = q;
        }
      });
    });

    // Column check: group by approx X
    const colGap = _vceThresholds[1];
    const cols   = [];
    [...siblings].sort((a,b) => a.x - b.x).forEach(n => {
      const col = cols.find(c => Math.abs(c.refX - n.x) <= colGap);
      if (col) col.nodes.push(n);
      else cols.push({ refX: n.x, nodes: [n] });
    });
    cols.forEach(col => {
      const xs = col.nodes.map(n => n.x);
      const minX = Math.min(...xs);
      col.nodes.forEach(n => {
        const dx = Math.abs(n.x - minX);
        let q = dx > _vceThresholds[1] ? 3 : dx > _vceThresholds[0] ? 2 : dx > 0 ? 1 : 0;
        if (_vceNodes[n.id] && q > _vceNodes[n.id]._alignQ) _vceNodes[n.id]._alignQ = q;
      });
    });
  });
}

const _VCE_AQ_COLOR = ['#a6e3a1', '#f9e2af', '#fab387', '#f38ba8'];
const _VCE_AQ_LABEL = ['Perfect ±0px', 'Minor offset', 'Moderate offset', 'Bad offset'];

// ── Canvas setup and rendering ────────────────────────────────────────────────

function _vceSetupCanvas() {
  const cv = document.getElementById(VCE_CV_ID);
  if (!cv) return;

  cv.addEventListener('click',     _vceOnClick);
  cv.addEventListener('mousedown', _vceOnMouseDown);
  cv.addEventListener('mousemove', _vceOnMouseMove);
  cv.addEventListener('mouseup',   _vceOnMouseUp);
  cv.addEventListener('mouseleave',() => { _vceHov = null; _vceRender(); });
  cv.addEventListener('wheel', e => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.08 : 0.08;
    _vceZoom = Math.max(0.1, Math.min(3.0, _vceZoom + delta));
    document.getElementById('vce-zoom-lbl').textContent = Math.round(_vceZoom * 100) + '%';
    _vceRender();
  }, { passive: false });
}

function _vceFitPage() {
  if (!_vcePage) return;
  const wrap = document.getElementById('vce-canvas-wrap');
  if (!wrap) return;
  const cw = wrap.clientWidth  - 16;
  const ch = wrap.clientHeight - 16;
  const pw = _vcePage.w || 1920;
  const ph = _vcePage.h || 1080;
  _vceZoom = Math.min(cw / pw, ch / ph, 1.0);
  _vcePanX = 0;
  _vcePanY = 0;
  const lbl = document.getElementById('vce-zoom-lbl');
  if (lbl) lbl.textContent = Math.round(_vceZoom * 100) + '%';
  _vceSizeCanvas();
}

function _vceSizeCanvas() {
  const cv = document.getElementById(VCE_CV_ID);
  if (!cv || !_vcePage) return;
  const s = _vceZoom;
  cv.width  = Math.round((_vcePage.w || 1920) * s);
  cv.height = Math.round((_vcePage.h || 1080) * s);
  cv.style.width  = cv.width  + 'px';
  cv.style.height = cv.height + 'px';
}

function _vceRender() {
  const cv = document.getElementById(VCE_CV_ID);
  if (!cv) return;
  _vceSizeCanvas();
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);

  if (!_vcePage) {
    ctx.fillStyle = '#181825';
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = '#6c7086';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('No page selected', cv.width / 2, cv.height / 2);
    return;
  }

  const s = _vceZoom;

  // Draw grid overlay in mask mode
  if (_vceMode === 'mask') {
    ctx.strokeStyle = '#cdd6f408';
    ctx.lineWidth   = 0.5;
    const gs = 10 * s;
    for (let gx = 0; gx < cv.width; gx += gs) {
      ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, cv.height); ctx.stroke();
    }
    for (let gy = 0; gy < cv.height; gy += gs) {
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(cv.width, gy); ctx.stroke();
    }
  }

  // Render in z-order: frames back→front, then buttons/sliders
  const allNodes = Object.values(_vceNodes);
  const frames  = allNodes.filter(n => n.type === 'Frame' || n.type === 'SoloFrame');
  const widgets = allNodes.filter(n => n.type !== 'Frame' && n.type !== 'SoloFrame');

  [...frames, ...widgets].forEach(n => _vceDrawNode(ctx, n, s));

  // Rubber-band overlay
  if (_vceDragRect) {
    const r = _vceDragRect;
    ctx.save();
    ctx.strokeStyle = '#89b4fa';
    ctx.lineWidth   = 1;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(r.x1 * s, r.y1 * s, (r.x2 - r.x1) * s, (r.y2 - r.y1) * s);
    ctx.fillStyle = '#89b4fa18';
    ctx.fillRect(r.x1 * s, r.y1 * s, (r.x2 - r.x1) * s, (r.y2 - r.y1) * s);
    ctx.restore();
  }
}

function _vceRR(ctx, x, y, w, h, r) {
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
  else ctx.rect(x, y, w, h);
}

function _vceDrawNode(ctx, n, s) {
  const ax = n._absX, ay = n._absY;
  const sx = ax * s, sy = ay * s, sw = n.w * s, sh = n.h * s;
  if (sw < 1 || sh < 1) return;

  const isSel = _vceSel.has(n.id);
  const isHov = _vceHov === n.id;
  const isFrame = n.type === 'Frame' || n.type === 'SoloFrame';
  const aq = n._alignQ || 0;

  ctx.save();

  if (isFrame) {
    // Frame fill
    ctx.fillStyle = n.bg_color ? n.bg_color + 'cc' : '#313244cc';
    ctx.beginPath(); _vceRR(ctx, sx, sy, sw, sh, 4 * s); ctx.fill();
    // Frame border
    ctx.strokeStyle = isSel ? '#89b4fa' : (n.fg_color || '#cdd6f4');
    ctx.lineWidth   = isSel ? 2 : 1;
    if (n.type === 'SoloFrame') ctx.setLineDash([5 * s, 3 * s]);
    ctx.beginPath(); _vceRR(ctx, sx, sy, sw, sh, 4 * s); ctx.stroke();
    ctx.setLineDash([]);
    // Frame label
    if (sw > 30 && sh > 14) {
      const fsize = Math.max(7, (n.font_size || 10) * s);
      ctx.font = `${n.font_bold ? '600' : '400'} ${fsize}px monospace`;
      ctx.fillStyle = n.fg_color || '#cdd6f4';
      ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText(n.caption || '', sx + 4 * s, sy + 3 * s, sw - 8 * s);
    }
  } else {
    // Widget (Button / Slider / etc.) fill
    let fillColor = n.bg_color || '#45475a';
    if (_vceMode === 'mask') {
      fillColor = ['#142814','#2a2208','#2a1408','#280808'][aq] || fillColor;
    }
    ctx.fillStyle = fillColor;
    ctx.beginPath(); _vceRR(ctx, sx, sy, sw, sh, 3 * s); ctx.fill();

    // Border
    if (_vceMode === 'mask') {
      ctx.strokeStyle = _VCE_AQ_COLOR[aq];
      ctx.lineWidth   = isSel ? 2.5 : (aq > 0 ? 1.5 : 0.8);
    } else {
      ctx.strokeStyle = isSel ? '#89b4fa' : (isHov ? '#6c7086' : '#313244');
      ctx.lineWidth   = isSel ? 2 : 0.5;
    }
    ctx.beginPath(); _vceRR(ctx, sx, sy, sw, sh, 3 * s); ctx.stroke();

    // Text
    const fsize = Math.max(6, (n.font_size || 9) * s);
    ctx.font = `${n.font_bold !== false ? '600' : '400'} ${fsize}px monospace`;
    ctx.fillStyle = _vceMode === 'mask' ? _VCE_AQ_COLOR[aq] : (n.fg_color || '#cdd6f4');
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(n.caption || '', sx + sw / 2, sy + sh / 2, sw - 8 * s);

    // Mask offset label
    if (_vceMode === 'mask' && aq > 0 && sw > 20 * s) {
      ctx.fillStyle = _VCE_AQ_COLOR[aq];
      ctx.font      = `bold ${Math.max(6, 8 * s)}px monospace`;
      ctx.textAlign = 'right'; ctx.textBaseline = 'top';
      ctx.fillText(['','±' + _vceThresholds[0],'±' + _vceThresholds[1],'>'+_vceThresholds[1]][aq] + 'px',
                   sx + sw - 2 * s, sy + 2 * s);
    }

    // Selection corner handles
    if (isSel) {
      const hs = Math.max(3, 4 * s);
      ctx.fillStyle = '#89b4fa';
      [[sx,sy],[sx+sw,sy],[sx,sy+sh],[sx+sw,sy+sh]].forEach(([hx,hy]) => {
        ctx.fillRect(hx - hs / 2, hy - hs / 2, hs, hs);
      });
    }
  }
  ctx.restore();
}

// ── Mouse interaction ─────────────────────────────────────────────────────────

function _vceCanvasXY(e) {
  const r = document.getElementById(VCE_CV_ID).getBoundingClientRect();
  return [(e.clientX - r.left) / _vceZoom,
          (e.clientY - r.top)  / _vceZoom];
}

function _vceHitTest(ax, ay) {
  const allNodes = Object.values(_vceNodes);
  const widgets  = allNodes.filter(n => n.type !== 'Frame' && n.type !== 'SoloFrame').reverse();
  const frames   = allNodes.filter(n => n.type === 'Frame' || n.type === 'SoloFrame').reverse();
  for (const n of [...widgets, ...frames]) {
    if (ax >= n._absX && ax <= n._absX + n.w &&
        ay >= n._absY && ay <= n._absY + n.h) return n;
  }
  return null;
}

function _vceOnMouseMove(e) {
  const [ax, ay] = _vceCanvasXY(e);
  const hit = _vceHitTest(ax, ay);
  const newHov = hit ? hit.id : null;
  if (newHov !== _vceHov) { _vceHov = newHov; _vceRender(); }
  document.getElementById(VCE_CV_ID).style.cursor = hit ? 'pointer' : 'default';

  // Update rubber-band
  if (_vceDragStart) {
    _vceDragRect = {
      x1: Math.min(_vceDragStart.ax, ax), y1: Math.min(_vceDragStart.ay, ay),
      x2: Math.max(_vceDragStart.ax, ax), y2: Math.max(_vceDragStart.ay, ay),
    };
    _vceRender();
  }

  // Show position in status bar
  if (hit) {
    _vceStatus(`${hit.caption || hit.type} [${hit.id}]  x:${hit.x} y:${hit.y} w:${hit.w} h:${hit.h}  abs x:${hit._absX} y:${hit._absY}`, 'ok');
  } else {
    _vceStatus('', '');
  }
}

function _vceOnMouseDown(e) {
  if (e.button !== 0) return;
  const [ax, ay] = _vceCanvasXY(e);
  const hit = _vceHitTest(ax, ay);
  if (!hit) {
    _vceDragStart = { ax, ay };
    _vceDragRect  = null;
  }
}

function _vceOnMouseUp(e) {
  if (_vceDragRect && _vceDragStart) {
    // Rubber-band selection
    const r = _vceDragRect;
    if (!e.shiftKey) _vceSel.clear();
    Object.values(_vceNodes).forEach(n => {
      // Node must be fully inside rubber-band to be selected
      if (n._absX >= r.x1 && n._absX + n.w <= r.x2 &&
          n._absY >= r.y1 && n._absY + n.h <= r.y2) {
        _vceSel.add(n.id);
      }
    });
    _vceDragStart = null; _vceDragRect = null;
    _vceRender(); _vceRenderProps();
  }
  _vceDragStart = null; _vceDragRect = null;
}

function _vceOnClick(e) {
  const [ax, ay] = _vceCanvasXY(e);
  const hit = _vceHitTest(ax, ay);
  if (!hit) {
    if (!e.shiftKey) { _vceSel.clear(); _vceRenderProps(); _vceRender(); }
    return;
  }
  if (e.shiftKey) {
    if (_vceSel.has(hit.id)) _vceSel.delete(hit.id);
    else _vceSel.add(hit.id);
  } else {
    _vceSel.clear(); _vceSel.add(hit.id);
  }
  _vceRender(); _vceRenderProps();
}

// ── Properties panel ─────────────────────────────────────────────────────────

function _vceRenderProps() {
  const pp = document.getElementById('vce-props');
  if (!pp) return;

  const selArr = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (!selArr.length) {
    const legend = _vceMode === 'mask'
      ? `<div class="vce-pl" style="margin-top:12px">Mask legend</div>
         ${_VCE_AQ_COLOR.map((c,i) => `
           <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
             <div style="width:12px;height:12px;border-radius:2px;background:${c}"></div>
             <span style="font-size:10px">${_VCE_AQ_LABEL[i]}</span>
           </div>`).join('')}`
      : '';
    pp.innerHTML = `<div style="color:var(--text-muted);font-size:11px;padding:20px 0;text-align:center">
      Click a widget to select<br>Shift+click to multi-select<br>Drag to rubber-band select
    </div>${legend}`;
    return;
  }

  const first = selArr[0];
  const multi = selArr.length > 1;
  const xSet  = new Set(selArr.map(n => n.x));
  const ySet  = new Set(selArr.map(n => n.y));
  const wSet  = new Set(selArr.map(n => n.w));
  const hSet  = new Set(selArr.map(n => n.h));
  const bgSet = new Set(selArr.map(n => n.bg_color || ''));
  const fgSet = new Set(selArr.map(n => n.fg_color || ''));
  const xv = xSet.size === 1 ? first.x : '';
  const yv = ySet.size === 1 ? first.y : '';
  const wv = wSet.size === 1 ? first.w : '';
  const hv = hSet.size === 1 ? first.h : '';
  const bgCur = bgSet.size === 1 ? (first.bg_color || '') : '';
  const fgCur = fgSet.size === 1 ? (first.fg_color || '') : '';

  const fsBtns = [7,8,9,10,11,12,14].map(sz =>
    `<button class="vce-ab" style="${first.font_size===sz?'border-color:var(--text-accent);color:var(--text-accent)':''}"
      onclick="vceApplyProp('font_size',${sz})">${sz}</button>`
  ).join('');

  const bgSwatches = VCE_BG_PAL.map(c =>
    `<div onclick="vceApplyColor('bg_color','${c}')" title="${c}"
      style="width:16px;height:16px;border-radius:3px;background:${c};cursor:pointer;
             border:1.5px solid ${bgCur===c?'#89b4fa':'transparent'}"></div>`
  ).join('');

  const fgSwatches = VCE_FG_PAL.map(c =>
    `<div onclick="vceApplyColor('fg_color','${c}')" title="${c}"
      style="width:16px;height:16px;border-radius:3px;background:${c};cursor:pointer;
             border:1.5px solid ${fgCur===c?'#cdd6f4':'#11111b'}"></div>`
  ).join('');

  const aqSection = (_vceMode === 'mask' && !multi) ? `
    <div class="vce-pl">Alignment quality</div>
    <div style="display:flex;align-items:center;gap:6px">
      <div style="width:12px;height:12px;border-radius:2px;background:${_VCE_AQ_COLOR[first._alignQ||0]}"></div>
      <span style="font-size:11px">${_VCE_AQ_LABEL[first._alignQ||0]}</span>
    </div>` : '';

  pp.innerHTML = `
    ${multi
      ? `<div style="font-size:11px;font-weight:500;margin-bottom:4px">${selArr.length} widgets selected</div>`
      : `<div style="font-size:11px;font-weight:500;margin-bottom:1px">${_esc(first.caption || first.type)}</div>
         <div style="font-size:10px;color:var(--text-muted);margin-bottom:6px">${first.type}  ID:${first.id}</div>`
    }

    <div class="vce-pl">Position &amp; size</div>
    <div class="vce-pr4" style="margin-bottom:6px">
      <div><span style="font-size:9px;color:var(--text-muted)">X</span>
        <input class="vce-pi" type="number" value="${xv}" placeholder="${xSet.size>1?'multi':''}"
          onchange="vceApplyProp('x',+this.value)"></div>
      <div><span style="font-size:9px;color:var(--text-muted)">Y</span>
        <input class="vce-pi" type="number" value="${yv}" placeholder="${ySet.size>1?'multi':''}"
          onchange="vceApplyProp('y',+this.value)"></div>
      <div><span style="font-size:9px;color:var(--text-muted)">W</span>
        <input class="vce-pi" type="number" value="${wv}" placeholder="${wSet.size>1?'multi':''}"
          onchange="vceApplyProp('w',+this.value)"></div>
      <div><span style="font-size:9px;color:var(--text-muted)">H</span>
        <input class="vce-pi" type="number" value="${hv}" placeholder="${hSet.size>1?'multi':''}"
          onchange="vceApplyProp('h',+this.value)"></div>
    </div>

    <div class="vce-pl">Font size (px)</div>
    <div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:4px">${fsBtns}</div>
    <div style="display:flex;gap:4px;margin-bottom:6px">
      <button class="vce-ab" style="${first.font_bold!==false?'border-color:var(--text-accent)':''}"
        onclick="vceApplyProp('font_bold',!${first.font_bold!==false})">B Bold</button>
    </div>

    <div class="vce-pl">Button background</div>
    <div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:6px">${bgSwatches}</div>

    <div class="vce-pl">Font colour</div>
    <div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px">${fgSwatches}</div>

    ${aqSection}

    ${_vceMode === 'mask' ? `
    <div class="vce-pl" style="margin-top:6px">Mask legend</div>
    ${_VCE_AQ_COLOR.map((c,i) => `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
        <div style="width:10px;height:10px;border-radius:2px;background:${c}"></div>
        <span style="font-size:10px">${_VCE_AQ_LABEL[i]}</span>
      </div>`).join('')}` : ''}
  `;
}

// ── Property application ──────────────────────────────────────────────────────

function vceApplyProp(field, value) {
  if (value === null || value === undefined) return;
  if (typeof value === 'number' && isNaN(value)) return;
  const selArr = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  selArr.forEach(n => {
    _vceChanges[n.id] = _vceChanges[n.id] || {};
    _vceChanges[n.id][field] = value;
    n[field] = value;
    // Reset align quality after manual edit
    if (['x','y','w','h'].includes(field)) n._alignQ = 0;
  });
  _vceRender(); _vceRenderProps();
  _vceStatus(`Set ${field} = ${value} on ${selArr.length} widget(s)`, 'ok');
}

function vceApplyColor(field, color) {
  const selArr = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  selArr.forEach(n => {
    _vceChanges[n.id] = _vceChanges[n.id] || {};
    _vceChanges[n.id][field] = color;
    n[field] = color;
  });
  _vceRender(); _vceRenderProps();
}

// ── Quick actions ─────────────────────────────────────────────────────────────

function vceAlign(dir) {
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (sa.length < 1) { _vceStatus('Select at least 1 widget', 'warn'); return; }
  const minX = Math.min(...sa.map(n => n.x));
  const minY = Math.min(...sa.map(n => n.y));
  const maxR = Math.max(...sa.map(n => n.x + n.w));
  const maxB = Math.max(...sa.map(n => n.y + n.h));
  const avgCX = sa.reduce((s,n) => s + n.x + n.w/2, 0) / sa.length;
  const avgCY = sa.reduce((s,n) => s + n.y + n.h/2, 0) / sa.length;

  sa.forEach(n => {
    let nx = n.x, ny = n.y;
    switch (dir) {
      case 'left':   nx = minX; break;
      case 'right':  nx = maxR - n.w; break;
      case 'centerH': nx = Math.round(avgCX - n.w / 2); break;
      case 'top':    ny = minY; break;
      case 'bottom': ny = maxB - n.h; break;
      case 'centerV': ny = Math.round(avgCY - n.h / 2); break;
    }
    vceApplyProp('x', nx); // sets on current n via _vceSel loop — need per-node
    _vceChanges[n.id] = _vceChanges[n.id] || {};
    _vceChanges[n.id].x = nx; _vceChanges[n.id].y = ny;
    n.x = nx; n.y = ny; n._alignQ = 0;
  });
  _vceRebuildAbsCoords(); _vceRender(); _vceRenderProps();
  _vceStatus(`Aligned ${sa.length} widgets: ${dir}`, 'ok');
}

function vceDistribute(dir) {
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (sa.length < 3) { _vceStatus('Need 3+ widgets to distribute', 'warn'); return; }
  if (dir === 'h') {
    sa.sort((a,b) => a.x - b.x);
    const span  = sa[sa.length-1].x + sa[sa.length-1].w - sa[0].x;
    const total = sa.reduce((s,n) => s + n.w, 0);
    const gap   = (sa.length > 1) ? Math.round((span - total) / (sa.length - 1)) : 0;
    let cur = sa[0].x;
    sa.forEach(n => { n.x = cur; cur += n.w + gap; n._alignQ = 0;
      (_vceChanges[n.id] = _vceChanges[n.id] || {}).x = n.x; });
  } else {
    sa.sort((a,b) => a.y - b.y);
    const span  = sa[sa.length-1].y + sa[sa.length-1].h - sa[0].y;
    const total = sa.reduce((s,n) => s + n.h, 0);
    const gap   = (sa.length > 1) ? Math.round((span - total) / (sa.length - 1)) : 0;
    let cur = sa[0].y;
    sa.forEach(n => { n.y = cur; cur += n.h + gap; n._alignQ = 0;
      (_vceChanges[n.id] = _vceChanges[n.id] || {}).y = n.y; });
  }
  _vceRebuildAbsCoords(); _vceRender(); _vceRenderProps();
  _vceStatus(`Distributed ${sa.length} widgets ${dir === 'h' ? 'horizontally' : 'vertically'}`, 'ok');
}

function vceSameSize(dim) {
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (sa.length < 2) { _vceStatus('Select 2+ widgets', 'warn'); return; }
  const ref = sa[0];
  const val = dim === 'w' ? ref.w : ref.h;
  sa.forEach(n => { n[dim] = val; n._alignQ = 0;
    (_vceChanges[n.id] = _vceChanges[n.id] || {})[dim] = val; });
  _vceRender(); _vceRenderProps();
  _vceStatus(`Equalized ${dim === 'w' ? 'width' : 'height'} to ${val}px`, 'ok');
}

function vceFitText() {
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  sa.forEach(n => {
    const fs  = n.font_size || 9;
    const ew  = Math.round((n.caption || '').length * fs * 0.62 + 14);
    const eh  = Math.round(fs * 2.8);
    n.w = Math.max(ew, 40); n.h = Math.max(eh, 20); n._alignQ = 0;
    const ch = _vceChanges[n.id] = _vceChanges[n.id] || {};
    ch.w = n.w; ch.h = n.h;
  });
  _vceRender(); _vceRenderProps();
  _vceStatus(`Fit text on ${sa.length} widget(s)`, 'ok');
}

// ── Grid arrange ──────────────────────────────────────────────────────────────

function vceArrangeGrid() {
  const cols    = parseInt(document.getElementById('vce-grid-cols')?.value) || 6;
  const gapX    = parseInt(document.getElementById('vce-grid-gapx')?.value) || 5;
  const gapY    = parseInt(document.getElementById('vce-grid-gapy')?.value) || 5;
  const sortBy  = document.getElementById('vce-grid-sort')?.value || 'pos';
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (!sa.length) { _vceStatus('Select widgets to arrange', 'warn'); return; }

  // Sort order
  const sorted = [...sa];
  if (sortBy === 'alpha')  sorted.sort((a,b) => (a.caption||'').localeCompare(b.caption||''));
  else if (sortBy === 'num') sorted.sort((a,b) => _vceNaturalCmp(a.caption||'', b.caption||''));
  else if (sortBy === 'color') sorted.sort((a,b) => _vceColorHue(a.bg_color||'') - _vceColorHue(b.bg_color||''));
  else if (sortBy === 'id')  sorted.sort((a,b) => (+a.id||0) - (+b.id||0));
  else sorted.sort((a,b) => a.y !== b.y ? a.y - b.y : a.x - b.x); // pos (original order)

  // Use first selected widget's size as reference cell size
  const refW = sa[0].w, refH = sa[0].h;

  // Start position = top-left of bounding box of selection
  const startX = Math.min(...sa.map(n => n.x));
  const startY = Math.min(...sa.map(n => n.y));

  sorted.forEach((n, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    n.x = startX + col * (refW + gapX);
    n.y = startY + row * (refH + gapY);
    n._alignQ = 0;
    const ch = _vceChanges[n.id] = _vceChanges[n.id] || {};
    ch.x = n.x; ch.y = n.y;
  });
  _vceRebuildAbsCoords(); _vceRender(); _vceRenderProps();
  _vceStatus(`Arranged ${sorted.length} widgets in ${cols}-column grid`, 'ok');
}

// ── Sort/reorder within parent ────────────────────────────────────────────────

function vceSortSiblings() {
  const sortBy = document.getElementById('vce-sort-by')?.value || 'alpha';
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  if (sa.length < 2) { _vceStatus('Select 2+ siblings to sort', 'warn'); return; }

  // Check all same parent
  const parents = new Set(sa.map(n => n._parentId));
  if (parents.size > 1) { _vceStatus('All selected widgets must share the same parent frame', 'warn'); return; }

  // Record original positions
  const positions = sa.map(n => ({ x: n.x, y: n.y }))
                       .sort((a,b) => a.y !== b.y ? a.y - b.y : a.x - b.x);

  // Sort widgets by chosen criterion
  const sorted = [...sa];
  if (sortBy === 'alpha') sorted.sort((a,b) => (a.caption||'').localeCompare(b.caption||''));
  else if (sortBy === 'num') sorted.sort((a,b) => _vceNaturalCmp(a.caption||'', b.caption||''));
  else if (sortBy === 'color') sorted.sort((a,b) => _vceColorHue(a.bg_color||'') - _vceColorHue(b.bg_color||''));
  else if (sortBy === 'id') sorted.sort((a,b) => (+a.id||0) - (+b.id||0));

  // Assign sorted widgets to original positions in reading order
  sorted.forEach((n, i) => {
    n.x = positions[i].x; n.y = positions[i].y; n._alignQ = 0;
    const ch = _vceChanges[n.id] = _vceChanges[n.id] || {};
    ch.x = n.x; ch.y = n.y;
  });
  _vceRebuildAbsCoords(); _vceRender(); _vceRenderProps();
  _vceStatus(`Sorted ${sorted.length} widgets by ${sortBy}`, 'ok');
}

// ── Snap to grid ──────────────────────────────────────────────────────────────

function vceSnapToGrid() {
  const gridPx = parseInt(document.getElementById('vce-snap-grid')?.value) || 5;
  const sa = [..._vceSel].map(id => _vceNodes[id]).filter(Boolean);
  sa.forEach(n => {
    const snap = v => Math.round(v / gridPx) * gridPx;
    n.x = snap(n.x); n.y = snap(n.y); n.w = snap(n.w); n.h = snap(n.h); n._alignQ = 0;
    Object.assign(_vceChanges[n.id] = _vceChanges[n.id] || {}, {x:n.x,y:n.y,w:n.w,h:n.h});
  });
  _vceRebuildAbsCoords(); _vceRender(); _vceRenderProps();
  _vceStatus(`Snapped ${sa.length} widgets to ${gridPx}px grid`, 'ok');
}

// ── Rebuild absolute coords after position changes ────────────────────────────

function _vceRebuildAbsCoords() {
  if (!_vcePage) return;
  _vceNodes = {};
  _vceFlattenNode(_vcePage, null, 0, 0);
  _vceComputeAlignQuality();
}

// ── Mask mode ─────────────────────────────────────────────────────────────────

function vceSetMode(m) {
  _vceMode = m;
  document.getElementById('vce-btn-normal')?.classList.toggle('on', m === 'normal');
  document.getElementById('vce-btn-mask')?.classList.toggle('on', m === 'mask');
  _vceComputeAlignQuality();
  _vceRender(); _vceRenderProps();
}

function vceUpdateThresholds() {
  const t0 = parseInt(document.getElementById('vce-thresh0')?.value) || 2;
  const t1 = parseInt(document.getElementById('vce-thresh1')?.value) || 5;
  _vceThresholds = [Math.min(t0, t1), Math.max(t0, t1)];
  _vceComputeAlignQuality(); _vceRender(); _vceRenderProps();
}

// ── Zoom / pan ─────────────────────────────────────────────────────────────────

function vceZoom(delta) {
  _vceZoom = Math.max(0.1, Math.min(3.0, _vceZoom + delta));
  document.getElementById('vce-zoom-lbl').textContent = Math.round(_vceZoom * 100) + '%';
  _vceRender();
}

function vceFit() { _vceFitPage(); _vceRender(); }

// ── Apply patches and export QXW ──────────────────────────────────────────────

async function vceApplyAndExport() {
  const changes = Object.entries(_vceChanges).map(([id, ch]) => ({ id, ...ch }));
  if (!changes.length) {
    _vceStatus('No pending changes to apply.', 'warn'); return;
  }

  // 1. Patch in-memory XML
  const patchRes = await fetch('/api/vc/patch', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ changes }),
  });
  const patchData = await patchRes.json();
  if (patchData.error) { _vceStatus('Patch error: ' + patchData.error, 'error'); return; }

  // 2. Pick save path via native picker
  let savePath = null;
  const state = await (await fetch('/api/status')).json();
  const srcName = (state.original_name || state.path || 'workspace').replace(/\.qxw$/i,'');
  const defName = srcName + '_edited.qxw';

  try {
    const pr = await fetch('/api/picker/save-name', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Save edited workspace as…', default_name: defName, initial_dir: '' }),
    });
    if (pr.ok) {
      const pd = await pr.json();
      if (!pd.cancelled && pd.path) savePath = pd.path;
    }
  } catch {}

  if (!savePath) { _vceStatus('Export cancelled (no path chosen).', 'warn'); return; }
  if (!savePath.toLowerCase().endsWith('.qxw')) savePath += '.qxw';

  // 3. Export QXW
  const expRes = await fetch('/api/vc/export-qxw', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: savePath }),
  });
  const expData = await expRes.json();
  if (expData.error) { _vceStatus('Export error: ' + expData.error, 'error'); return; }

  _vceChanges = {};
  _vceStatus(`✓ Patched ${patchData.patched} widget(s) → saved as ${savePath.split(/[\\/]/).pop()}`, 'ok');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _vceStatus(msg, type) {
  const el = document.getElementById('vce-status');
  if (!el) return;
  el.textContent = msg;
  el.style.color = type === 'error' ? '#f38ba8'
                 : type === 'warn'  ? '#f9e2af'
                 : type === 'ok'    ? '#a6e3a1'
                 : 'var(--text-muted)';
}

function _esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _vceNaturalCmp(a, b) {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

function _vceColorHue(hex) {
  hex = hex.replace('#','');
  if (hex.length !== 6) return 0;
  const r = parseInt(hex.slice(0,2),16)/255;
  const g = parseInt(hex.slice(2,4),16)/255;
  const b = parseInt(hex.slice(4,6),16)/255;
  const max = Math.max(r,g,b), min = Math.min(r,g,b), d = max-min;
  if (d === 0) return 0;
  let h = max === r ? (g-b)/d%6 : max === g ? (b-r)/d+2 : (r-g)/d+4;
  return h * 60;
}

// ── Called from app.js when user opens the VC Editor sub-tab ─────────────────

window.vcEditorOnTabShow = vcEditorOnTabShow;
window.initVcEditor      = initVcEditor;
