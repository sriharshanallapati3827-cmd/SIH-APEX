/**
 * ==============================================================================
 * WeatherGPT Progressive Web App (PWA) — Service Worker
 * ==============================================================================
 * Architecture:
 *   - Stale-While-Revalidate for UI shell and styling
 *   - Network-First with Cache Fallback for dynamic weather telemetry
 *   - Offline Emergency Bulletin hydration when disconnected
 * ==============================================================================
 */

const CACHE_NAME = 'weathergpt-pwa-v1';

const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/chat.html',
  '/styles/landing.css',
  '/styles/chat.css',
  '/scripts/landing.js',
  '/scripts/chat.js',
  '/scripts/offline-store.js',
  '/manifest.json',
  '/icons/icon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

// ── 1. INSTALL EVENT ────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching UI shell assets');
      return cache.addAll(SHELL_ASSETS).catch((err) => {
        console.warn('[SW] Partial pre-cache failure:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// ── 2. ACTIVATE EVENT ───────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[SW] Purging outdated cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// ── 3. FETCH EVENT ──────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Only handle GET requests for caching
  if (request.method !== 'GET') {
    return;
  }

  // A. Static Shell Assets & Fonts: Stale-While-Revalidate
  if (
    url.origin === self.location.origin ||
    url.hostname.includes('fonts.googleapis.com') ||
    url.hostname.includes('fonts.gstatic.com')
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const responseClone = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
            }
            return networkResponse;
          })
          .catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // B. External API Calls (e.g., Open-Meteo): Network-first with Cache fallback
  if (url.hostname.includes('open-meteo.com')) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        })
        .catch(() => caches.match(request))
    );
  }
});
