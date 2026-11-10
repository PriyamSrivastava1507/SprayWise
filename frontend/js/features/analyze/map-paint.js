// Shared drawing for the map views: colour the crop/weed classes of a mask over
// the photo, draw the zone grid, and describe one zone for tooltips.
import { loadImage } from '../../utils/dom.js';
import { mediaUrl } from '../../services/api.js';

const CROP = [34, 197, 94];
const WEED = [239, 68, 68];
const ALPHA = 0.55; // the same blend the backend uses for overlay_url
export const SPRAY = '#E2A019';

/** Load the photo and a result's mask; returns { photo ImageData, classes }. */
export async function loadLayers(scan, width, height, maskUrls) {
  const photo = await loadImage(mediaUrl(scan.original_url));
  const c = document.createElement('canvas');
  c.width = width; c.height = height;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(photo, 0, 0, width, height);
  const base = ctx.getImageData(0, 0, width, height);
  const masks = await Promise.all(maskUrls.map(async (url) => {
    const img = await loadImage(mediaUrl(url));
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0, width, height);
    const d = ctx.getImageData(0, 0, width, height).data;
    const classes = new Uint8Array(width * height);
    for (let p = 0; p < classes.length; p++) classes[p] = d[p * 4];
    return classes;
  }));
  return { base, masks };
}

/**
 * Blend crop and weed colours into a copy of `base`.
 * `pick(x)` chooses which mask applies at column x (used by the swipe view).
 */
export function paintClasses(base, masks, layers, pick = () => 0) {
  const img = new ImageData(new Uint8ClampedArray(base.data), base.width, base.height);
  if (!layers.crop && !layers.weed) return img;
  const d = img.data, w = base.width;
  const choice = new Uint8Array(w);
  for (let x = 0; x < w; x++) choice[x] = pick(x);
  for (let p = 0, i = 0; p < masks[0].length; p++, i += 4) {
    const cls = masks[choice[p % w]][p];
    const color = cls === 1 && layers.crop ? CROP : cls === 2 && layers.weed ? WEED : null;
    if (!color) continue;
    d[i] += (color[0] - d[i]) * ALPHA;
    d[i + 1] += (color[1] - d[i + 1]) * ALPHA;
    d[i + 2] += (color[2] - d[i + 2]) * ALPHA;
  }
  return img;
}

/** Draw the zone grid and outline the zones to spray. */
export function drawZones(ctx, width, height, rows, cols, sprayCells, { fill = 0.16, lines = 'rgba(255,255,255,.2)', x0 = 0, x1 = width } = {}) {
  const spray = new Set(sprayCells.map(([r, c]) => r + ',' + c));
  const cw = width / cols, ch = height / rows;
  const lw = Math.max(1.5, width / 380);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x0, 0, x1 - x0, height);
  ctx.clip();
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

/** The zone under an image point, with its weed share and spray decision. */
export function zoneAt(scan, result, x, y, width, height) {
  const rows = scan.params.grid_rows, cols = scan.params.grid_cols;
  if (x < 0 || y < 0 || x >= width || y >= height || !result.grid) return null;
  const row = Math.min(rows - 1, Math.floor(y / (height / rows)));
  const col = Math.min(cols - 1, Math.floor(x / (width / cols)));
  const density = (result.grid[row] || [])[col];
  if (density == null) return null;
  const sprayed = result.spray_cells.some(([r, c]) => r === row && c === col);
  return { row, col, density, sprayed };
}
