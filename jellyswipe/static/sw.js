self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});


self.addEventListener('fetch', (event) => {
    // Let the browser handle requests natively when re-issuing via fetch()
    // would change semantics:
    // - SSE / event-stream: wrapping breaks long-lived text/event-stream connections.
    // - Cross-origin (e.g. image.tmdb.org cast photos): no-cors <img> requests
    //   fail with NetworkError when re-issued through the ServiceWorker.
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) {
        return;
    }
    if (event.request.headers.get('Accept')?.includes('text/event-stream') ||
        url.pathname === '/room/stream') {
        return;
    }
    event.respondWith(fetch(event.request));
});
