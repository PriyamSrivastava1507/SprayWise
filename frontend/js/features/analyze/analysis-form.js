// The "New scan" form. Input names are the backend's parameter names, so the
// FormData is the request body (only the threshold is converted from % to 0..1).
// Client checks mirror the server's ranges; the server stays the authority.
import { CONFIG } from '../../config.js';
import { h, s as svg, nextId } from '../../utils/dom.js';
import { fieldsApi } from '../../services/endpoints.js';
import { currencySymbol } from '../../utils/formatters.js';

const TYPES = ['image/jpeg', 'image/png'];
const STORE_KEY = 'spraywise.form.v1';
const MODES = [['classical', 'Classical'], ['ml', 'ML'], ['compare', 'Both']];

function remembered() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch { return {}; }
}
function remember(values) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(values)); } catch { /* private mode */ }
}

function prettySize(bytes) {
  return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.round(bytes / 1024) + ' KB';
}

/**
 * @param {{ fixedMode?: string, title?: string, submitLabel?: string,
 *           onSubmit: (fd: FormData) => Promise<void> }} options
 * @returns {HTMLFormElement & { submitWithMode: (mode: string) => void }}
 */
export function AnalysisForm({ fixedMode = null, title = 'New scan', submitLabel = 'Analyze photo', onSubmit }) {
  const saved = remembered();
  const ids = { file: nextId('file'), field: nextId('field'), list: nextId('fields'), area: nextId('area'),
    dose: nextId('dose'), price: nextId('price'), rows: nextId('rows'), cols: nextId('cols'), thr: nextId('thr') };

  // ---- photo picker -------------------------------------------------------
  const fileInput = h('input', { id: ids.file, type: 'file', name: 'file', accept: TYPES.join(','), class: 'visually-hidden' });
  const pickerBody = h('div', { class: 'picker-body' });
  const picker = h('div', { class: 'picker' }, fileInput, pickerBody);
  let previewUrl = null;

  function drawPicker() {
    const f = fileInput.files[0];
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
    if (!f) {
      picker.classList.remove('has-file');
      pickerBody.replaceChildren(
        svg('svg', { class: 'picker-icon', viewBox: '0 0 24 24', 'aria-hidden': 'true' }),
        h('div', {},
          h('b', {}, 'Drop a field photo here'),
          h('small', {}, 'JPG or PNG, up to ' + CONFIG.MAX_UPLOAD_MB + ' MB. Shoot straight down over the rows.')),
        h('label', { for: ids.file, class: 'btn btn-quiet' }, 'Choose photo'));
      pickerBody.querySelector('svg').innerHTML =
        '<path d="M4 17l4.5-5 3.5 4 2.5-3L20 17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="15.5" cy="8.5" r="1.5" fill="currentColor"/>';
      return;
    }
    previewUrl = URL.createObjectURL(f);
    const dims = h('small', {}, prettySize(f.size));
    const img = h('img', { src: previewUrl, alt: '' });
    img.onload = () => { dims.textContent = img.naturalWidth + ' × ' + img.naturalHeight + ' px, ' + prettySize(f.size); };
    picker.classList.add('has-file');
    pickerBody.replaceChildren(img,
      h('div', { class: 'picker-name' }, h('b', { title: f.name }, f.name), dims),
      h('label', { for: ids.file, class: 'link-btn' }, 'Replace'));
  }
  fileInput.addEventListener('change', () => { drawPicker(); clearError('file'); });
  picker.addEventListener('dragover', (e) => { e.preventDefault(); picker.classList.add('over'); });
  picker.addEventListener('dragleave', () => picker.classList.remove('over'));
  picker.addEventListener('drop', (e) => {
    e.preventDefault();
    picker.classList.remove('over');
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event('change'));
    }
  });
  drawPicker();

  // ---- method -------------------------------------------------------------
  const modeInput = h('input', { type: 'hidden', name: 'mode', value: fixedMode || saved.mode || 'classical' });
  const modeButtons = MODES.map(([value, label]) => h('button', {
    type: 'button', 'aria-pressed': String(modeInput.value === value),
    onclick: () => setMode(value),
  }, label));
  function setMode(value) {
    modeInput.value = value;
    modeButtons.forEach((b, i) => b.setAttribute('aria-pressed', String(MODES[i][0] === value)));
  }
  const methodBlock = fixedMode ? null : h('div', { class: 'form-row' },
    h('span', { class: 'label', id: 'method-label' }, 'Method'),
    h('div', { class: 'seg', role: 'group', 'aria-labelledby': 'method-label' }, modeButtons),
    h('p', { class: 'help' }, 'Both runs classical and ML on the same photo.'));

  // ---- numbers ------------------------------------------------------------
  const num = (id, name, value, unit, attrs = {}) => h('div', { class: 'unit-input' },
    h('input', { id, name, type: 'number', inputmode: 'decimal', step: 'any', value: value ?? '', ...attrs }),
    h('span', { 'aria-hidden': 'true' }, unit));

  const datalist = h('datalist', { id: ids.list });
  fieldsApi.list().then((rows) => datalist.replaceChildren(...rows.map((f) => h('option', { value: f.name }))))
    .catch(() => { /* suggestions are optional */ });

  const thresholdPct = saved.threshold_pct ?? 10;
  const errBox = h('div', { class: 'form-errors', role: 'alert' });
  const submit = h('button', { type: 'submit', class: 'btn btn-primary' }, submitLabel);

  const form = h('form', { class: 'setup', novalidate: true, 'aria-labelledby': 'setup-title' },
    h('h2', { id: 'setup-title' }, title),
    h('div', { class: 'form-row', 'data-for': 'file' }, picker, h('p', { class: 'field-error' })),
    modeInput,
    methodBlock,
    h('div', { class: 'form-row' },
      h('label', { for: ids.field }, 'Field ', h('span', { class: 'hint' }, 'optional')),
      h('input', { id: ids.field, name: 'field_name', type: 'text', maxlength: '120', list: ids.list,
        autocomplete: 'off', placeholder: 'e.g. North plot', value: saved.field_name || '' }),
      datalist,
      h('p', { class: 'help' }, 'Scans of the same field build its weed trend.')),
    h('div', { class: 'form-row numbers' },
      h('label', { for: ids.area }, 'Field area'),
      num(ids.area, 'area_ha', saved.area_ha, 'ha', { min: '0', required: true }),
      h('p', { class: 'field-error', 'data-for': 'area_ha' }),
      h('label', { for: ids.dose }, 'Herbicide dose'),
      num(ids.dose, 'dose_l_per_ha', saved.dose_l_per_ha, 'L/ha', { min: '0', required: true }),
      h('p', { class: 'field-error', 'data-for': 'dose_l_per_ha' }),
      h('label', { for: ids.price }, 'Herbicide price'),
      num(ids.price, 'price_per_l', saved.price_per_l, currencySymbol() + ' per L', { min: '0', required: true }),
      h('p', { class: 'field-error', 'data-for': 'price_per_l' })),
    h('details', { open: saved.advanced_open || null },
      h('summary', {}, 'Zones and spray threshold'),
      h('div', { class: 'grid3' },
        h('div', {}, h('label', { for: ids.rows }, 'Rows'), num(ids.rows, 'grid_rows', saved.grid_rows ?? 8, '', { min: '2', max: '32', step: '1' })),
        h('div', {}, h('label', { for: ids.cols }, 'Columns'), num(ids.cols, 'grid_cols', saved.grid_cols ?? 8, '', { min: '2', max: '32', step: '1' })),
        h('div', {}, h('label', { for: ids.thr }, 'Spray above'), num(ids.thr, 'threshold_pct', thresholdPct, '% weeds', { min: '1', max: '99', step: '1' }))),
      h('p', { class: 'field-error', 'data-for': 'grid' }),
      h('p', { class: 'help' }, 'The photo is split into rows × columns zones. A zone is sprayed when weeds cover more than this share of it.')),
    errBox,
    submit);

  form.querySelectorAll('input').forEach((input) => input.addEventListener('input', () => clearError(input.name)));

  // ---- validation ---------------------------------------------------------
  function setError(key, message) {
    const slot = key === 'file' ? form.querySelector('[data-for=file] .field-error') : form.querySelector(`.field-error[data-for="${key}"]`);
    if (slot) slot.textContent = message;
    const input = key === 'file' ? null : form.elements[key];
    if (input) input.setAttribute('aria-invalid', 'true');
    if (key === 'file') picker.classList.add('invalid');
  }
  function clearError(key) {
    const keys = key === 'grid_rows' || key === 'grid_cols' || key === 'threshold_pct' ? ['grid'] : [key];
    keys.forEach((k) => {
      const slot = k === 'file' ? form.querySelector('[data-for=file] .field-error') : form.querySelector(`.field-error[data-for="${k}"]`);
      if (slot) slot.textContent = '';
    });
    if (form.elements[key]) form.elements[key].removeAttribute('aria-invalid');
    if (key === 'file') picker.classList.remove('invalid');
  }

  function validate() {
    const el = form.elements;
    const n = (k) => (el[k].value === '' ? NaN : Number(el[k].value));
    const errors = {};
    const f = fileInput.files[0];
    if (!f) errors.file = 'Choose a photo to analyze.';
    else if (!TYPES.includes(f.type)) errors.file = 'Only JPG and PNG photos can be analyzed.';
    else if (f.size > CONFIG.MAX_UPLOAD_MB * 1048576) errors.file = 'This photo is ' + prettySize(f.size) + '. The limit is ' + CONFIG.MAX_UPLOAD_MB + ' MB.';
    if (!(n('area_ha') > 0)) errors.area_ha = 'Enter the field area in hectares (more than 0).';
    if (!(n('dose_l_per_ha') >= 0)) errors.dose_l_per_ha = 'Enter the herbicide dose (0 or more).';
    if (!(n('price_per_l') >= 0)) errors.price_per_l = 'Enter the price per litre (0 or more).';
    const r = n('grid_rows'), c = n('grid_cols'), t = n('threshold_pct');
    if (![r, c].every((v) => Number.isInteger(v) && v >= 2 && v <= 32)) errors.grid = 'Rows and columns must be whole numbers from 2 to 32.';
    else if (!(t > 0 && t < 100)) errors.grid = 'The spray threshold must be between 1 and 99%.';
    return errors;
  }

  let busy = false;
  async function handleSubmit(ev) {
    if (ev) ev.preventDefault();
    if (busy) return;
    errBox.textContent = '';
    const errors = validate();
    for (const key of Object.keys(errors)) setError(key, errors[key]);
    if (Object.keys(errors).length) {
      const first = form.querySelector('[aria-invalid=true]') || (errors.file ? picker.querySelector('label') : null);
      if (first) first.focus();
      return;
    }

    const fd = new FormData(form);
    fd.set('cell_threshold', String(Number(fd.get('threshold_pct')) / 100));
    fd.delete('threshold_pct');
    for (const [k, v] of [...fd.entries()]) if (v === '') fd.delete(k);
    remember({
      mode: fixedMode ? saved.mode : modeInput.value,
      field_name: form.elements.field_name.value.trim(),
      area_ha: form.elements.area_ha.value, dose_l_per_ha: form.elements.dose_l_per_ha.value,
      price_per_l: form.elements.price_per_l.value, grid_rows: form.elements.grid_rows.value,
      grid_cols: form.elements.grid_cols.value, threshold_pct: form.elements.threshold_pct.value,
      advanced_open: form.querySelector('details').open,
    });

    busy = true;
    submit.disabled = true;
    submit.textContent = 'Analyzing…';
    try {
      await onSubmit(fd);
    } finally {
      busy = false;
      submit.disabled = false;
      submit.textContent = submitLabel;
    }
  }
  form.addEventListener('submit', handleSubmit);

  /** Run again with another method (used by "Run ML on this photo"). */
  form.submitWithMode = (mode) => { setMode(mode); handleSubmit(); };
  /** Show a server-side validation message under the form. */
  form.showServerError = (message) => { errBox.textContent = message; };
  return form;
}
