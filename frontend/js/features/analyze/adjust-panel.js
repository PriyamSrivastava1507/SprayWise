// "Adjust and recalculate": change the spray threshold, the zone grid or the
// area, dose and price of a stored scan and see the result update while you
// move the controls. Previews are calculated by the server from the saved
// masks (nothing is written); "Save to scan" makes them permanent.
import { h, nextId } from '../../utils/dom.js';
import { isAbort } from '../../services/api.js';
import { scansApi } from '../../services/endpoints.js';
import { toast } from '../../components/toast.js';
import { currencySymbol } from '../../utils/formatters.js';

const DEBOUNCE_MS = 180;

const settingsOf = (scan) => ({ ...scan.params });
const same = (a, b) => Object.keys(a).every((k) => Number(a[k]) === Number(b[k]));

/**
 * @param {object} scan  the saved scan
 * @param {{ onPreview: (scan, dirty: boolean) => void, onSaved: (scan) => void }} handlers
 */
export function AdjustPanel(scan, { onPreview, onSaved }) {
  let saved = scan;
  let ctrl = null, timer = null;
  const id = (p) => nextId(p);

  // ---- controls -----------------------------------------------------------
  const ids = { thr: id('adj-thr'), rows: id('adj-rows'), cols: id('adj-cols'), area: id('adj-area'), dose: id('adj-dose'), price: id('adj-price') };
  const thr = h('input', { id: ids.thr, type: 'range', min: '1', max: '60', step: '1' });
  const thrOut = h('output', { for: ids.thr, class: 'adj-value' });
  const rows = h('input', { id: ids.rows, type: 'range', min: '2', max: '32', step: '1' });
  const rowsOut = h('output', { for: ids.rows, class: 'adj-value' });
  const cols = h('input', { id: ids.cols, type: 'range', min: '2', max: '32', step: '1' });
  const colsOut = h('output', { for: ids.cols, class: 'adj-value' });
  const numberInput = (iid, unit) => {
    const input = h('input', { id: iid, type: 'number', inputmode: 'decimal', step: 'any', min: '0' });
    return [input, h('div', { class: 'unit-input' }, input, h('span', { 'aria-hidden': 'true' }, unit))];
  };
  const [area, areaBox] = numberInput(ids.area, 'ha');
  const [dose, doseBox] = numberInput(ids.dose, 'L/ha');
  const [price, priceBox] = numberInput(ids.price, currencySymbol() + '/L');

  const status = h('p', { class: 'adj-status', 'aria-live': 'polite' });
  const saveBtn = h('button', { type: 'button', class: 'btn btn-small', onclick: save }, 'Save to scan');
  const resetBtn = h('button', { type: 'button', class: 'link-btn', onclick: reset }, 'Reset');

  const panel = h('section', { class: 'adjust', 'aria-labelledby': ids.thr + '-title' },
    h('div', { class: 'adjust-head' },
      h('h3', { id: ids.thr + '-title' }, 'Adjust and recalculate'),
      h('p', {}, 'Try other settings on this photo. The map, zones and savings update as you move the controls.')),
    h('div', { class: 'adjust-grid' },
      h('div', { class: 'adj-control' }, h('label', { for: ids.thr }, 'Spray zones above'), h('div', { class: 'adj-range' }, thr, thrOut)),
      h('div', { class: 'adj-control' }, h('label', { for: ids.rows }, 'Zone rows'), h('div', { class: 'adj-range' }, rows, rowsOut)),
      h('div', { class: 'adj-control' }, h('label', { for: ids.cols }, 'Zone columns'), h('div', { class: 'adj-range' }, cols, colsOut)),
      h('div', { class: 'adj-control' }, h('label', { for: ids.area }, 'Field area'), areaBox),
      h('div', { class: 'adj-control' }, h('label', { for: ids.dose }, 'Dose'), doseBox),
      h('div', { class: 'adj-control' }, h('label', { for: ids.price }, 'Price'), priceBox)),
    h('div', { class: 'adjust-foot' }, status, h('div', { class: 'adjust-actions' }, resetBtn, saveBtn)));

  function fill(s) {
    thr.value = String(Math.round(s.cell_threshold * 100));
    rows.value = String(s.grid_rows);
    cols.value = String(s.grid_cols);
    area.value = String(s.area_ha);
    dose.value = String(s.dose_l_per_ha);
    price.value = String(s.price_per_l);
    outputs();
  }
  function outputs() {
    thrOut.textContent = thr.value + '% weeds';
    rowsOut.textContent = rows.value;
    colsOut.textContent = cols.value;
  }
  function read() {
    return {
      area_ha: Number(area.value), dose_l_per_ha: Number(dose.value), price_per_l: Number(price.value),
      grid_rows: Number(rows.value), grid_cols: Number(cols.value), cell_threshold: Number(thr.value) / 100,
    };
  }
  function problem(s) {
    if (area.value === '' || !(s.area_ha > 0)) return 'Field area must be more than 0.';
    if (dose.value === '' || !(s.dose_l_per_ha >= 0)) return 'Dose must be 0 or more.';
    if (price.value === '' || !(s.price_per_l >= 0)) return 'Price must be 0 or more.';
    return null;
  }
  function setState(kind, text) {
    status.textContent = text;
    status.dataset.state = kind;
    const dirty = kind === 'dirty' || kind === 'busy' || kind === 'error';
    saveBtn.disabled = kind !== 'dirty';
    resetBtn.hidden = !dirty;
  }

  // ---- preview / save / reset ----------------------------------------------
  function schedule() {
    outputs();
    clearTimeout(timer);
    const s = read();
    const bad = problem(s);
    for (const input of [area, dose, price]) input.removeAttribute('aria-invalid');
    if (bad) {
      ({ 'Field area must be more than 0.': area, 'Dose must be 0 or more.': dose, 'Price must be 0 or more.': price })[bad]
        .setAttribute('aria-invalid', 'true');
      setState('error', bad);
      return;
    }
    if (same(s, settingsOf(saved))) {
      if (ctrl) ctrl.abort();
      setState('clean', 'Showing the saved settings.');
      onPreview(saved, false);
      return;
    }
    setState('busy', 'Recalculating…');
    timer = setTimeout(() => preview(s), DEBOUNCE_MS);
  }

  async function preview(s) {
    if (ctrl) ctrl.abort();
    ctrl = new AbortController();
    try {
      const next = await scansApi.recalculate(saved.id, s, false, ctrl.signal);
      setState('dirty', 'Preview. Save to keep these settings for this scan, its downloads and its trend.');
      onPreview(next, true);
    } catch (err) {
      if (!isAbort(err)) setState('error', err.message);
    }
  }

  async function save() {
    const s = read();
    saveBtn.disabled = true;
    setState('busy', 'Saving…');
    try {
      saved = await scansApi.recalculate(saved.id, s, true);
      setState('clean', 'Saved. Downloads and History now use these settings.');
      toast('Scan ' + saved.id + ' updated.');
      onSaved(saved);
    } catch (err) {
      setState('error', err.message);
      saveBtn.disabled = false;
    }
  }

  function reset() {
    if (ctrl) ctrl.abort();
    clearTimeout(timer);
    fill(saved.params);
    for (const input of [area, dose, price]) input.removeAttribute('aria-invalid');
    setState('clean', 'Showing the saved settings.');
    onPreview(saved, false);
  }

  for (const input of [thr, rows, cols, area, dose, price]) input.addEventListener('input', schedule);
  fill(saved.params);
  setState('clean', 'Showing the saved settings.');
  panel.dispose = () => { if (ctrl) ctrl.abort(); clearTimeout(timer); };
  return panel;
}

/** Only scans with a stored mask can be recalculated. */
export const canAdjust = (scan) => scan.results.some((r) => r.status === 'ok' && r.mask_url);
