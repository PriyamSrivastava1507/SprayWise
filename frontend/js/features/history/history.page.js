// History: filter by field, a weed trend for the chosen field, and a paged
// table of scans with View, CSV, PDF and Delete.
import { CONFIG } from '../../config.js';
import { h } from '../../utils/dom.js';
import { isAbort } from '../../services/api.js';
import { fieldsApi, scansApi } from '../../services/endpoints.js';
import { EmptyState, ErrorState, Loader } from '../../components/states.js';
import { whenHealth } from '../../components/health.js';
import { toast } from '../../components/toast.js';
import { fmtDate, fmtPct, fmtPctWhole, modeLabel, resultLabel, DASH } from '../../utils/formatters.js';
import { primaryResult } from '../../utils/calculations.js';
import { PressureTag } from '../analyze/scan-results.js';
import { TrendChart } from './trend-chart.js';

const STATE_KEY = 'spraywise.history.v1';

export function mount(root) {
  const ctrl = new AbortController();
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem(STATE_KEY)) || {}; } catch { /* ignore */ }
  // Trend source: 'classical' or 'ml:<model key>' ('ml' = the default model).
  const state = { fieldId: saved.fieldId || '', method: saved.method || 'ml', offset: 0 };
  const persist = () => { try { sessionStorage.setItem(STATE_KEY, JSON.stringify(state)); } catch { /* ignore */ } };

  const count = h('p', {});
  const fieldSel = h('select', { id: 'h-field', onchange: (e) => { state.fieldId = e.target.value; state.offset = 0; persist(); loadTrend(); loadList(); } },
    h('option', { value: '' }, 'All fields'));
  const methodSel = h('select', { id: 'h-method', onchange: (e) => { state.method = e.target.value; persist(); loadTrend(); } },
    h('option', { value: 'ml' }, 'ML segmentation'), h('option', { value: 'classical' }, 'Classical'));
  methodSel.value = state.method;
  const sourceLabel = () => (methodSel.selectedOptions[0] || {}).textContent || 'ML segmentation';
  whenHealth().then((health) => {
    const models = (health && health.models) || [];
    if (models.length < 2) return; // one model: keep the simple choice
    methodSel.replaceChildren(
      ...models.map((m) => h('option', { value: 'ml:' + m.key }, m.label)),
      h('option', { value: 'classical' }, 'Classical'));
    const def = models.find((m) => m.default) || models[0];
    const wanted = state.method === 'ml' ? 'ml:' + def.key : state.method;
    methodSel.value = [...methodSel.options].some((o) => o.value === wanted) ? wanted : 'ml:' + def.key;
    if (state.method !== methodSel.value) { state.method = methodSel.value; persist(); loadTrend(); }
  });
  const methodWrap = h('div', {}, h('label', { for: 'h-method' }, 'Trend method'), methodSel);
  const trend = h('div', {});
  const list = h('div', {});

  root.replaceChildren(
    h('div', { class: 'page-head' }, h('h1', {}, 'Scan history'), count),
    h('div', { class: 'toolbar' }, h('div', {}, h('label', { for: 'h-field' }, 'Field'), fieldSel), methodWrap),
    trend, list);

  fieldsApi.list(ctrl.signal).then((fields) => {
    fieldSel.append(...fields.map((f) => h('option', { value: String(f.id) }, f.name)));
    if (fields.some((f) => String(f.id) === state.fieldId)) fieldSel.value = state.fieldId;
    else state.fieldId = '';
    loadTrend();
    loadList();
  }).catch((err) => { if (!isAbort(err)) { loadTrend(); loadList(); } });

  async function loadTrend() {
    methodWrap.hidden = !state.fieldId;
    if (!state.fieldId) {
      trend.replaceChildren(h('p', { class: 'hint-line' }, 'Choose a field to see how its weed cover changes over time.'));
      return;
    }
    trend.replaceChildren(Loader('Loading trend…'));
    try {
      const [method, model] = state.method.split(':');
      const [data, health] = await Promise.all([fieldsApi.trend(state.fieldId, method, model, ctrl.signal), whenHealth()]);
      const name = fieldSel.selectedOptions[0].textContent;
      if (data.points.length < 2) {
        trend.replaceChildren(EmptyState('Not enough scans for a trend yet',
          name + ' has ' + data.points.length + ' successful ' + (data.model_label || sourceLabel()) +
          ' scan' + (data.points.length === 1 ? '' : 's') + '. A trend needs at least two.'));
        return;
      }
      trend.replaceChildren(h('section', { class: 'panel' },
        h('div', { class: 'trend-head' }, h('h2', {}, 'Weed cover over time'),
          h('p', {}, name + ', ' + (data.model_label || sourceLabel()) + ', ' + data.points.length + ' scans')),
        TrendChart(data.points, health && health.pressure_thresholds)));
    } catch (err) {
      if (!isAbort(err)) trend.replaceChildren(ErrorState(err, loadTrend));
    }
  }

  async function loadList() {
    list.replaceChildren(Loader('Loading scans…'));
    try {
      const page = await scansApi.list({ fieldId: state.fieldId, limit: CONFIG.PAGE_SIZE, offset: state.offset }, ctrl.signal);
      if (page.total > 0 && page.items.length === 0 && state.offset > 0) {
        state.offset = Math.max(0, state.offset - CONFIG.PAGE_SIZE); // the last row of a page was deleted
        return loadList();
      }
      count.textContent = page.total + (page.total === 1 ? ' scan' : ' scans');
      if (!page.total) {
        list.replaceChildren(EmptyState(state.fieldId ? 'No scans for this field yet' : 'No scans yet',
          'Analyze a photo and it will appear here.', h('a', { class: 'btn btn-quiet', href: '#/analyze' }, 'Analyze a photo')));
        return;
      }
      list.replaceChildren(Table(page));
    } catch (err) {
      if (!isAbort(err)) list.replaceChildren(ErrorState(err, loadList));
    }
  }

  function Row(scan) {
    const r = primaryResult(scan);
    const actions = h('div', { class: 'row-actions' },
      h('a', { href: '#/scans/' + scan.id }, 'View'),
      r ? h('a', { href: scansApi.exportUrl(scan.id, 'csv', r) }, 'CSV') : null,
      r ? h('a', { href: scansApi.exportUrl(scan.id, 'pdf', r) }, 'PDF') : null,
      h('button', { type: 'button', class: 'link-btn danger', onclick: () => askDelete() }, 'Delete'));

    function askDelete() {
      actions.replaceChildren(
        h('span', { class: 'confirm-text' }, 'Delete scan ' + scan.id + '?'),
        h('button', { type: 'button', class: 'link-btn danger', onclick: doDelete }, 'Delete'),
        h('button', { type: 'button', class: 'link-btn', onclick: () => row.replaceWith(Row(scan)) }, 'Keep'));
      actions.querySelector('button').focus();
    }
    async function doDelete() {
      actions.replaceChildren(h('span', { class: 'confirm-text' }, 'Deleting…'));
      try {
        await scansApi.remove(scan.id);
        toast('Scan ' + scan.id + ' deleted.');
        loadList();
        if (state.fieldId) loadTrend();
      } catch (err) {
        toast(err.message, { tone: 'error' });
        row.replaceWith(Row(scan));
      }
    }

    const others = r ? scan.results.filter((x) => x !== r) : [];
    const method = r
      ? [resultLabel(r), others.length ? h('span', { class: 'more', title: 'Also: ' + others.map(resultLabel).join(', ') }, ' +' + others.length) : null]
      : modeLabel(scan.mode);
    const row = h('tr', {},
      h('td', {}, h('a', { href: '#/scans/' + scan.id, class: 'row-link' }, fmtDate(scan.created_at))),
      h('td', {}, scan.field ? scan.field.name : h('span', { class: 'dash' }, 'No field')),
      h('td', {}, method),
      h('td', { class: 'num' }, r ? fmtPct(r.weed_pct) : DASH),
      h('td', {}, r ? PressureTag(r.pressure) : h('span', { class: 'tag tag-muted' }, 'No result')),
      h('td', { class: 'num' }, r ? fmtPctWhole(r.savings.saved_pct) : DASH),
      h('td', {}, actions));
    return row;
  }

  function Table(page) {
    const from = page.offset + 1, to = page.offset + page.items.length;
    const go = (delta) => { state.offset = Math.max(0, state.offset + delta); loadList(); };
    return h('section', { class: 'panel history-table' },
      h('div', { class: 'table-wrap' },
        h('table', {},
          h('thead', {}, h('tr', {},
            h('th', {}, 'Date'), h('th', {}, 'Field'), h('th', {}, 'Method'), h('th', { class: 'num' }, 'Weed cover'),
            h('th', {}, 'Pressure'), h('th', { class: 'num' }, 'Herbicide saved'), h('th', {}, h('span', { class: 'visually-hidden' }, 'Actions')))),
          h('tbody', {}, page.items.map(Row)))),
      h('div', { class: 'pager' },
        h('span', {}, 'Showing ' + from + '–' + to + ' of ' + page.total),
        h('span', { class: 'pager-buttons' },
          h('button', { type: 'button', class: 'btn btn-quiet', disabled: page.offset === 0, onclick: () => go(-CONFIG.PAGE_SIZE) }, 'Previous'),
          h('button', { type: 'button', class: 'btn btn-quiet', disabled: to >= page.total, onclick: () => go(CONFIG.PAGE_SIZE) }, 'Next'))));
  }

  return () => ctrl.abort();
}
