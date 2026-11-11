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
  const models = health.models && health.models.length ? health.models : [{ ...health.model, label: 'ML model' }];
  const ready = models.filter((m) => m.ready);
  const demo = ready.filter((m) => m.model_id === DEMO_MODEL_ID);
  const title = models.map((m) => m.label + ': ' + (!m.ready ? 'offline' + (m.detail ? ' (' + m.detail + ')' : '')
    : m.model_id === DEMO_MODEL_ID ? 'demo model' : 'ready')).join('\n');
  let model;
  if (!ready.length) model = { tone: 'bad', text: 'ML offline', title };
  else if (ready.length < models.length) model = { tone: 'warn', text: 'ML: ' + ready.length + ' of ' + models.length + ' models ready', title };
  else if (demo.length === ready.length) model = { tone: 'warn', text: models.length > 1 ? 'ML: demo models' : 'ML: demo model', title };
  else model = { tone: 'ok', text: models.length > 1 ? 'ML: ' + models.length + ' models ready' : 'ML ready', title };
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
    const healthy = health && health.database === 'ok' && (health.models || [health.model]).every((m) => m.ready);
    clearTimeout(timer);
    timer = setTimeout(check, healthy ? 60000 : 10000);
  }

  addEventListener('online', check);
  check();
}
