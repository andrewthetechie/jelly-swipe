self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});


self.addEventListener('fetch', (event) => {
    // Don't intercept SSE / streaming requests — pass through natively.
    // ServiceWorker fetch() wraps the response in a regular Response object
    // which breaks text/event-stream long-lived connections.
    const url = new URL(event.request.url);
    if (event.request.headers.get('Accept')?.includes('text/event-stream') ||
        url.pathname === '/room/stream') {
        return; // Let the browser handle SSE natively
    }
    event.respondWith(fetch(event.request));
});
