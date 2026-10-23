/* Resize by dragging handles (3.10.0): the arithmetic, kept apart from the canvas so it can be tested.
 *
 * A selected widget gets eight handles (four corners, four sides).  Dragging one moves the edges it
 * stands on.  The edges ALWAYS land on the grid (the step is the editor's "Snap to grid" box, 1 to 50 px),
 * a widget never goes below a minimum size and is never dragged out of its frame (or the page); one that
 * already reaches outside keeps its edge and is not squashed.
 * Coordinates are the widget's own (x, y relative to its frame), like the typed fields. */

const VCE_HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
const VCE_MIN_SIZE = 10;

function vceHandlePoints(n) {
  // absolute canvas positions of the handles of node n ({_absX, _absY, w, h})
  const x0 = n._absX, y0 = n._absY, x1 = x0 + n.w, y1 = y0 + n.h, xm = x0 + n.w / 2, ym = y0 + n.h / 2;
  return { nw: [x0, y0], n: [xm, y0], ne: [x1, y0], e: [x1, ym], se: [x1, y1], s: [xm, y1], sw: [x0, y1], w: [x0, ym] };
}

// Which handle (if any) is at the absolute point (ax, ay); tol is in canvas units (screen pixels / zoom).
function vceHandleAt(n, ax, ay, tol) {
  const pts = vceHandlePoints(n);
  let best = null, bestD = Infinity;
  for (const h of VCE_HANDLES) {
    const d = Math.max(Math.abs(ax - pts[h][0]), Math.abs(ay - pts[h][1]));
    if (d <= tol && d < bestD) { best = h; bestD = d; }
  }
  return best;
}

function vceHandleCursor(h) {
  return { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize', n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize' }[h] || 'default';
}

// The new {x, y, w, h} after dragging handle h by (dx, dy).
//   o       the widget before the drag {x, y, w, h}
//   grid    snap step in px (>= 1)
//   bounds  the frame's size {w, h} (the widget stays inside), or null
function vceResizeRect(o, h, dx, dy, grid, bounds) {
  const g = Math.max(1, Math.round(Number(grid)) || 1);
  const min = Math.max(VCE_MIN_SIZE, g);
  const snap = v => Math.round(v / g) * g;
  let left = o.x, top = o.y, right = o.x + o.w, bottom = o.y + o.h;
  if (h.includes('w')) left = Math.min(Math.max(snap(o.x + dx), 0), right - min);
  if (h.includes('e')) { right = Math.max(snap(o.x + o.w + dx), left + min); if (bounds) right = Math.min(right, Math.max(bounds.w, o.x + o.w, left + min)); }
  if (h.includes('n')) top = Math.min(Math.max(snap(o.y + dy), 0), bottom - min);
  if (h.includes('s')) { bottom = Math.max(snap(o.y + o.h + dy), top + min); if (bounds) bottom = Math.min(bottom, Math.max(bounds.h, o.y + o.h, top + min)); }
  return { x: left, y: top, w: right - left, h: bottom - top };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { VCE_HANDLES, VCE_MIN_SIZE, vceHandlePoints, vceHandleAt, vceHandleCursor, vceResizeRect };
