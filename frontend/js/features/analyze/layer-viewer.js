// The prescription map: the photo with crop, weed and spray-zone layers that
// can be switched on and off, zoom and pan, and a tooltip for the zone under
// the pointer. Crop and weeds come from the result's mask (pixel value =
// class), so the layers are exact. If the mask cannot be read, the finished
// overlay picture is shown instead, without the crop/weed switches.
//
// The returned element has update(scan, result): used while recalculating,
// it redraws the zones without reloading images or losing the zoom.
import { h, loadImage } from '../../utils/dom.js';
import { mediaUrl } from '../../services/api.js';
import { drawZones, loadLayers, paintClasses, zoneAt } from './map-paint.js';
import { ZoneTooltip } from './zone-tooltip.js';
import { ZoomStage } from './zoom-stage.js';

export { drawZones };

export function LayerViewer(scan, result, { zones = true, label = 'Field photo with crop, weed and spray-zone layers' } = {}) {
  const W = scan.width, H = scan.height;
  const canvas = h('canvas', { width: W, height: H, 'aria-hidden': 'true' });
  const hover = h('canvas', { class: 'hover-layer', width: W, height: H, 'aria-hidden': 'true' });
  const layers = { crop: true, weed: true, zones };
  let current = { scan, result };
  let base = null, masks = null, overlayImg = null, lastZone = null;

  const shell = h('div', { class: 'map-stage is-loading' });
  const tooltip = ZoneTooltip(shell);
  const zoom = ZoomStage(h('div', { class: 'map-content' }, canvas, hover), {
    label,
    onHover: (cx, cy, px, py) => {
      const k = W / zoom.el.clientWidth;
      const zone = zoneAt(current.scan, current.result, cx * k, cy * k, W, H);
      tooltip.show(zone, px, py, current.scan.params.cell_threshold);
      highlight(zone);
    },
    onLeave: () => { tooltip.hide(); highlight(null); },
  });
  shell.append(zoom.el);

  const toggles = h('div', { class: 'layers', role: 'group', 'aria-label': 'Map layers' },
    ...[['crop', 'Crop'], ['weed', 'Weeds'], ['zones', 'Spray zones']].map(([key, text]) =>
      h('button', {
        type: 'button', class: 'layer', 'data-layer': key, 'aria-pressed': String(layers[key]),
        onclick: (e) => {
          layers[key] = !layers[key];
          e.currentTarget.setAttribute('aria-pressed', String(layers[key]));
          paint();
        },
      }, h('i', { 'aria-hidden': 'true' }), text)));

  const ctx = canvas.getContext('2d');
  const hctx = hover.getContext('2d');

  function paint() {
    const { scan: s, result: r } = current;
    if (base) ctx.putImageData(paintClasses(base, masks, layers), 0, 0);
    else if (overlayImg) ctx.drawImage(overlayImg, 0, 0, W, H);
    else return;
    if (layers.zones) drawZones(ctx, W, H, s.params.grid_rows, s.params.grid_cols, r.spray_cells);
  }

  function highlight(zone) {
    const key = zone ? zone.row + ',' + zone.col : null;
    if (key === lastZone) return;
    lastZone = key;
    hctx.clearRect(0, 0, W, H);
    if (!zone) return;
    const { grid_rows: rows, grid_cols: cols } = current.scan.params;
    const cw = W / cols, ch = H / rows, lw = Math.max(2, W / 300);
    hctx.strokeStyle = '#fff';
    hctx.lineWidth = lw;
    hctx.strokeRect(zone.col * cw + lw / 2, zone.row * ch + lw / 2, cw - lw, ch - lw);
  }

  (async () => {
    try {
      ({ base, masks } = await loadLayers(scan, W, H, [result.mask_url]));
      shell.append(toggles);
    } catch {
      try { overlayImg = await loadImage(mediaUrl(result.overlay_url)); } catch { /* handled below */ }
    }
    if (!base && !overlayImg) shell.append(h('p', { class: 'map-missing' }, 'The images for this scan could not be loaded.'));
    paint();
    shell.classList.remove('is-loading');
  })();

  shell.update = (nextScan, nextResult) => {
    current = { scan: nextScan, result: nextResult };
    lastZone = null;
    hctx.clearRect(0, 0, W, H);
    paint();
  };
  return shell;
}
