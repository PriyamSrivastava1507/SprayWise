// A model's training report from the ML team, shown as a summary, one metrics
// table (validation and test side by side) and the notes. Values that are
// null or missing say "not reported"; nothing is filled in or estimated.
// Unknown fields still appear, so a report in another shape is never hidden.
import { h } from '../../utils/dom.js';

const CLASSES = ['soil', 'crop', 'weed'];
const NOT_REPORTED = 'not reported';
const pretty = (key) => key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
function num(v) {
  if (v == null) return NOT_REPORTED;
  if (typeof v !== 'number') return String(v);
  if (Math.abs(v) >= 10) return String(v);
  // 0.995 would round to "1.00", which reads as perfect: show one more digit.
  let digits = 2;
  while (v < 1 && digits < 6 && Number(v.toFixed(digits)) === 1) digits += 1;
  return v.toFixed(digits);
}

/** "validation_metrics_at_best_epoch" -> "Validation (best epoch)", "test_metrics" -> "Test". */
function sectionName(key) {
  const k = key.toLowerCase();
  const base = k.includes('val') ? 'Validation' : k.includes('test') ? 'Test' : pretty(key.replace(/_?metrics_?/g, ' ').trim());
  return k.includes('best') ? base + ' (best epoch)' : base;
}

/** Per-class value from {soil: 0.9, ...} or [0.9, ...]. */
function perClass(values, cls, i) {
  if (values == null) return null;
  if (Array.isArray(values)) return values[i] ?? null;
  return typeof values === 'object' ? values[cls] ?? null : null;
}

function MetricsTable(report, classNames) {
  const sections = Object.entries(report).filter(([, v]) => v && typeof v === 'object' && !Array.isArray(v) && 'iou' in v);
  if (!sections.length) return null;
  const kinds = [['iou', 'IoU'], ['precision', 'precision'], ['recall', 'recall']];
  const rows = [];
  const missing = [];
  for (const [key, sec] of sections) {
    for (const [kind, label] of kinds) {
      if (sec[kind] === undefined) continue;
      const values = classNames.map((cls, i) => perClass(sec[kind], cls, i));
      const mean = kind === 'iou' ? sec.mean_crop_weed_iou ?? sec.mean_iou_crop_weed ?? null : undefined;
      if (values.every((v) => v == null) && mean == null) missing.push(sectionName(key).toLowerCase() + ' ' + label);
      else rows.push([sectionName(key) + ' ' + label, values, mean]);
    }
  }
  return h('div', {},
    rows.length ? h('div', { class: 'table-wrap' },
      h('table', { class: 'report-table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Measure'),
          classNames.map((c) => h('th', { class: 'num' }, pretty(c))),
          h('th', { class: 'num' }, 'Crop and weed mean'))),
        h('tbody', {}, rows.map(([label, values, mean]) => h('tr', {},
          h('th', { scope: 'row' }, label),
          values.map((v) => h('td', { class: 'num' + (v == null ? ' dash' : '') }, num(v))),
          h('td', { class: 'num' + (mean == null ? ' dash' : '') }, mean === undefined ? '' : num(mean)))))))
      : null,
    missing.length ? h('p', { class: 'note' }, 'Not reported: ' + missing.join(', ') + '.') : null);
}

function summary(report) {
  const t = report.training && typeof report.training === 'object' ? report.training : {};
  const classes = report.class_mapping && typeof report.class_mapping === 'object'
    ? Object.values(report.class_mapping).join(', ')
    : report.num_classes != null ? String(report.num_classes) : null;
  const epochs = [
    t.completed_epochs != null ? t.completed_epochs + ' completed' : null,
    t.configured_epochs != null && t.configured_epochs !== t.completed_epochs ? 'of ' + t.configured_epochs + ' planned' : null,
    t.best_epoch != null ? 'best at epoch ' + t.best_epoch : null,
    t.early_stopping ? 'stopped early' : null,
  ].filter(Boolean).join(', ');
  const losses = [
    t.best_epoch_training_loss != null ? 'training ' + num(t.best_epoch_training_loss) : null,
    t.best_epoch_validation_loss != null ? 'validation ' + num(t.best_epoch_validation_loss) : null,
  ].filter(Boolean).join(', ');

  const rows = [
    ['Trained on', report.dataset],
    ['Model', [report.model, report.backbone].filter(Boolean).join(', ')],
    ['Classes', classes],
    ['Epochs', epochs],
    ['Loss at best epoch', losses],
  ];
  // Anything else at the top level, or inside "training", that is a plain value.
  const known = new Set(['dataset', 'model', 'backbone', 'num_classes', 'class_mapping', 'training', 'notes']);
  for (const [k, v] of Object.entries(report)) {
    if (!known.has(k) && (typeof v !== 'object' || v === null)) rows.push([pretty(k), num(v)]);
  }
  const shown = new Set(['completed_epochs', 'configured_epochs', 'best_epoch', 'early_stopping', 'best_epoch_training_loss', 'best_epoch_validation_loss']);
  for (const [k, v] of Object.entries(t)) {
    if (!shown.has(k) && (typeof v !== 'object' || v === null)) rows.push([pretty(k), num(v)]);
  }
  return rows.filter(([, v]) => v !== null && v !== undefined && v !== '');
}

export function TrainingReport(label, report) {
  const classNames = report.class_mapping && typeof report.class_mapping === 'object'
    ? Object.values(report.class_mapping) : CLASSES;
  const notes = Array.isArray(report.notes) ? report.notes.filter((n) => typeof n === 'string') : [];
  return h('section', { class: 'panel report' },
    h('div', { class: 'report-head' },
      h('h3', {}, label),
      h('p', {}, 'Reported by the ML team, measured on their own validation and test photos during training.')),
    h('dl', { class: 'report-summary' }, summary(report).map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', {}, v)))),
    MetricsTable(report, classNames),
    notes.length ? h('ul', { class: 'report-notes' }, notes.map((n) => h('li', {}, n))) : null);
}
