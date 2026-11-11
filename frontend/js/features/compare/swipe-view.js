// Swipe comparison: one photo, classical on the left of a divider and ML on
// the right. Drag the divider (or use the arrow keys on it) to see where the
// two methods disagree. Spray zones of each method are drawn on its own side.
import { h } from '../../utils/dom.js';
import { drawZones, loadLayers, paintClasses } from '../analyze/map-paint.js';
import { resultLabel } from '../../utils/formatters.js';

export function SwipeView(scan, left, right) {
  const W = scan.width, H = scan.height;
  const canvas = h('canvas', { width: W, height: H, 'aria-hidden': 'true' });
  const divider = h('div', { class: 'swipe-divider', 'aria-hidden': 'true' }, h('span', { class: 'swipe-grip' }));
  const range = h('input', {
    type: 'range', min: '0', max: '100', step: '1', value: '50', class: 'swipe-range',
    'aria-label': 'Divider position: ' + resultLabel(left) + ' on the left, ' + resultLabel(right) + ' on the right',
  });
  const layers = { crop: true, weed: true, zones: true };
  const stage = h('div', { class: 'swipe-stage is-loading' },
    canvas, divider,
    h('span', { class: 'swipe-label swipe-left' }, resultLabel(left)),
    h('span', { class: 'swipe-label swipe-right' }, resultLabel(right)),
    range);

  const toggles = h('div', { class: 'layers swipe-layers', role: 'group', 'aria-label': 'Layers' },
    ...[['crop', 'Crop'], ['weed', 'Weeds'], ['zones', 'Spray zones']].map(([key, text]) =>
      h('button', {
        type: 'button', class: 'layer', 'data-layer': key, 'aria-pressed': 'true',
        onclick: (e) => { layers[key] = !layers[key]; e.currentTarget.setAttribute('aria-pressed', String(layers[key])); paint(); },
      }, h('i', { 'aria-hidden': 'true' }), text)));

  const ctx = canvas.getContext('2d');
  let data = null;

  function paint() {
    const split = Math.round(W * Number(range.value) / 100);
    divider.style.left = range.value + '%';
    range.setAttribute('aria-valuetext', range.value + '% ' + resultLabel(left));
    if (!data) return;
    ctx.putImageData(paintClasses(data.base, data.masks, layers, (x) => (x < split ? 0 : 1)), 0, 0);
    if (layers.zones) {
      const { grid_rows: rows, grid_cols: cols } = scan.params;
      drawZones(ctx, W, H, rows, cols, left.spray_cells, { x0: 0, x1: split });
      drawZones(ctx, W, H, rows, cols, right.spray_cells, { x0: split, x1: W });
    }
  }
  range.addEventListener('input', paint);

  // Clicking anywhere on the photo moves the divider there.
  stage.addEventListener('pointerdown', (e) => {
    if (e.target === range || e.target.closest('button')) return;
    const r = stage.getBoundingClientRect();
    range.value = String(Math.round(((e.clientX - r.left) / r.width) * 100));
    paint();
  });

  loadLayers(scan, W, H, [left.mask_url, right.mask_url])
    .then((d) => { data = d; stage.append(toggles); paint(); })
    .catch(() => stage.append(h('p', { class: 'map-missing' }, 'The masks for this scan could not be loaded.')))
    .finally(() => stage.classList.remove('is-loading'));
  paint();

  const diff = left.weed_pct != null && right.weed_pct != null
    ? 'Weed cover: ' + resultLabel(left) + ' ' + left.weed_pct.toFixed(1) + '%, ' +
      resultLabel(right) + ' ' + right.weed_pct.toFixed(1) + '%. Zones to spray: ' +
      left.spray_cells.length + ' and ' + right.spray_cells.length + '.'
    : '';
  return h('div', { class: 'swipe' }, stage, h('p', { class: 'note' }, 'Drag the divider or click the photo. ' + diff));
}
