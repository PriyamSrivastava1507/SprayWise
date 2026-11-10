// The three states every page needs: loading, empty and error.
import { h } from '../utils/dom.js';

export const Loader = (message = 'Loading…') =>
  h('div', { class: 'state state-loading', role: 'status' },
    h('span', { class: 'spinner', 'aria-hidden': 'true' }), h('span', {}, message));

export const EmptyState = (title, text, action) =>
  h('div', { class: 'state state-empty' },
    h('h2', {}, title), text ? h('p', {}, text) : null, action || null);

// One place that turns an error code into advice someone can act on.
const ADVICE = {
  network_error: 'Check that the backend is running and that this page is served from an allowed address (see the frontend README).',
  file_too_large: 'Use a smaller photo or export it at a lower resolution.',
  invalid_image: 'Use a JPG or PNG photo straight from the camera.',
  model_unavailable: 'The ML model is offline. Run the analysis with Classical, or with Both to keep the classical result.',
  not_found: 'It may have been deleted. Open History to see what is available.',
  validation_error: 'Check the highlighted values and try again.',
  internal_error: 'The server hit an unexpected problem. Try again, and if it repeats, report the request ID from the browser’s Network tab.',
};

export function ErrorState(err, onRetry) {
  const advice = ADVICE[err && err.code];
  return h('div', { class: 'state state-error', role: 'alert' },
    h('h2', {}, (err && err.message) || 'Something went wrong.'),
    advice ? h('p', {}, advice) : null,
    onRetry ? h('button', { class: 'btn btn-quiet', type: 'button', onclick: onRetry }, 'Try again') : null);
}

export const adviceFor = (code) => ADVICE[code] || null;
