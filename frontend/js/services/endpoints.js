// Thin wrappers, one per backend resource. Field names match the API exactly.
import { request, apiUrl } from './api.js';

/**
 * @typedef {'ok'|'rows_not_detected'|'model_unavailable'|'failed'} ResultStatus
 * @typedef {{ method: 'classical'|'ml', status: ResultStatus, status_detail: ?string,
 *   model_id: ?string, vegetation_pct: ?number, crop_pct: ?number, weed_pct: ?number,
 *   pressure: ?('Low'|'Medium'|'High'), overlay_url: ?string, mask_url: ?string,
 *   grid: ?number[][], spray_cells: ?number[][], processing_ms: ?number,
 *   savings: { blanket_litres: ?number, spot_litres: ?number, saved_litres: ?number,
 *     blanket_cost: ?number, spot_cost: ?number, saved_cost: ?number, saved_pct: ?number } }} ScanResult
 * @typedef {{ id: number, field: ?{id: number, name: string}, created_at: string,
 *   mode: 'classical'|'ml'|'compare', width: number, height: number, original_url: string,
 *   params: { area_ha: number, dose_l_per_ha: number, price_per_l: number,
 *     grid_rows: number, grid_cols: number, cell_threshold: number },
 *   results: ScanResult[] }} Scan
 */

export const analysisApi = {
  /** @returns {Promise<Scan>} */
  analyze: (formData, signal) => request('/analyze', { method: 'POST', body: formData, signal }),
};

export const scansApi = {
  list: ({ fieldId, limit, offset } = {}, signal) =>
    request('/scans', { query: { field_id: fieldId, limit, offset }, signal }),
  get: (id, signal) => request('/scans/' + encodeURIComponent(id), { signal }),
  remove: (id) => request('/scans/' + encodeURIComponent(id), { method: 'DELETE' }),
  /** Re-cut the saved masks with other settings. save=false only previews. */
  recalculate: (id, settings, save, signal) => request('/scans/' + encodeURIComponent(id) + '/recalculate',
    { method: 'POST', query: { save: save ? 'true' : 'false' }, json: settings, signal }),
  exportUrl: (id, kind, method) =>
    apiUrl('/scans/' + id + '/export/' + kind) + (method ? '?method=' + method : ''),
};

export const fieldsApi = {
  list: (signal) => request('/fields', { signal }),
  create: (name) => request('/fields', { method: 'POST', json: { name } }),
  trend: (id, method, signal) => request('/fields/' + id + '/trend', { query: { method }, signal }),
};

export const evaluationApi = { get: (signal) => request('/evaluation', { signal }) };

export const healthApi = { get: (signal) => request('/health', { signal }) };
