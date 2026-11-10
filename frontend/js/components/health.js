// Header status: is the API up, and is the ML model real, a demo, or offline?
// Also keeps the latest /health answer so pages can read the pressure limits.
import { h } from '../utils/dom.js';
import { healthApi } from '../services/endpoints.js';
import { DEMO_MODEL_ID } from '../utils/formatters.js';

let latest = null;
const waiters = [];

/** Resolves with the latest /health payload (or null if the API is down). */
export function whenHealth() {
  return latest ? Promise.resolve(latest) : new Promise((resolve) => waiters.push(resolve));
}

function describe(health) {
  if (!health) return [{ tone: 'bad', text: 'API offline', title: 'The SprayWise server cannot be reached.' }];
  const api = health.database === 'ok'
    ? { tone: 'ok', text: 'API connected' }
    : { tone: 'bad', text: 'Database error', title: 'The server is up but cannot reach its database.' };
  const m = health.model;
  let model;
  if (!m.ready) model = { tone: 'bad', text: 'ML offline', title: m.detail || 'The ML model is not loaded.' };
  else if (m.model_id === DEMO_MODEL_ID) model = { tone: 'warn', text: 'ML: demo model', title: 'ML results come from a placeholder, not a trained model.' };
  else model = { tone: 'ok', text: 'ML ready', title: m.model_id };
  return [api, model];
}

export function startHealth(el) {
  let timer = null;

  async function check() {
    let health = null;
    try { health = await healthApi.get(); } catch { health = null; }
    latest = health;
    if (health) waiters.splice(0).forEach((resolve) => resolve(health));
    el.replaceChildren(...describe(health).map((s) =>
      h('span', { class: 'status-item', title: s.title || null },
        h('i', { class: 'dot dot-' + s.tone, 'aria-hidden': 'true' }), s.text)));
    // Poll quickly while something is wrong (cold start), slowly once healthy.
    const healthy = health && health.database === 'ok' && health.model.ready;
    clearTimeout(timer);
    timer = setTimeout(check, healthy ? 60000 : 10000);
  }

  addEventListener('online', check);
  check();
}
