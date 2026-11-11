// Compare: the same request with mode=compare, shown as two columns plus a
// table of headline numbers. If one method has no result, its column says why.
import { h } from '../../utils/dom.js';
import { analysisApi } from '../../services/endpoints.js';
import { isAbort } from '../../services/api.js';
import { EmptyState, ErrorState, Loader } from '../../components/states.js';
import { toast } from '../../components/toast.js';
import { fmtMs, fmtPct, fmtPctWhole, fmtMoney, resultLabel, variantOf, DASH } from '../../utils/formatters.js';
import { AnalysisForm } from '../analyze/analysis-form.js';
import { DemoTag, Downloads, PressureTag, ScanMeta, StatusPanel, StatusTag } from '../analyze/scan-results.js';
import { LayerViewer } from '../analyze/layer-viewer.js';
import { SwipeView } from './swipe-view.js';

const ROWS = [
  ['Result', (r) => (r.status === 'ok' ? 'Analyzed' : { rows_not_detected: 'Rows not detected', model_unavailable: 'Model offline', failed: 'Failed' }[r.status])],
  ['Weed cover', (r) => fmtPct(r.weed_pct)],
  ['Crop cover', (r) => fmtPct(r.crop_pct)],
  ['Weed pressure', (r) => r.pressure || DASH],
  ['Zones to spray', (r, s) => (r.spray_cells ? r.spray_cells.length + ' of ' + s.params.grid_rows * s.params.grid_cols : DASH)],
  ['Herbicide saved', (r) => fmtPctWhole(r.savings.saved_pct)],
  ['Money saved', (r) => fmtMoney(r.savings.saved_cost)],
  ['Processing time', (r) => fmtMs(r.processing_ms)],
];

function MethodColumn(scan, result) {
  return h('article', { class: 'method-card' },
    h('header', {}, h('h2', {}, resultLabel(result)),
      h('div', { class: 'tags' }, StatusTag(result), DemoTag(result), result.status === 'ok' ? PressureTag(result.pressure) : null)),
    result.status === 'ok' ? LayerViewer(scan, result) : StatusPanel(scan, result),
    result.status === 'ok' ? h('div', { class: 'method-foot' }, Downloads(scan, result)) : null);
}

export function SideBySide(scan) {
  return h('section', { class: 'panel side-table' },
    h('h2', {}, 'Side by side'),
    h('div', { class: 'table-wrap' },
      h('table', {},
        h('thead', {}, h('tr', {}, h('th', {}, h('span', { class: 'visually-hidden' }, 'Measure')),
          scan.results.map((r) => h('th', {}, resultLabel(r))))),
        h('tbody', {}, ROWS.map(([label, fn]) => h('tr', {}, h('th', { scope: 'row' }, label),
          scan.results.map((r) => { const v = fn(r, scan); return h('td', { class: v === DASH ? 'dash' : null }, v); })))))),
    h('p', { class: 'note' }, 'Differences show where the methods disagree, not which one is right. Accuracy on labelled photos is on the Evaluation page.'));
}

/**
 * Swipe between two results over the same photo. With more than two
 * successful results, two dropdowns choose the left and right sides.
 * Returns null when fewer than two results can be shown.
 */
export function SwipePanel(scan) {
  const ok = scan.results.filter((r) => r.status === 'ok' && r.mask_url);
  if (ok.length < 2) return null;
  let left = ok[0], right = ok[1];
  const body = h('div', {});
  const draw = () => body.replaceChildren(SwipeView(scan, left, right));

  let pickers = null;
  if (ok.length > 2) {
    const select = (id, text, current, set) => {
      const el = h('select', { id, onchange: (e) => { set(ok.find((r) => variantOf(r) === e.target.value)); draw(); } },
        ok.map((r) => h('option', { value: variantOf(r) }, resultLabel(r))));
      el.value = variantOf(current);
      return h('div', {}, h('label', { for: id }, text), el);
    };
    pickers = h('div', { class: 'swipe-pickers' },
      select('swipe-left', 'Left side', left, (r) => { left = r; }),
      select('swipe-right', 'Right side', right, (r) => { right = r; }));
  }
  draw();
  return h('div', { class: 'swipe-panel-body' }, pickers, body);
}

export function CompareView(scan) {
  const swipe = SwipePanel(scan);
  const body = h('div', {});
  let view = swipe ? 'swipe' : 'columns';

  const options = [['swipe', 'Swipe'], ['columns', 'Side by side']];
  const buttons = options.map(([value, text]) => h('button', {
    type: 'button', 'aria-pressed': String(view === value), disabled: value === 'swipe' && !swipe,
    onclick: () => { view = value; render(); },
  }, text));
  const switcher = h('div', { class: 'view-switch' },
    h('div', { class: 'seg seg-2', role: 'group', 'aria-label': 'Comparison view' }, buttons),
    swipe ? null : h('span', { class: 'note-inline' }, 'Swipe needs two successful results.'));

  const columns = h('div', { class: 'compare-cols cols-' + Math.min(scan.results.length, 3) },
    scan.results.map((r) => MethodColumn(scan, r)));
  function render() {
    buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(options[i][0] === view)));
    body.replaceChildren(view === 'swipe' ? swipe : columns);
  }
  render();

  return h('div', { class: 'compare-view' },
    h('div', { class: 'compare-top' }, ScanMeta(scan, null), switcher),
    body,
    SideBySide(scan));
}

export function mount(root) {
  const ctrl = new AbortController();
  const out = h('section', { class: 'compare-out', 'aria-live': 'polite' },
    EmptyState('Nothing to compare yet', 'Choose a photo and tick what to compare: classical, one or more ML models. Their maps and numbers appear here side by side.'));

  const form = AnalysisForm({
    chooser: true,
    title: 'Compare on a photo',
    submitLabel: 'Run comparison',
    onSubmit: async (fd) => {
      out.replaceChildren(Loader('Running the comparison on the photo…'));
      try {
        const scan = await analysisApi.analyze(fd, ctrl.signal);
        out.replaceChildren(CompareView(scan));
        toast('Scan ' + scan.id + ' saved to History.');
      } catch (err) {
        if (isAbort(err)) return;
        if (err.code === 'validation_error') form.showServerError(err.message);
        out.replaceChildren(ErrorState(err));
      }
    },
  });

  root.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'Compare methods'),
      h('p', {}, 'Classical finds crop rows by colour and geometry. Each ML model labels every pixel; models trained on different datasets can disagree.')),
    h('div', { class: 'compare-layout' }, h('aside', { class: 'workspace-side' }, form), out));
  return () => ctrl.abort();
}
