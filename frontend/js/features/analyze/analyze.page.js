import { h } from '../../utils/dom.js';
import { analysisApi } from '../../services/endpoints.js';
import { isAbort } from '../../services/api.js';
import { ErrorState, Loader } from '../../components/states.js';
import { toast } from '../../components/toast.js';
import { AnalysisForm } from './analysis-form.js';
import { ScanView } from './scan-results.js';

function Intro() {
  return h('div', { class: 'intro' },
    h('h1', {}, 'Find the weeds, spray only where they are.'),
    h('p', {}, 'Upload a photo taken straight down over a crop row. SprayWise marks crop and weeds, splits the photo into zones and shows which zones need herbicide, with the litres and money saved against spraying the whole field.'),
    h('dl', { class: 'intro-legend' },
      h('div', {}, h('dt', {}, h('i', { style: { background: 'var(--crop)' } }), 'Crop'), h('dd', {}, 'left untouched')),
      h('div', {}, h('dt', {}, h('i', { style: { background: 'var(--weed)' } }), 'Weeds'), h('dd', {}, 'measured per zone')),
      h('div', {}, h('dt', {}, h('i', { class: 'zone-swatch' }), 'Spray zone'), h('dd', {}, 'weeds above your threshold'))));
}

export function mount(root) {
  const ctrl = new AbortController();
  const out = h('section', { class: 'workspace-main', 'aria-live': 'polite' }, Intro());

  const form = AnalysisForm({
    onSubmit: async (fd) => {
      out.replaceChildren(Loader(fd.get('mode') === 'compare' ? 'Running both methods on the photo…' : 'Analyzing the photo…'));
      try {
        const scan = await analysisApi.analyze(fd, ctrl.signal);
        out.replaceChildren(ScanView(scan, { onRerun: (mode) => form.submitWithMode(mode) }));
        toast('Scan ' + scan.id + ' saved to History.');
        if (matchMedia('(max-width: 860px)').matches) out.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (err) {
        if (isAbort(err)) return;
        if (err.code === 'validation_error') form.showServerError(err.message);
        out.replaceChildren(ErrorState(err));
      }
    },
  });

  root.replaceChildren(h('div', { class: 'workspace' }, h('aside', { class: 'workspace-side' }, form), out));
  return () => ctrl.abort();
}
