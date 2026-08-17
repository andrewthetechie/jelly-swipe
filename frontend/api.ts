const DEFAULT_API_BASE_URL = 'http://localhost:5005';

export function getApiBaseUrl(): URL {
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

export function apiUrl(path: string): URL {
  return new URL(path, getApiBaseUrl());
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(apiUrl(path), {
    ...options,
    credentials: 'same-origin',
  });
}

export async function postJson(path: string, body?: unknown, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');

  const request: RequestInit = {
    ...options,
    credentials: 'same-origin',
    headers,
    method: 'POST',
  };

  if (body !== undefined) {
    request.body = JSON.stringify(body);
  }

  return fetch(apiUrl(path), request);
}