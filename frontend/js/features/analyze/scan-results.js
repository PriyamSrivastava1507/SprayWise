// Everything about one scan: the meta line, a method switcher when both
// methods ran, and one result panel. Every result has the same shape; the
// panel branches on `status` first, because non-ok results carry nulls.
import { h } from '../../utils/dom.js';
import { mediaUrl } from '../../services/api.js';
import { scansApi } from '../../services/endpoints.js';
import { whenHealth } from '../../components/health.js';
import { pressurePosition } from '../../utils/calculations.js';
import {
  fmtDate, fmtLitres, fmtMoney, fmtMs, fmtNumber, fmtFixed, fmtPct, isDemo, methodLabel,
} from '../../utils/formatters.js';
import { LayerViewer } from './layer-viewer.js';
import { HeatMap, SprayMap } from './grid-map.js';

// ---------------------------------------------------------------- tags

export function StatusTag(result) {
  const map = {
    ok: null,
    rows_not_detected: ['No rows found', 'tag-muted'],
    model_unavailable: ['Model offline', 'tag-muted'],
    failed: ['Failed', 'tag-bad'],
  };
  const t = map[result.status];
  return t ? h('span', { class: 'tag ' + t[1] }, t[0]) : null;
}

export const DemoTag = (result) => (isDemo(result)
  ? h('span', { class: 'tag tag-demo', title: 'Produced by a placeholder model, not a trained one.' }, 'Demo model')
  : null);

export const PressureTag = (pressure) => (pressure
  ? h('span', { class: 'tag tag-' + pressure.toLowerCase() }, pressure)
  : null);

// ---------------------------------------------------------------- non-ok results

const ROW_REASONS = {
  too_little_vegetation: ['There is too little vegetation to find crop rows',
    'Only a small part of the photo is green plants, so the row pattern cannot be measured. Check that the photo shows the crop.'],
  default: ['Crop rows weren’t detected in this photo',
    'The classical method separates crop from weeds by finding regularly spaced rows. Here the row pattern was too weak to measure. ML segmentation does not need rows.'],
};
const FAIL_REASONS = {
  invalid_model_output: 'The model returned a mask the app could not use.',
  inference_error: 'The model stopped with an error while processing this photo.',
};

export function StatusPanel(scan, result, { onRerun } = {}) {
  let title, text, action = null;
  if (result.status === 'rows_not_detected') {
    [title, text] = ROW_REASONS[result.status_detail] || ROW_REASONS.default;
    if (onRerun) action = h('button', { type: 'button', class: 'btn btn-quiet', onclick: () => onRerun('ml') }, 'Run ML on this photo');
  } else if (result.status === 'model_unavailable') {
    title = 'The ML model is offline';
    text = (result.status_detail ? result.status_detail.replace(/\.?$/, '. ') : '') + 'Classical results are not affected.';
  } else {
    title = methodLabel(result.method) + ' failed on this photo';
    text = FAIL_REASONS[result.status_detail] || 'Try again, or use the other method.';
  }
  return h('div', { class: 'blocked', style: { backgroundImage: `url("${mediaUrl(scan.original_url)}")` } },
    h('div', { class: 'blocked-card' },
      h('h3', {}, title), h('p', {}, text),
      result.status_detail ? h('p', { class: 'blocked-code' }, 'Reason code: ' + result.status_detail) : null,
      action));
}

// ---------------------------------------------------------------- ok results

function Answer(scan, result) {
  const total = scan.params.grid_rows * scan.params.grid_cols;
  const n = result.spray_cells.length;
  const s = result.savings;
  let head;
  if (n === 0) head = h('h1', { class: 'answer' }, 'No zones need spraying.');
  else if (n === total) head = h('h1', { class: 'answer' }, 'Spray all ', h('em', {}, String(total)), ' zones.');
  else head = h('h1', { class: 'answer' }, 'Spray ', h('em', {}, n + ' of ' + total), ' zones.');

  const sub = n === total
    ? h('p', { class: 'answer-sub' }, 'Weeds are spread across the whole photo, so spot spraying saves nothing here. Spraying all ',
      h('b', {}, fmtNumber(scan.params.area_ha) + ' ha'), ' takes ', h('b', {}, fmtLitres(s.blanket_litres)), '.')
    : h('p', { class: 'answer-sub' }, 'Spot spraying uses ', h('b', {}, fmtLitres(s.spot_litres)), ' instead of ',
      h('b', {}, fmtLitres(s.blanket_litres)), ' on this ', fmtNumber(scan.params.area_ha), ' ha field and saves ',
      h('b', {}, fmtMoney(s.saved_cost)), ' compared with spraying all of it.');
  return [head, sub];
}

