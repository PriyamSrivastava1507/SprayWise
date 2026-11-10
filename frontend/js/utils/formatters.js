import { CONFIG } from '../config.js';

const DASH = '–';
const nf = (min, max) => new Intl.NumberFormat(CONFIG.LOCALE, { minimumFractionDigits: min, maximumFractionDigits: max });
const one = nf(1, 1);
const two = nf(2, 2);
const money = new Intl.NumberFormat(CONFIG.LOCALE, { style: 'currency', currency: CONFIG.CURRENCY });
const moneyShort = new Intl.NumberFormat(CONFIG.LOCALE, { style: 'currency', currency: CONFIG.CURRENCY, maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const dayMonth = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' });
const clock = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' });

export const fmtPct = (n) => (n == null ? DASH : one.format(n) + '%');
export const fmtPctWhole = (n) => (n == null ? DASH : Math.round(n) + '%');
export const fmtMoney = (n) => (n == null ? DASH : money.format(n));
export const fmtMoneyShort = (n) => (n == null ? DASH : moneyShort.format(n));
export const fmtLitres = (n) => (n == null ? DASH : two.format(n) + ' L');
export const fmtNumber = (n, digits = 2) => (n == null ? DASH : nf(0, digits).format(n));
export const fmtFixed = (n) => (n == null ? DASH : two.format(n));
export const fmtMs = (n) => (n == null ? DASH : Math.round(n) + ' ms');
export const fmtDate = (iso) => dateTime.format(new Date(iso));
export const fmtDay = (iso) => dayMonth.format(new Date(iso));
export const fmtTime = (iso) => clock.format(new Date(iso));
export const currencySymbol = () =>
  (money.formatToParts(0).find((p) => p.type === 'currency') || { value: '' }).value;

export const methodLabel = (m) => (m === 'ml' ? 'ML segmentation' : 'Classical');
export const modeLabel = (m) => ({ classical: 'Classical', ml: 'ML segmentation', compare: 'Both methods' }[m] || m);

export const DEMO_MODEL_ID = 'fake-demo-model';
export const isDemo = (result) => result && result.model_id === DEMO_MODEL_ID;
export { DASH };
