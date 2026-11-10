// Small helpers for drawing. Figures shown to the user come from the API;
// nothing here recomputes savings or statistics.

export const okResults = (scan) => scan.results.filter((r) => r.status === 'ok');

/** The result a list row should summarise: the first successful one. */
export const primaryResult = (scan) => okResults(scan)[0] || null;

export function densest(grid) {
  let best = { value: -1, row: 0, col: 0 };
  grid.forEach((line, row) => line.forEach((value, col) => {
    if (value > best.value) best = { value, row, col };
  }));
  return best;
}

/** Paper (no weeds) to deep red (most weeds). t is 0..1. */
const STOPS = [[247, 246, 241], [244, 180, 164], [226, 90, 74], [180, 35, 35]];
export function heatColor(t) {
  const x = Math.min(0.999, Math.max(0, t)) * (STOPS.length - 1);
  const i = Math.floor(x), f = x - i;
  const [r, g, b] = STOPS[i].map((v, k) => Math.round(v + (STOPS[i + 1][k] - v) * f));
  return `rgb(${r},${g},${b})`;
}

/** Where a weed % falls on the Low / Medium / High scale, 0..1 for drawing. */
export function pressurePosition(weedPct, t) {
  if (weedPct == null || !t) return null;
  const top = t.high_min * 2; // the High band is drawn as wide as the others
  if (weedPct < t.low_max) return (weedPct / t.low_max) / 3;
  if (weedPct < t.high_min) return 1 / 3 + ((weedPct - t.low_max) / (t.high_min - t.low_max)) / 3;
  return 2 / 3 + Math.min(1, (weedPct - t.high_min) / (top - t.high_min)) / 3;
}