function Readout(scan, result) {
  const soil = result.vegetation_pct == null ? null : Math.max(0, 100 - result.vegetation_pct);
  const pct = (v) => Math.max(0, v || 0) + '%';
  const scale = h('div', { class: 'scale-wrap' });

  whenHealth().then((health) => {
    const t = health && health.pressure_thresholds;
    const pos = pressurePosition(result.weed_pct, t);
    if (pos == null) return;
    scale.replaceChildren(
      h('div', { class: 'scale', 'aria-hidden': 'true' }, h('i', { style: { left: (pos * 100).toFixed(1) + '%' } })),
      h('div', { class: 'scale-labels', 'aria-hidden': 'true' },
        h('span', {}, '0%'), h('span', {}, fmtNumber(t.low_max, 1) + '%'),
        h('span', {}, fmtNumber(t.high_min, 1) + '%'), h('span', {}, '')),
      h('p', { class: 'visually-hidden' }, 'Low below ' + t.low_max + '% weed cover, High from ' + t.high_min + '%.'));
  });

  const kv = [
    ['Spray threshold', Math.round(scan.params.cell_threshold * 100) + '% weeds'],
    ['Zones', scan.params.grid_rows + ' × ' + scan.params.grid_cols],
    result.model_id ? ['Model', result.model_id] : null,
    ['Processing', fmtMs(result.processing_ms)],
  ].filter(Boolean);

  return h('div', { class: 'readout' },
    h('div', {},
      h('h3', {}, 'Ground cover'),
      h('div', { class: 'comp-bar', 'aria-hidden': 'true' },
        h('span', { style: { width: pct(soil), background: 'var(--soil)' } }),
        h('span', { style: { width: pct(result.crop_pct), background: 'var(--crop)' } }),
        h('span', { style: { width: pct(result.weed_pct), background: 'var(--weed)' } })),
      h('dl', { class: 'comp-legend' },
        h('div', {}, h('dt', {}, h('i', { style: { background: 'var(--weed)' } }), 'Weeds'), h('dd', {}, fmtPct(result.weed_pct))),
        h('div', {}, h('dt', {}, h('i', { style: { background: 'var(--crop)' } }), 'Crop'), h('dd', {}, fmtPct(result.crop_pct))),
        h('div', {}, h('dt', {}, h('i', { style: { background: 'var(--soil)' } }), 'Bare soil'), h('dd', {}, fmtPct(soil))))),
    h('div', {},
      h('div', { class: 'pressure-line' }, h('h3', {}, 'Weed pressure'), PressureTag(result.pressure)),
      scale),
    h('dl', { class: 'kv-mini' }, kv.map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', {}, v)))),
    Downloads(scan, result));
}

export function Downloads(scan, result) {
  return h('div', { class: 'downloads' },
    h('a', { class: 'btn btn-quiet', href: scansApi.exportUrl(scan.id, 'csv', result.method) }, 'CSV'),
    h('a', { class: 'btn btn-quiet', href: scansApi.exportUrl(scan.id, 'pdf', result.method) }, 'PDF report'));
}

function CostTable(scan, result) {
  const s = result.savings;
  return h('section', { class: 'mini' },
    h('h3', {}, 'Herbicide and cost'),
    h('table', { class: 'cost-table' },
      h('thead', {}, h('tr', {}, h('th', {}, h('span', { class: 'visually-hidden' }, 'Plan')), h('th', { class: 'num' }, 'Litres'), h('th', { class: 'num' }, 'Cost'))),
      h('tbody', {},
        h('tr', {}, h('td', {}, 'Spray everything'), h('td', { class: 'num' }, fmtFixed(s.blanket_litres)), h('td', { class: 'num' }, fmtMoney(s.blanket_cost))),
        h('tr', {}, h('td', {}, 'Spray ' + result.spray_cells.length + ' zones'), h('td', { class: 'num' }, fmtFixed(s.spot_litres)), h('td', { class: 'num' }, fmtMoney(s.spot_cost))),
        h('tr', { class: 'total' }, h('td', {}, 'Saved'), h('td', { class: 'num' }, fmtFixed(s.saved_litres)), h('td', { class: 'num' }, fmtMoney(s.saved_cost))))),
    h('p', { class: 'note' }, 'Based on ' + fmtNumber(scan.params.dose_l_per_ha) + ' L/ha at ' + fmtMoney(scan.params.price_per_l) +
      ' per litre. Assumes cost scales with sprayed area; nozzle overlap is not counted.'));
}

/** The full view of one result (Analyze page and scan detail). */
export function ResultPanel(scan, result, { onRerun } = {}) {
  if (result.status !== 'ok') {
    return h('div', { class: 'result' }, StatusPanel(scan, result, { onRerun }));
  }
  return h('div', { class: 'result' },
    ...Answer(scan, result),
    h('div', { class: 'map-block' }, LayerViewer(scan, result), Readout(scan, result)),
    h('div', { class: 'lower' }, HeatMap(scan, result), SprayMap(scan, result), CostTable(scan, result)));
}

// ---------------------------------------------------------------- the scan

export function ScanMeta(scan, result, extra) {
  return h('div', { class: 'result-meta' },
    h('strong', {}, scan.field ? scan.field.name : 'No field'),
    h('a', { href: '#/scans/' + scan.id }, 'Scan ' + scan.id),
    h('span', {}, h('time', { datetime: scan.created_at }, fmtDate(scan.created_at))),
    result ? h('span', { class: 'tag' }, methodLabel(result.method)) : null,
    result ? StatusTag(result) : null,
    result ? DemoTag(result) : null,
    extra || null);
}

export function ScanView(scan, { method, onRerun } = {}) {
  const root = h('div', { class: 'scan-view' });
  const initial = scan.results.find((r) => r.method === method) ||
    scan.results.find((r) => r.status === 'ok') || scan.results[0];

  function show(result) {
    const tabs = scan.results.length > 1
      ? h('div', { class: 'method-tabs', role: 'tablist', 'aria-label': 'Method' },
        scan.results.map((r) => h('button', {
          type: 'button', role: 'tab', 'aria-selected': String(r === result),
          onclick: () => show(r),
        }, methodLabel(r.method), r.status !== 'ok' ? h('span', { class: 'tab-note' }, 'no result') : null)))
      : null;
    root.replaceChildren(...[ScanMeta(scan, result), tabs, ResultPanel(scan, result, { onRerun })].filter(Boolean));
  }
  show(initial);
  return root;
}
