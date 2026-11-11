// #/scans/:id: one stored scan, reusing the Analyze result view.
import { h } from '../../utils/dom.js';
import { isAbort } from '../../services/api.js';
import { scansApi } from '../../services/endpoints.js';
import { ErrorState } from '../../components/states.js';
import { toast } from '../../components/toast.js';
import { ScanView } from '../analyze/scan-results.js';
import { SideBySide, SwipePanel } from '../compare/compare.page.js';
import { CompareExplanation } from '../compare/compare-explanation.js';

export async function mount(root, { id }) {
  const ctrl = new AbortController();
  const back = h('a', { href: '#/history', class: 'back-link' }, 'Back to history');

  let scan;
  try {
    scan = await scansApi.get(id, ctrl.signal);
  } catch (err) {
    if (isAbort(err)) return null;
    root.replaceChildren(back, ErrorState(err, () => mount(root, { id })));
    return () => ctrl.abort();
  }

  const actions = h('div', { class: 'detail-actions' });
  function idle() {
    actions.replaceChildren(h('button', { type: 'button', class: 'link-btn danger', onclick: confirm }, 'Delete scan'));
  }
  function confirm() {
    actions.replaceChildren(h('span', { class: 'confirm-text' }, 'Delete this scan and its images?'),
      h('button', { type: 'button', class: 'link-btn danger', onclick: remove }, 'Delete'),
      h('button', { type: 'button', class: 'link-btn', onclick: idle }, 'Keep'));
    actions.querySelector('button').focus();
  }
  async function remove() {
    try {
      await scansApi.remove(scan.id);
      toast('Scan ' + scan.id + ' deleted.');
      location.hash = '#/history';
    } catch (err) {
      toast(err.message, { tone: 'error' });
      idle();
    }
  }
  idle();

  const view = ScanView(scan);
  const swipeBody = SwipePanel(scan);
  const swipe = swipeBody ? h('section', { class: 'panel swipe-panel' }, h('h2', { class: 'panel-title' }, 'Swipe between results'), swipeBody) : null;

  root.replaceChildren(...[
    h('div', { class: 'detail-bar' }, back, actions),
    view,
    swipe,
    scan.results.length > 1 ? SideBySide(scan) : null,
    scan.results.length > 1 ? CompareExplanation(scan) : null,
  ].filter(Boolean));
  return () => { ctrl.abort(); view.dispose(); };
}
