// Evaluation: every method and ML model scored on labelled test photos, from
// GET /evaluation. One table per test set, one column per method or model.
// Honesty rules: a model with no stored result says "Not evaluated yet", and
// the number of photos actually scored is always shown next to the scores.
import { h } from '../../utils/dom.js';
import { isAbort } from '../../services/api.js';
import { evaluationApi } from '../../services/endpoints.js';
import { ErrorState, EmptyState } from '../../components/states.js';
import { fmtMs, DASH } from '../../utils/formatters.js';

const SOIL = 0, CROP = 1, WEED = 2;
const score = (v) => (v == null ? DASH : Number(v).toFixed(2));
const at = (arr, i) => (Array.isArray(arr) ? arr[i] : null);
const scored = (m) => m && m.n_evaluated > 0;

const ROWS = [
  ['Photos scored', (m) => m.n_evaluated + ' of ' + m.n_images],
  ['Crop IoU', (m) => (scored(m) ? score(at(m.iou, CROP)) : DASH)],
  ['Weed IoU', (m) => (scored(m) ? score(at(m.iou, WEED)) : DASH)],
  ['Mean IoU, crop and weed', (m) => (scored(m) ? score(m.mean_iou_crop_weed) : DASH)],
  ['Weed precision', (m) => (scored(m) ? score(at(m.precision, WEED)) : DASH)],
  ['Weed recall', (m) => (scored(m) ? score(at(m.recall, WEED)) : DASH)],
  ['Soil IoU', (m) => (scored(m) ? score(at(m.iou, SOIL)) : DASH)],
  ['Time per photo', (m) => fmtMs(m.ms_per_image)],
];

/** Classical first, then models in the server's order, then anything else. */
function order(data) {
  const keys = ['classical', ...data.models.map((m) => 'ml-' + m.key)];
  return (variant) => { const i = keys.indexOf(variant); return i === -1 ? keys.length : i; };
}

function bestOf(entries, pick) {
  let best = null;
  for (const e of entries) {
    const v = scored(e.metrics) ? pick(e.metrics) : null;
    if (v != null && (best == null || v > best)) best = v;
  }
  return best;
}

function DatasetTable(dataset, entries) {
  // Highlight the best mean IoU only when more than one column has a score.
  const meanIou = (m) => m.mean_iou_crop_weed;
  const best = entries.filter((e) => scored(e.metrics)).length > 1 ? bestOf(entries, meanIou) : null;
  return h('section', { class: 'panel eval-set' },
    h('h2', { class: 'panel-title' }, dataset),
    h('div', { class: 'table-wrap' },
      h('table', { class: 'eval-table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Measure'), entries.map((e) => h('th', { class: 'num' }, e.label)))),
        h('tbody', {}, ROWS.map(([label, fn]) => h('tr', {},
          h('th', { scope: 'row' }, label),
          entries.map((e) => {
            const v = fn(e.metrics);
            const top = best != null && label === 'Mean IoU, crop and weed' && scored(e.metrics) && meanIou(e.metrics) === best;
            return h('td', { class: 'num' + (v === DASH ? ' dash' : '') + (top ? ' best' : '') }, v, top ? h('span', { class: 'visually-hidden' }, ' (best)') : null);
          })))))));
}

function notes(data, entries) {
  const out = [];
  for (const e of entries.filter((x) => x.method === 'classical')) {
    const m = e.metrics;
    if (m.rows_detected_rate != null && m.rows_detected_rate < 1) {
      out.push(['warn', 'Classical found crop rows in ' + m.n_evaluated + ' of ' + m.n_images + ' photos (' + e.dataset + ')',
        m.n_evaluated === 0
          ? 'Photos without detectable rows are left out rather than counted as correct, so there are no classical scores here. The method is being tuned.'
          : 'Its scores cover only those ' + m.n_evaluated + ' photos. Photos without detectable rows are left out rather than counted as correct.']);
    }
  }
  if (!entries.some((e) => e.method === 'classical')) {
    out.push(['neutral', 'Classical has not been evaluated yet', 'Run scripts/evaluate.py on a labelled test set to add it.']);
  }
  for (const model of data.models) {
    if (!entries.some((e) => e.model_key === model.key)) {
      out.push(['neutral', model.label + ' has not been evaluated yet',
        'Run scripts/evaluate.py with --model ' + model.key + ' on the same test photos to add its column.']);
    }
  }
  const sets = new Set(entries.map((e) => e.dataset));
  if (data.models.length > 1 && sets.size === 1 && entries.some((e) => e.method === 'ml')) {
    out.push(['neutral', 'Scored on one test set only',
      'A model usually does best on photos like the ones it was trained on. Scores on a second test set show whether one model is better in general.']);
  }
  return out;
}

function TrainingReport(label, report) {
  const rows = Object.entries(report).filter(([, v]) => typeof v === 'number' || typeof v === 'string').slice(0, 12);
  if (!rows.length) return null;
  return h('section', { class: 'panel' },
    h('h2', { class: 'panel-title' }, 'Training report: ' + label),
    h('p', { class: 'note' }, 'As reported by the ML team, measured during training. Not the same test run as the tables.'),
    h('dl', { class: 'kv' }, rows.map(([k, v]) => [h('dt', {}, k.replace(/_/g, ' ')),
      h('dd', {}, typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(3) : String(v)) : v)])));
}

export async function mount(root) {
  const ctrl = new AbortController();
  let data;
  try {
    data = await evaluationApi.get(ctrl.signal);
  } catch (err) {
    if (isAbort(err)) return null;
    root.replaceChildren(ErrorState(err, () => mount(root)));
    return null;
  }

  const rank = order(data);
  const entries = (data.entries || []).slice().sort((a, b) => rank(a.variant) - rank(b.variant));
  const byDataset = new Map();
  for (const e of entries) {
    if (!byDataset.has(e.dataset)) byDataset.set(e.dataset, []);
    byDataset.get(e.dataset).push(e);
  }
  const labelOf = (key) => (data.models.find((m) => m.key === key) || { label: key }).label;

  root.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'Evaluation'),
      h('p', {}, 'Each method and model scored on hand-labelled test photos. One table per test set.')),
    h('div', { class: 'eval-grid' },
      h('div', { class: 'eval-main' },
        byDataset.size
          ? [...byDataset].map(([dataset, list]) => DatasetTable(dataset, list))
          : EmptyState('Nothing has been evaluated yet', 'Results appear here once scripts/evaluate.py has scored a method or model on labelled photos.'),
        h('p', { class: 'note' }, 'IoU (intersection over union) compares the pixels labelled as crop or weed with hand-labelled ones: 1.00 is a perfect match. Precision is the share of predicted weed pixels that really are weeds; recall is the share of real weed pixels that were found. The best mean IoU in a table is marked.')),
      h('div', { class: 'eval-side' },
        notes(data, entries).map(([tone, title, text]) => h('div', { class: 'callout callout-' + tone }, h('h2', {}, title), h('p', {}, text))),
        Object.entries(data.training_reports || {}).map(([key, report]) => TrainingReport(labelOf(key), report)))));
  return () => ctrl.abort();
}
