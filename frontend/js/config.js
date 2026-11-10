// Everything that changes between a laptop and a server lives here.
// This file is public: never put secrets in it.

const isLocal = ['localhost', '127.0.0.1', ''].includes(location.hostname);

export const CONFIG = {
  // Where the FastAPI backend runs. Change the second value when you deploy.
  API_BASE: isLocal ? 'http://localhost:8000' : 'https://YOUR-BACKEND-URL',
  API_PREFIX: '/api/v1',

  MAX_UPLOAD_MB: 10, // must match the backend's MAX_UPLOAD_MB

  // How money is shown. Amounts come from the API; this only formats them.
  LOCALE: 'en-IN',
  CURRENCY: 'INR',

  PAGE_SIZE: 10, // rows per page on History
};
