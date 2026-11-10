// Compare: the same request with mode=compare, shown as two columns plus a
// table of headline numbers. If one method has no result, its column says why.
import { h } from '../../utils/dom.js';
import { analysisApi } from '../../services/endpoints.js';
import { isAbort } from '../../services/api.js';
import { EmptyState, ErrorState, Loader } from '../../components/states.js';
import { toast } from '../../components/toast.js';
import { fmtMs, fmtPct, fmtPctWhole, fmtMoney, methodLabel, DASH } from '../../utils/formatters.js';
import { AnalysisForm } from '../analyze/analysis-form.js';
import { DemoTag, Downloads, PressureTag, ScanMeta, StatusPanel, StatusTag } from '../analyze/scan-results.js';
import { LayerViewer } from '../analyze/layer-viewer.js';

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
    h('header', {}, h('h2', {}, methodLabel(result.method)),
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
          scan.results.map((r) => h('th', {}, methodLabel(r.method))))),
        h('tbody', {}, ROWS.map(([label, fn]) => h('tr', {}, h('th', { scope: 'row' }, label),
          scan.results.map((r) => { const v = fn(r, scan); return h('td', { class: v === DASH ? 'dash' : null }, v); })))))),
    h('p', { class: 'note' }, 'Differences show where the methods disagree, not which one is right. Accuracy on labelled photos is on the Evaluation page.'));
}

export function CompareView(scan) {
  return h('div', { class: 'compare-view' },
    ScanMeta(scan, null),
    h('div', { class: 'compare-cols' }, scan.results.map((r) => MethodColumn(scan, r))),
    SideBySide(scan));
}

export function mount(root) {
  const ctrl = new AbortController();
  const out = h('section', { class: 'compare-out', 'aria-live': 'polite' },
    EmptyState('Nothing to compare yet', 'Choose a photo and both methods run on it. Their maps and numbers appear here side by side.'));

  const form = AnalysisForm({
    fixedMode: 'compare',
    title: 'Compare on a photo',
    submitLabel: 'Run both methods',
    onSubmit: async (fd) => {
      out.replaceChildren(Loader('Running classical and ML on the photo…'));
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
      h('p', {}, 'Classical finds crop rows by colour and geometry. ML segmentation labels every pixel with a trained model.')),
    h('div', { class: 'compare-layout' }, h('aside', { class: 'workspace-side' }, form), out));
  return () => ctrl.abort();
}
