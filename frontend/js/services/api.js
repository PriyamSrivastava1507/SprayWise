// The only place that calls fetch. Every failure becomes an ApiError with the
// backend's { error: { code, message } } shape, so pages handle one kind of error.
import { CONFIG } from '../config.js';

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export const apiUrl = (path) => CONFIG.API_BASE + CONFIG.API_PREFIX + path;

/** Image URLs from the API are relative (/media/...). */
export const mediaUrl = (path) => (!path ? null : /^https?:/.test(path) ? path : CONFIG.API_BASE + path);

export async function request(path, { method = 'GET', query, body, json, signal } = {}) {
  const url = new URL(apiUrl(path));
  for (const [k, v] of Object.entries(query || {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  }

  const init = { method, signal, headers: {} };
  if (json !== undefined) {
    init.body = JSON.stringify(json);
    init.headers['Content-Type'] = 'application/json';
  } else if (body) {
    init.body = body; // FormData: the browser sets the multipart boundary itself
  }

  let res;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError(0, 'network_error', 'Cannot reach the SprayWise server.');
  }

  if (res.status === 204) return null;
  const isJson = (res.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const e = data && data.error;
    throw new ApiError(
      res.status,
      e ? e.code : 'http_' + res.status,
      e ? e.message : 'The server answered with an error (' + res.status + ').',
    );
  }
  return data;
}

export const isAbort = (err) => err && err.name === 'AbortError';
