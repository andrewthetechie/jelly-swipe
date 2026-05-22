export function getApiBaseUrl() {
  if (import.meta.env.DEV) {
    return new URL('http://localhost:5005');
  }
  return new URL(window.location.origin);
}

export function apiUrl(path) {
  return new URL(path, getApiBaseUrl());
}

export async function apiFetch(path, options = {}) {
  options = { ...options };
  options.credentials = import.meta.env.DEV ? 'include' : 'same-origin';

  if (options.headers == null) {
    options.headers = {};
  }

  return fetch(apiUrl(path), options);
}
