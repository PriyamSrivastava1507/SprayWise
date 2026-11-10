// The two zone maps under the prescription map, drawn from result.grid
// (weed share per zone, 0..1, indexed [row][col]) and result.spray_cells.
import { h, loadImage } from '../../utils/dom.js';
import { mediaUrl } from '../../services/api.js';
import { densest, heatColor } from '../../utils/calculations.js';
import { drawZones, zoneAt } from './map-paint.js';
import { ZoneTooltip } from './zone-tooltip.js';

const W = 480;

/** Wrap a zone canvas so hovering it describes the zone underneath. */
function withTooltip(canvas, scan, result) {
  const wrap = h('div', { class: 'mini-map' }, canvas);
  const tip = ZoneTooltip(wrap);
  canvas.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') return;
    const r = canvas.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    tip.show(zoneAt(scan, result, x, y, r.width, r.height), x, y, scan.params.cell_threshold);
  });
  canvas.addEventListener('pointerleave', () => tip.hide());
  return wrap;
}

function sizeFor(scan) {
  return { width: W, height: Math.round(W * scan.height / scan.width) };
}

export function HeatMap(scan, result) {
  const { width, height } = sizeFor(scan);
  const grid = result.grid, rows = grid.length, cols = grid[0].length;
  const top = densest(grid);
  const scale = top.value > 0 ? top.value : 1;
  const canvas = h('canvas', { class: 'zone-canvas', width, height, role: 'img',
    'aria-label': 'Weed density per zone. The densest zone is row ' + (top.row + 1) + ', column ' + (top.col + 1) + '.' });
  const ctx = canvas.getContext('2d');
  const cw = width / cols, ch = height / rows;
  grid.forEach((line, r) => line.forEach((v, c) => {
    ctx.fillStyle = heatColor(v / scale);
    ctx.fillRect(Math.floor(c * cw), Math.floor(r * ch), Math.ceil(cw) + 1, Math.ceil(ch) + 1);
  }));
  ctx.strokeStyle = 'rgba(30,43,36,.09)';
  ctx.beginPath();
  for (let c = 1; c < cols; c++) { ctx.moveTo(c * cw, 0); ctx.lineTo(c * cw, height); }
  for (let r = 1; r < rows; r++) { ctx.moveTo(0, r * ch); ctx.lineTo(width, r * ch); }
  ctx.stroke();

  const maxPct = Math.round(top.value * 100);
  return h('section', { class: 'mini' },
    h('h3', {}, 'Weed density'),
    withTooltip(canvas, scan, result),
    h('div', { class: 'key' }, h('span', {}, 'None'), h('span', { class: 'ramp', 'aria-hidden': 'true' }), h('span', {}, maxPct + '%')),
    h('p', { class: 'note' }, top.value > 0
      ? 'Densest zone: row ' + (top.row + 1) + ', column ' + (top.col + 1) + ', ' + maxPct + '% weeds.'
      : 'No weeds were found in any zone.'));
}

export function SprayMap(scan, result) {
  const { width, height } = sizeFor(scan);
  const canvas = h('canvas', { class: 'zone-canvas', width, height, role: 'img',
    'aria-label': result.spray_cells.length + ' zones to spray, outlined in amber.' });
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#E9EBE6';
  ctx.fillRect(0, 0, width, height);
  const draw = () => drawZones(ctx, width, height, scan.params.grid_rows, scan.params.grid_cols, result.spray_cells,
    { fill: 0.55, lines: 'rgba(30,43,36,.12)' });
  loadImage(mediaUrl(scan.original_url)).then((photo) => {
    ctx.drawImage(photo, 0, 0, width, height);
    ctx.fillStyle = 'rgba(242,243,239,.72)';
    ctx.fillRect(0, 0, width, height);
    draw();
  }).catch(draw);
  draw();

  const pct = Math.round(scan.params.cell_threshold * 100);
  return h('section', { class: 'mini' },
    h('h3', {}, 'Spray zones'),
    withTooltip(canvas, scan, result),
    h('p', { class: 'note' }, result.spray_cells.length
      ? 'Zones where weeds cover more than ' + pct + '% are sprayed. The rest of the field is skipped.'
      : 'No zone has more than ' + pct + '% weed cover, so nothing needs spraying.'));
}
