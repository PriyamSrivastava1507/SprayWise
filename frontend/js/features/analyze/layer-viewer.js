// The prescription map: the photo with crop, weed and spray-zone layers that
// can be switched on and off. Crop and weeds come from the result's mask
// (pixel value = class), so the layers are exact. If the mask cannot be read,
// the finished overlay image is shown instead, without toggles.
import { h, loadImage } from '../../utils/dom.js';
import { mediaUrl } from '../../services/api.js';

const CROP = [34, 197, 94];
const WEED = [239, 68, 68];
const ALPHA = 0.55; // the same blend the backend uses for overlay_url
const SPRAY = '#E2A019';

/** Draw the zone grid and outline the zones to spray. */
export function drawZones(ctx, width, height, rows, cols, sprayCells, { fill = 0.16, lines = 'rgba(255,255,255,.2)' } = {}) {
  const spray = new Set(sprayCells.map(([r, c]) => r + ',' + c));
  const cw = width / cols, ch = height / rows;
  const lw = Math.max(1.5, width / 380);
  ctx.save();
  ctx.fillStyle = `rgba(226,160,25,${fill})`;
  for (const key of spray) {
    const [r, c] = key.split(',').map(Number);
    ctx.fillRect(c * cw, r * ch, cw, ch);
  }
  ctx.strokeStyle = lines;
  ctx.lineWidth = Math.max(1, width / 900);
  ctx.beginPath();
  for (let c = 1; c < cols; c++) { ctx.moveTo(c * cw, 0); ctx.lineTo(c * cw, height); }
  for (let r = 1; r < rows; r++) { ctx.moveTo(0, r * ch); ctx.lineTo(width, r * ch); }
  ctx.stroke();
  ctx.strokeStyle = SPRAY;
  ctx.lineWidth = lw;
  for (const key of spray) {
    const [r, c] = key.split(',').map(Number);
    ctx.strokeRect(c * cw + lw / 2, r * ch + lw / 2, cw - lw, ch - lw);
  }
  ctx.restore();
}

/**
 * @param {import('../../services/endpoints.js').Scan} scan
 * @param {import('../../services/endpoints.js').ScanResult} result
 */
export function LayerViewer(scan, result, { zones = true, label = 'Field photo with crop, weed and spray-zone layers' } = {}) {
  const canvas = h('canvas', { width: scan.width, height: scan.height, role: 'img', 'aria-label': label });
  const stage = h('div', { class: 'map-stage is-loading' }, canvas);
  const layers = { crop: true, weed: true, zones };

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

  let base = null, classes = null;
  const ctx = canvas.getContext('2d');

  function paint() {
    if (!base) return;
    const img = new ImageData(new Uint8ClampedArray(base.data), base.width, base.height);
    const d = img.data;
    if (layers.crop || layers.weed) {
      for (let p = 0, i = 0; p < classes.length; p++, i += 4) {
        const cls = classes[p];
        const color = cls === 1 && layers.crop ? CROP : cls === 2 && layers.weed ? WEED : null;
        if (!color) continue;
        d[i] += (color[0] - d[i]) * ALPHA;
        d[i + 1] += (color[1] - d[i + 1]) * ALPHA;
        d[i + 2] += (color[2] - d[i + 2]) * ALPHA;
      }
    }
    ctx.putImageData(img, 0, 0);
    if (layers.zones) drawZones(ctx, canvas.width, canvas.height, scan.params.grid_rows, scan.params.grid_cols, result.spray_cells);
  }

  (async () => {
    try {
      const [photo, mask] = await Promise.all([loadImage(mediaUrl(scan.original_url)), loadImage(mediaUrl(result.mask_url))]);
      ctx.drawImage(photo, 0, 0, canvas.width, canvas.height);
      base = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const m = document.createElement('canvas');
      m.width = canvas.width; m.height = canvas.height;
      const mctx = m.getContext('2d', { willReadFrequently: true });
      mctx.imageSmoothingEnabled = false;
      mctx.drawImage(mask, 0, 0, m.width, m.height);
      const md = mctx.getImageData(0, 0, m.width, m.height).data;
      classes = new Uint8Array(m.width * m.height);
      for (let p = 0; p < classes.length; p++) classes[p] = md[p * 4];
      stage.append(toggles);
      paint();
    } catch {
      // Fallback: the finished overlay picture, plus the zone grid on top.
      try {
        const overlay = await loadImage(mediaUrl(result.overlay_url));
        ctx.drawImage(overlay, 0, 0, canvas.width, canvas.height);
        if (zones) drawZones(ctx, canvas.width, canvas.height, scan.params.grid_rows, scan.params.grid_cols, result.spray_cells);
      } catch {
        stage.append(h('p', { class: 'map-missing' }, 'The images for this scan could not be loaded.'));
      }
    } finally {
      stage.classList.remove('is-loading');
    }
  })();

  return stage;
}
