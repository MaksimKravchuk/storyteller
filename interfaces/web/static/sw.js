const CACHE_NAME = "STORYTELLER-PWA-CACHE-v1";
const OFFLINE_DETAIL = "Storyteller needs an internet connection and model access to continue.";
const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/static/style.css",
  "/static/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

function offlineJson() {
  return new Response(JSON.stringify({ detail: OFFLINE_DETAIL }), {
    status: 503,
    headers: { "Content-Type": "application/json" },
  });
}

function offlineHtml() {
  return new Response(
    "<!DOCTYPE html><title>Storyteller offline</title><p>" + OFFLINE_DETAIL + "</p>",
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}

function requestPath(request) {
  return new URL(request.url).pathname;
}

function isApiOrMutation(request) {
  return requestPath(request).startsWith("/api/") || request.method !== "GET";
}

function shouldCacheShell(request, response) {
  return response.ok && PRECACHE_URLS.includes(requestPath(request));
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (shouldCacheShell(request, response)) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (request.mode === "navigate") {
      return (await cache.match("/")) || offlineHtml();
    }
    throw err;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (isApiOrMutation(request)) {
    event.respondWith(fetch(request).catch(() => offlineJson()));
    return;
  }
  event.respondWith(networkFirst(request));
});
