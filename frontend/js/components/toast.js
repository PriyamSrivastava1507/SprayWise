export function toast(message, { tone = 'info', ms = 3500 } = {}) {
  const host = document.getElementById('toasts');
  if (!host) return;
  const el = document.createElement('div');
  el.className = 'toast toast-' + tone;
  el.setAttribute('role', tone === 'error' ? 'alert' : 'status');
  el.textContent = message;
  host.append(el);
  setTimeout(() => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 250);
  }, ms);
}
