// A small tooltip that follows the pointer over a map and describes the zone
// underneath: its position, weed share and whether it is sprayed.
import { h } from '../../utils/dom.js';

export function ZoneTooltip(host) {
  const tip = h('div', { class: 'zone-tip', role: 'tooltip', hidden: true });
  host.append(tip);
  return {
    show(zone, px, py, threshold) {
      if (!zone) { tip.hidden = true; return; }
      const pct = Math.round(zone.density * 1000) / 10;
      tip.replaceChildren(
        h('b', {}, 'Row ' + (zone.row + 1) + ', column ' + (zone.col + 1)),
        h('span', {}, pct + '% weeds'),
        h('span', { class: zone.sprayed ? 'tip-spray' : 'tip-skip' },
          zone.sprayed ? 'Sprayed (above ' + Math.round(threshold * 100) + '%)' : 'Skipped'));
      tip.hidden = false;
      const hw = host.clientWidth, hh = host.clientHeight;
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let left = px + 14, top = py + 14;
      if (left + tw > hw - 6) left = px - tw - 14;
      if (top + th > hh - 6) top = py - th - 14;
      tip.style.left = Math.max(6, left) + 'px';
      tip.style.top = Math.max(6, top) + 'px';
    },
    hide() { tip.hidden = true; },
  };
}
