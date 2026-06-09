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

export async function postJson(path, body, options = {}) {
  options = { ...options };
  options.credentials = import.meta.env.DEV ? 'include' : 'same-origin';

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
