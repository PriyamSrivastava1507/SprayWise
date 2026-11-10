// Zoom and pan for a map. The content (canvases) fills the stage at scale 1.
//   buttons + / − / Fit, Ctrl (or ⌘) + scroll, double-click, two-finger pinch,
//   drag to move when zoomed, and the keyboard: + − 0 and arrow keys.
// onHover receives positions in content pixels (0..stage width) so callers
// can work out what is under the pointer.
import { h } from '../../utils/dom.js';

const MIN = 1, MAX = 8;

export function ZoomStage(content, { label, onHover, onLeave } = {}) {
  const viewport = h('div', { class: 'zoom-viewport' }, content);
  const level = h('span', { class: 'zoom-level', 'aria-live': 'polite' }, '100%');
  const hint = h('div', { class: 'zoom-hint', hidden: true }, 'Hold Ctrl and scroll to zoom the map');
  const controls = h('div', { class: 'zoom-controls', role: 'group', 'aria-label': 'Zoom' },
    h('button', { type: 'button', 'aria-label': 'Zoom in', onclick: () => zoomBy(1.6) }, '+'),
    h('button', { type: 'button', 'aria-label': 'Zoom out', onclick: () => zoomBy(1 / 1.6) }, '−'),
    h('button', { type: 'button', class: 'zoom-fit', onclick: () => set(1, 0, 0) }, 'Fit'),
    level);
  const stage = h('div', {
    class: 'zoom-stage', tabindex: '0', role: 'group',
    'aria-label': (label || 'Map') + '. Use plus and minus to zoom and the arrow keys to move.',
  }, viewport, controls, hint);

  let scale = 1, tx = 0, ty = 0;

  function clamp() {
    const w = stage.clientWidth, hgt = viewport.offsetHeight;
    tx = Math.min(0, Math.max(w - w * scale, tx));
    ty = Math.min(0, Math.max(hgt - hgt * scale, ty));
  }
  function apply() {
    clamp();
    viewport.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    stage.classList.toggle('is-zoomed', scale > 1.001);
    level.textContent = Math.round(scale * 100) + '%';
  }
  function set(s, x, y) { scale = s; tx = x; ty = y; apply(); }

  /** Zoom keeping the point (px, py) of the stage still. */
  function zoomAt(factor, px, py) {
    const next = Math.min(MAX, Math.max(MIN, scale * factor));
    tx = px - (px - tx) * (next / scale);
    ty = py - (py - ty) * (next / scale);
    scale = next;
    apply();
  }
  function zoomBy(factor) { zoomAt(factor, stage.clientWidth / 2, viewport.offsetHeight / 2); }

  const local = (e) => {
    const r = stage.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const toContent = (px, py) => [(px - tx) / scale, (py - ty) / scale];

  let hintTimer = null;
  stage.addEventListener('wheel', (e) => {
    if (!(e.ctrlKey || e.metaKey)) {
      hint.hidden = false;
      clearTimeout(hintTimer);
      hintTimer = setTimeout(() => { hint.hidden = true; }, 1200);
      return; // let the page scroll
    }
    e.preventDefault();
    const [px, py] = local(e);
    zoomAt(Math.exp(-e.deltaY * 0.0025), px, py);
  }, { passive: false });

  stage.addEventListener('dblclick', (e) => {
    if (e.target.closest('button')) return;
    const [px, py] = local(e);
    if (scale >= MAX - 0.01) set(1, 0, 0); else zoomAt(2, px, py);
  });

  // Pointer drag and pinch.
  const pointers = new Map();
  let drag = null, pinch = null;
  stage.addEventListener('pointerdown', (e) => {
    if (e.target.closest('button, .layers')) return;
    pointers.set(e.pointerId, local(e));
    stage.setPointerCapture(e.pointerId);
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { dist: Math.hypot(a[0] - b[0], a[1] - b[1]), scale };
      drag = null;
    } else if (scale > 1) {
      const [px, py] = local(e);
      drag = { px, py, tx, ty };
      stage.classList.add('is-dragging');
    }
  });
  stage.addEventListener('pointermove', (e) => {
    const [px, py] = local(e);
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, [px, py]);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomAt((pinch.scale * dist / pinch.dist) / scale, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      return;
    }
    if (drag) {
      tx = drag.tx + px - drag.px;
      ty = drag.ty + py - drag.py;
      apply();
      if (onLeave) onLeave();
      return;
    }
    if (onHover && e.pointerType !== 'touch') onHover(...toContent(px, py), px, py);
  });
  const end = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    drag = null;
    stage.classList.remove('is-dragging');
  };
  stage.addEventListener('pointerup', end);
  stage.addEventListener('pointercancel', end);
  stage.addEventListener('pointerleave', () => { if (onLeave) onLeave(); });

  stage.addEventListener('keydown', (e) => {
    if (e.target !== stage) return;
    const step = 40;
    const keys = {
      '+': () => zoomBy(1.6), '=': () => zoomBy(1.6), '-': () => zoomBy(1 / 1.6), '0': () => set(1, 0, 0),
      ArrowLeft: () => { tx += step; apply(); }, ArrowRight: () => { tx -= step; apply(); },
      ArrowUp: () => { ty += step; apply(); }, ArrowDown: () => { ty -= step; apply(); },
    };
    if (keys[e.key]) { e.preventDefault(); keys[e.key](); }
  });
  addEventListener('resize', apply);

  return { el: stage, reset: () => set(1, 0, 0) };
}
