// Weed cover over time for one field, as an SVG line chart with the
// Low / Medium / High bands behind it. Points come from /fields/{id}/trend.
import { h, s } from '../../utils/dom.js';
import { fmtDay, fmtPct, fmtDate, fmtTime } from '../../utils/formatters.js';

export function TrendChart(points, thresholds) {
  const W = 1000, H = 260, L = 48, R = 24, T = 18, B = 34;
  const values = points.map((p) => p.weed_pct);
  const top = Math.max(...values, thresholds ? thresholds.high_min * 1.15 : 0, 5);
  const yMax = Math.ceil(top / 5) * 5;
  const x = (i) => (points.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (points.length - 1));
  const y = (v) => T + (1 - v / yMax) * (H - T - B);

  const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'trend-svg', role: 'img',
    'aria-label': 'Weed cover from ' + fmtPct(values[0]) + ' on ' + fmtDay(points[0].created_at) +
      ' to ' + fmtPct(values[values.length - 1]) + ' on ' + fmtDay(points[points.length - 1].created_at) + '.' });

  if (thresholds) {
    const lo = Math.min(thresholds.low_max, yMax), hi = Math.min(thresholds.high_min, yMax);
    svg.append(
      s('rect', { x: L, y: y(hi), width: W - L - R, height: y(lo) - y(hi), class: 'band-medium' }),
      s('rect', { x: L, y: y(yMax), width: W - L - R, height: Math.max(0, y(hi) - y(yMax)), class: 'band-high' }),
      s('text', { x: W - R - 8, y: y(hi) + 16, 'text-anchor': 'end', class: 'band-label' }, 'Medium pressure'),
      hi < yMax ? s('text', { x: W - R - 8, y: y(yMax) + 16, 'text-anchor': 'end', class: 'band-label high' }, 'High pressure') : null,
    );
  }
  const step = yMax <= 20 ? 5 : 10;
  for (let v = 0; v <= yMax; v += step) {
    svg.append(s('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'gridline' }),
      s('text', { x: L - 10, y: y(v) + 4, 'text-anchor': 'end', class: 'axis' }, v + '%'));
  }
  if (points.length > 1) {
    svg.append(s('polyline', { points: points.map((p, i) => x(i) + ',' + y(p.weed_pct)).join(' '), class: 'trend-line' }));
  }
  const days = new Set(points.map((p) => fmtDay(p.created_at)));
  const tick = days.size === 1 ? fmtTime : fmtDay; // one day: show times instead
  const every = Math.ceil(points.length / 8);
  points.forEach((p, i) => {
    const last = i === points.length - 1;
    svg.append(s('circle', { cx: x(i), cy: y(p.weed_pct), r: 4.5, class: 'trend-dot' },
      s('title', {}, fmtDate(p.created_at) + ': ' + fmtPct(p.weed_pct) + ' weeds')));
    if (i % every === 0 || last) svg.append(s('text', { x: x(i), y: H - 10, 'text-anchor': 'middle', class: 'axis' }, tick(p.created_at)));
  });
  const peak = values.indexOf(Math.max(...values));
  for (const i of new Set([peak, points.length - 1])) {
    svg.append(s('text', { x: x(i), y: y(values[i]) - 12, 'text-anchor': 'middle', class: 'point-label' }, fmtPct(values[i])));
  }
  return h('div', { class: 'trend' }, svg);
}
