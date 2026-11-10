// A small hash router (#/history, #/scans/12). Pages are modules exporting
// mount(root, params), loaded only when visited. mount may return a cleanup
// function, called when the user leaves the page.
import { Loader, ErrorState, EmptyState } from './components/states.js';
import { h } from './utils/dom.js';

function match(pattern, path) {
  const a = pattern.split('/'), b = path.split('/');
  if (a.length !== b.length) return null;
  const params = {};
  for (let i = 0; i < a.length; i++) {
    if (a[i].startsWith(':')) params[a[i].slice(1)] = decodeURIComponent(b[i]);
    else if (a[i] !== b[i]) return null;
  }
  return params;
}

export function startRouter(outlet, routes) {
  let cleanup = null;
  let token = 0;

  async function render() {
    const path = location.hash.slice(1) || '/analyze';
    const mine = ++token;
    if (cleanup) { cleanup(); cleanup = null; }

    for (const a of document.querySelectorAll('#nav a')) {
      const target = a.getAttribute('href').slice(1);
      const active = path === target || path.startsWith(target + '/') ||
        (target === '/history' && path.startsWith('/scans/'));
      if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    }

    for (const route of routes) {
      const params = match(route.path, path);
      if (!params) continue;
      outlet.replaceChildren(Loader());
      try {
        const mod = await route.load();
        if (mine !== token) return; // the user navigated away while loading
        const c = (await mod.mount(outlet, params)) || null;
        if (mine !== token) { if (c) c(); } else cleanup = c;
        document.title = (route.title ? route.title + ' – ' : '') + 'SprayWise';
      } catch (err) {
        if (mine === token) outlet.replaceChildren(ErrorState(err, render));
      }
      return;
    }
    outlet.replaceChildren(EmptyState('This page does not exist', 'Check the address, or go back to Analyze.',
      h('a', { class: 'btn btn-quiet', href: '#/analyze' }, 'Go to Analyze')));
  }

  addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
  render();
}
