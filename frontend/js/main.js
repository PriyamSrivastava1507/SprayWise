import { startRouter } from './router.js';
import { startHealth } from './components/health.js';

startHealth(document.getElementById('health'));

startRouter(document.getElementById('app'), [
  { path: '/analyze', title: 'Analyze', load: () => import('./features/analyze/analyze.page.js') },
  { path: '/compare', title: 'Compare', load: () => import('./features/compare/compare.page.js') },
  { path: '/history', title: 'History', load: () => import('./features/history/history.page.js') },
  { path: '/scans/:id', title: 'Scan', load: () => import('./features/history/scan-detail.page.js') },
  { path: '/evaluation', title: 'Evaluation', load: () => import('./features/evaluation/evaluation.page.js') },
]);
