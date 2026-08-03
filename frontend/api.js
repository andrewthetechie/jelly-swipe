const DEFAULT_API_BASE_URL = 'http://localhost:5005';

export function getApiBaseUrl() {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return new URL(configuredBaseUrl);
  }

  const currentLocation = typeof window !== 'undefined' && window.location
    ? window.location
    : globalThis.location;

  if (currentLocation?.origin) {
    return new URL(currentLocation.origin);
  }

  return new URL(DEFAULT_API_BASE_URL);
}

export function apiUrl(path) {
  return new URL(path, getApiBaseUrl());
}

export async function apiFetch(path, options = {}) {
  options = { ...options };
  options.credentials = 'same-origin';

  if (options.headers == null) {
    options.headers = {};
  }

  return fetch(apiUrl(path), options);
}

export async function postJson(path, body, options = {}) {
  options = { ...options };
  options.credentials = 'same-origin';

  if (options.headers == null) {
    options.headers = {};
  }

  options.headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  return fetch(apiUrl(path), {
    method: 'POST',
    body: JSON.stringify(body),
    ...options,
  });
}

export function formatRating(r) {
  return Number(r).toFixed(2)
}