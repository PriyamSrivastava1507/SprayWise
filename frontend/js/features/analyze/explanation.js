// "What this means": the result's numbers walked through in plain sentences.
// Every figure comes from the API response. The only arithmetic here is the
// share of weed area inside the sprayed zones, summed from result.grid
// (all zones are the same size, so their weed shares can be added).
import { h } from '../../utils/dom.js';
import { whenHealth } from '../../components/health.js';
import { toast } from '../../components/toast.js';
import { densest } from '../../utils/calculations.js';
import { fmtFixed, fmtMoney, fmtNumber, fmtPct, isDemo, resultLabel } from '../../utils/formatters.js';

/** Share (0..100) of all weed area that lies in the sprayed zones, or null if there are no weeds. */
function weedShareSprayed(result) {
  const spray = new Set(result.spray_cells.map(([r, c]) => r + ',' + c));
  let all = 0, inside = 0;
  result.grid.forEach((line, r) => line.forEach((v, c) => {
    all += v;
    if (spray.has(r + ',' + c)) inside += v;
  }));
  return all > 0 ? (inside / all) * 100 : null;
}

function pressureSentence(result, t) {
  if (!result.pressure) return null;
  if (!t) return 'Weed pressure is ' + result.pressure + '.';
  const range = { Low: 'below ' + fmtNumber(t.low_max, 1) + '%',
    Medium: 'between ' + fmtNumber(t.low_max, 1) + '% and ' + fmtNumber(t.high_min, 1) + '%',
    High: fmtNumber(t.high_min, 1) + '% or more' }[result.pressure];
  return 'That puts weed pressure at ' + result.pressure + (range ? ' (weed cover ' + range + ').' : '.');
}

/** The paragraphs, as plain strings (also used for "Copy text"). */
function paragraphs(scan, result, thresholds) {
  const p = scan.params;
  const s = result.savings;
  const total = p.grid_rows * p.grid_cols;
  const n = result.spray_cells.length;
  const limit = Math.round(p.cell_threshold * 100);
  const soil = result.vegetation_pct == null ? null : Math.max(0, 100 - result.vegetation_pct);
  const top = densest(result.grid);
  const share = weedShareSprayed(result);
  const out = [];

  out.push([
    resultLabel(result) + ' found weeds on ' + fmtPct(result.weed_pct) + ' of the photo and crop on ' +
      fmtPct(result.crop_pct) + '; the remaining ' + fmtPct(soil) + ' is bare soil.',
    pressureSentence(result, thresholds),
  ].filter(Boolean).join(' '));

  let zones = 'The photo was split into ' + p.grid_rows + ' × ' + p.grid_cols + ' = ' + total +
    ' zones, and a zone is sprayed when weeds cover more than ' + limit + '% of it. ';
  if (n === 0) zones += 'No zone passes that line, so nothing needs spraying.';
  else if (n === total) zones += 'Every zone passes it, so the whole photo would be sprayed.';
  else zones += n + ' of the ' + total + ' zones pass it.';
  if (top.value > 0) {
    zones += ' The weediest zone is row ' + (top.row + 1) + ', column ' + (top.col + 1) + ', at ' +
      Math.round(top.value * 100) + '% weeds.';
  }
  out.push(zones);

  if (share != null && n > 0 && n < total) {
    const missed = 100 - share;
    let cover = 'Together the sprayed zones hold ' + Math.round(share) + '% of all the weed area in the photo';
    cover += missed >= 0.5
      ? ', so about ' + Math.round(missed) + '% of the weeds sit in zones that would be skipped.'
      : ', so practically no weeds are left unsprayed.';
    if (missed >= 20) cover += ' To catch more of them, lower the spray threshold under Adjust and recalculate.';
    out.push(cover);
  }

  if (n < total) {
    out.push('Spraying the whole ' + fmtNumber(p.area_ha) + ' ha at ' + fmtNumber(p.dose_l_per_ha) + ' L/ha would use ' +
      fmtFixed(s.blanket_litres) + ' L of herbicide and cost ' + fmtMoney(s.blanket_cost) + '. Spraying only the ' +
      (n === 0 ? 'zones that need it uses nothing' : 'marked zones uses ' + fmtFixed(s.spot_litres) + ' L and costs ' + fmtMoney(s.spot_cost)) +
      ', a saving of ' + fmtFixed(s.saved_litres) + ' L and ' + fmtMoney(s.saved_cost) +
      ' (' + Math.round(s.saved_pct) + '% less).');
  } else {
    out.push('Spraying all ' + fmtNumber(p.area_ha) + ' ha at ' + fmtNumber(p.dose_l_per_ha) + ' L/ha uses ' +
      fmtFixed(s.blanket_litres) + ' L and costs ' + fmtMoney(s.blanket_cost) + '; spot spraying saves nothing on this photo.');
  }

  let caveat = 'These figures assume the photo is typical of the whole field and that herbicide use grows with the sprayed area; nozzle overlap and turning at the field edges are not counted.';
  if (isDemo(result)) caveat += ' This ML result comes from a demo model, not a trained one, so treat the numbers as an example only.';
  out.push(caveat);
  return out;
}

let boxes = 0;

/**
 * A "What this means" box. `build(health)` returns the paragraphs as strings;
 * it runs once at once and again when /health (pressure limits) is known.
 */
export function ExplainBox(title, build) {
  const id = 'explain-title-' + ++boxes;
  const body = h('div', { class: 'explain-body' });
  let text = [];
  const render = (health) => {
    text = build(health);
    body.replaceChildren(...text.map((t) => h('p', {}, t)));
  };
  render(null);
  whenHealth().then(render);

  const copy = h('button', {
    type: 'button', class: 'link-btn',
    onclick: async () => {
      try {
        await navigator.clipboard.writeText(text.join('\n\n'));
        toast('Explanation copied.');
      } catch {
        toast('Copying is blocked here. Select the text and copy it instead.', { tone: 'error' });
      }
    },
  }, 'Copy text');

  return h('section', { class: 'explain', 'aria-labelledby': id },
    h('div', { class: 'explain-head' }, h('h3', { id }, title), copy),
    body);
}

export const Explanation = (scan, result) =>
  ExplainBox('What this means', (health) => paragraphs(scan, result, health && health.pressure_thresholds));
