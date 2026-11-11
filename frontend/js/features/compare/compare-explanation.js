// "What the comparison shows": the results of one scan compared in plain
// sentences. Every figure comes from the results; the only arithmetic is
// counting which zones each result marks for spraying (same grid for all).
import { fmtMoney, fmtNumber, fmtPct, isDemo, resultLabel } from '../../utils/formatters.js';
import { ExplainBox } from '../analyze/explanation.js';

const WHY_NOT = {
  rows_not_detected: 'it found no crop rows in this photo',
  model_unavailable: 'the model was offline',
  failed: 'it failed on this photo',
};

/** "A", "A and B", "A, B and C" */
function list(items) {
  if (items.length <= 1) return items.join('');
  return items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
}

const zoneSet = (r) => new Set(r.spray_cells.map(([row, col]) => row + ',' + col));

function paragraphs(scan) {
  const ok = scan.results.filter((r) => r.status === 'ok');
  const missing = scan.results.filter((r) => r.status !== 'ok');
  const out = [];

  let intro = 'This scan ran ' + list(scan.results.map(resultLabel)) + ' on the same photo.';
  for (const r of missing) {
    intro += ' ' + resultLabel(r) + ' has no result because ' + (WHY_NOT[r.status] || 'it did not finish') + ', so it is left out below.';
  }
  out.push(intro);

  if (ok.length < 2) {
    out.push('With fewer than two results there is nothing to compare. The result that did finish is explained on its own page.');
    return out;
  }

  // Weed cover and pressure
  const byCover = ok.slice().sort((a, b) => b.weed_pct - a.weed_pct);
  const high = byCover[0], low = byCover[byCover.length - 1];
  let cover = list(ok.map((r, i) => resultLabel(r) + (i === 0 ? ' puts weed cover at ' : ' at ') + fmtPct(r.weed_pct))) + '.';
  const gap = high.weed_pct - low.weed_pct;
  cover += gap < 1
    ? ' They agree closely on how much of the photo is weeds.'
    : ' ' + resultLabel(high) + ' sees the most weeds, ' + fmtNumber(gap, 1) + ' percentage points more than ' + resultLabel(low) + '.';
  const pressures = new Set(ok.map((r) => r.pressure));
  cover += pressures.size === 1
    ? ' ' + (ok.length === 2 ? 'Both put' : 'All of them put') + ' weed pressure at ' + ok[0].pressure + '.'
    : ' Weed pressure differs: ' + list(ok.map((r) => r.pressure + ' for ' + resultLabel(r))) + '.';
  out.push(cover);

  // Zones: where they make the same spraying decision
  const total = scan.params.grid_rows * scan.params.grid_cols;
  const sets = ok.map(zoneSet);
  const union = new Set(sets.flatMap((s) => [...s]));
  const common = [...union].filter((z) => sets.every((s) => s.has(z)));
  const sameDecision = total - (union.size - common.length);
  let zones;
  if (!union.size) {
    zones = 'None of them marks any zone for spraying, so their decisions are the same everywhere.';
  } else if (ok.length === 2) {
    const [a, b] = ok;
    const onlyA = [...sets[0]].filter((z) => !sets[1].has(z)).length;
    const onlyB = [...sets[1]].filter((z) => !sets[0].has(z)).length;
    if (!common.length) {
      zones = 'Out of ' + total + ' zones, they have none in common to spray: ' + resultLabel(a) + ' marks ' +
        sets[0].size + ' and ' + resultLabel(b) + ' marks ' + sets[1].size + ', all different.';
    } else {
    zones = 'Out of ' + total + ' zones, both mark ' + common.length + ' for spraying';
    if (onlyA || onlyB) {
      const extras = [];
      if (onlyA) extras.push(resultLabel(a) + ' adds ' + onlyA + ' more');
      if (onlyB) extras.push(resultLabel(b) + ' adds ' + onlyB + ' more');
      zones += '; ' + list(extras) + '.';
    } else {
      zones += ', and neither marks any other zone.';
    }
    }
  } else {
    zones = 'Out of ' + total + ' zones, ' + common.length + ' are marked for spraying by every result and ' + union.size +
      ' by at least one (' + list(ok.map((r, i) => resultLabel(r) + ' ' + sets[i].size)) + ').';
  }
  zones += ' They make the same spray-or-skip decision on ' + sameDecision + ' of the ' + total + ' zones (' +
    Math.round((sameDecision / total) * 100) + '%).';
  out.push(zones);

  // Savings
  const bySaving = ok.slice().sort((a, b) => a.savings.saved_pct - b.savings.saved_pct);
  const least = bySaving[0], most = bySaving[bySaving.length - 1];
  out.push(least.savings.saved_pct === most.savings.saved_pct
    ? (ok.length === 2 ? 'Both' : 'All of them') + ' save the same: ' + Math.round(most.savings.saved_pct) + '% of the herbicide, ' + fmtMoney(most.savings.saved_cost) + ' on this ' + fmtNumber(scan.params.area_ha) + ' ha field.'
    : 'Herbicide saved ranges from ' + Math.round(least.savings.saved_pct) + '% with ' + resultLabel(least) + ' to ' +
      Math.round(most.savings.saved_pct) + '% with ' + resultLabel(most) + ', that is ' + fmtMoney(least.savings.saved_cost) +
      ' to ' + fmtMoney(most.savings.saved_cost) + ' on this ' + fmtNumber(scan.params.area_ha) + ' ha field. The more zones a result marks, the less it saves.');

  let note = 'Where they disagree, swipe between the maps and check which one matches the plants in the photo. A disagreement shows where the methods are unsure, not which one is right; the Evaluation page shows how accurate each one is on hand-labelled photos.';
  if (ok.some(isDemo)) note += ' Results marked Demo model come from a placeholder model, so treat them as examples only.';
  out.push(note);
  return out;
}

export const CompareExplanation = (scan) => ExplainBox('What the comparison shows', () => paragraphs(scan));
