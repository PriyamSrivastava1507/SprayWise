// Evaluation: classical vs ML on labelled test photos, from GET /evaluation.
// Honesty rules: a missing file is "Not evaluated yet", and the number of
// photos actually scored is always shown next to the scores.
import { h } from '../../utils/dom.js';
import { isAbort } from '../../services/api.js';
import { evaluationApi } from '../../services/endpoints.js';
import { ErrorState } from '../../components/states.js';
import { fmtMs, DASH } from '../../utils/formatters.js';

const SOIL = 0, CROP = 1, WEED = 2;
const score = (v) => (v == null ? DASH : v.toFixed(2));
const at = (arr, i) => (Array.isArray(arr) ? arr[i] : null);

// A method's numbers are only meaningful when at least one photo was scored.
const scored = (m) => m && m.n_evaluated > 0;

const ROWS = [
  ['Photos scored', (m) => (m ? m.n_evaluated + ' of ' + m.n_images : null)],
  ['Crop IoU', (m) => (scored(m) ? score(at(m.iou, CROP)) : DASH)],
  ['Weed IoU', (m) => (scored(m) ? score(at(m.iou, WEED)) : DASH)],
  ['Mean IoU, crop and weed', (m) => (scored(m) ? score(m.mean_iou_crop_weed) : DASH)],
  ['Weed precision', (m) => (scored(m) ? score(at(m.precision, WEED)) : DASH)],
  ['Weed recall', (m) => (scored(m) ? score(at(m.recall, WEED)) : DASH)],
  ['Soil IoU', (m) => (scored(m) ? score(at(m.iou, SOIL)) : DASH)],
  ['Time per photo', (m) => (m ? fmtMs(m.ms_per_image) : DASH)],
];

function cell(method, fn) {
  if (!method) return h('td', { class: 'num dash' }, DASH);
  const v = fn(method);
  return h('td', { class: 'num' + (v === DASH ? ' dash' : '') }, v ?? DASH);
}

function notes(data) {
  const out = [];
  const c = data.classical, m = data.ml;
  if (!c) out.push(['neutral', 'Classical has not been evaluated yet', 'Run scripts/evaluate.py on the labelled test photos to fill in this column.']);
  else if (c.rows_detected_rate != null && c.rows_detected_rate < 1) {
    const found = c.n_evaluated, total = c.n_images;
    out.push(['warn', 'Classical found crop rows in ' + found + ' of ' + total + ' photos',
      found === 0
        ? 'Photos without detectable rows are left out rather than counted as correct, so there are no classical scores yet. The method is being tuned.'
        : 'Its scores cover only those ' + found + ' photos. Photos without detectable rows are left out rather than counted as correct.']);
  }
  if (!m) out.push(['neutral', 'ML results arrive with the trained model', 'Once the model is connected and evaluated on the same photos, its scores appear here.']);
  return out;
}

function TrainingReport(report) {
  if (!report) return null;
  const rows = Object.entries(report).filter(([, v]) => typeof v === 'number' || typeof v === 'string').slice(0, 12);
  if (!rows.length) return null;
  return h('section', { class: 'panel' },
    h('h2', { class: 'panel-title' }, 'ML training report'),
    h('p', { class: 'note' }, 'As reported by the ML team, measured during training. Not the same test run as the table.'),
    h('dl', { class: 'kv' }, rows.map(([k, v]) => [h('dt', {}, k.replace(/_/g, ' ')), h('dd', {}, typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(3) : String(v)) : v)])));
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

  const c = data.classical, m = data.ml;
  const dataset = (c && c.dataset) || (m && m.dataset) || 'Labelled test photos';
  const notMeasured = h('td', { class: 'num dash' }, 'Not evaluated yet');

  root.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'Evaluation'), h('p', {}, dataset)),
    h('div', { class: 'eval-grid' },
      h('section', { class: 'panel' },
        h('div', { class: 'table-wrap' },
          h('table', { class: 'eval-table' },
            h('thead', {}, h('tr', {}, h('th', {}, 'Measure'), h('th', { class: 'num' }, 'Classical'), h('th', { class: 'num' }, 'ML segmentation'))),
            h('tbody', {}, ROWS.map(([label, fn], i) => h('tr', {},
              h('th', { scope: 'row' }, label),
              !c && i === 0 ? notMeasured.cloneNode(true) : cell(c, fn),
              !m && i === 0 ? notMeasured.cloneNode(true) : cell(m, fn)))))),
        h('p', { class: 'note' }, 'IoU (intersection over union) compares the pixels a method labels as crop or weed with hand-labelled ones: 1.00 is a perfect match. Precision is the share of predicted weed pixels that really are weeds; recall is the share of real weed pixels that were found. Photos are scored at the same working width the app uses.')),
      h('div', { class: 'eval-side' },
        notes(data).map(([tone, title, text]) => h('div', { class: 'callout callout-' + tone }, h('h2', {}, title), h('p', {}, text))),
        TrainingReport(data.ml_training_report))));
  return () => ctrl.abort();
}
