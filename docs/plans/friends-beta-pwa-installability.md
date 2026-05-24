# Friends Beta v0.2 — PWA installability implementation plan

Issue: #236  
Owner/profile: Web UI engineer  
Release impact: invited Friends Beta testers can install Storyteller and launch it like an app, while gameplay remains online-required.

## Objective

Make the existing FastAPI-served web UI installable as a PWA with a manifest, app icons, a service worker, and a clear offline/poor-network state. Do **not** add offline gameplay, local story persistence, background sync, or speculative PWA abstractions.

## Acceptance criteria

- `GET /` links a valid web app manifest and registers a service worker.
- `GET /manifest.webmanifest` returns a valid installability manifest with Storyteller name, start URL, standalone display mode, theme/background colors, and required icons.
- `GET /sw.js` returns JavaScript with a service-worker content type and a root scope.
- App icons are present under `interfaces/web/static/icons/` and are referenced by the manifest.
- The installed app shell can open from `/` when previously cached.
- When the browser is offline or gameplay requests fail because the network is unavailable, the UI says Storyteller needs internet/model access to continue.
- No UI or copy claims offline gameplay.
- Existing gameplay API behavior remains online-required and unchanged.

## Current touch points

- `interfaces/web/static/index.html` — HTML shell; currently links only `/static/style.css` and `/static/app.js`.
- `interfaces/web/static/app.js` — fetches `/api/games/current`, `/api/games`, `/api/character-template`, and `/api/games/{game_id}/actions`; currently shows generic load/start/action errors.
- `interfaces/web/static/style.css` — app styling; add only the offline banner/status styles needed by this feature.
- `interfaces/web/routes.py` — currently serves `/`, `/healthz`, `/readyz`, and gameplay API routes; add top-level PWA asset routes here.
- `interfaces/web/app.py` — mounts `/static`; no broad app factory refactor expected.
- `tests/test_web_api.py` — existing FastAPI route/static-shell tests; add PWA route and shell assertions here.

## Implementation tasks

### 1. Add failing route tests for PWA assets

Objective: lock the server contract before adding files/routes.

Files:

- `tests/test_web_api.py`

Tasks:

- Add constants for any new status/content-type checks if needed.
- Add a `Static shell` test that `GET /manifest.webmanifest` returns HTTP 200, includes `application/manifest+json` or JSON-compatible content type, and has at least:
  - `name: "Storyteller"`
  - `short_name: "Storyteller"`
  - `start_url: "/"`
  - `scope: "/"`
  - `display: "standalone"`
  - non-empty `icons` entries including `192x192` and `512x512` PNG icons.
- Add a `Static shell` test that `GET /sw.js` returns HTTP 200, JavaScript content type, and service-worker source containing the offline message copy: `Storyteller needs an internet connection and model access to continue.`
- Add a `Static shell` test that `GET /` includes:
  - `<link rel="manifest" href="/manifest.webmanifest">`
  - a theme-color meta tag.
  - a script path or inline script that registers `/sw.js`.

Verification command:

```bash
uv run pytest tests/test_web_api.py -k "manifest or sw or index"
```

Expected before implementation: the new tests fail because `/manifest.webmanifest`, `/sw.js`, and shell links are absent.

### 2. Add manifest and icon assets

Objective: provide browser-installable metadata and icons without changing gameplay.

Files:

- `interfaces/web/static/manifest.webmanifest`
- `interfaces/web/static/icons/icon-192.png`
- `interfaces/web/static/icons/icon-512.png`
- Optional only if generated with the same source: `interfaces/web/static/icons/maskable-icon-512.png`

Tasks:

- Create `interfaces/web/static/manifest.webmanifest` with concrete values:
  - `name`: `Storyteller`
  - `short_name`: `Storyteller`
  - `description`: `An online AI storytelling game.`
  - `start_url`: `/`
  - `scope`: `/`
  - `display`: `standalone`
  - `background_color`: match the current page background from `interfaces/web/static/style.css`.
  - `theme_color`: match the header/accent color from `interfaces/web/static/style.css`.
  - `icons`: reference `/static/icons/icon-192.png` and `/static/icons/icon-512.png` with correct `sizes` and `type: "image/png"`.
- Add simple Storyteller-branded PNG icons at 192x192 and 512x512. Keep them static files; do not introduce an asset pipeline.
- If a maskable icon is added, reference it with `purpose: "maskable"`; otherwise keep the manifest minimal with `purpose: "any"` or no purpose field.

Verification command:

```bash
python -m json.tool interfaces/web/static/manifest.webmanifest >/dev/null
file interfaces/web/static/icons/icon-192.png interfaces/web/static/icons/icon-512.png
```

### 3. Serve top-level PWA asset URLs

Objective: expose PWA assets at browser-expected top-level paths while reusing static files.

Files:

- `interfaces/web/routes.py`

Tasks:

- Add `_MANIFEST = _STATIC_DIR / "manifest.webmanifest"`.
- Add `_SERVICE_WORKER = _STATIC_DIR / "sw.js"`.
- Add `@router.get("/manifest.webmanifest", include_in_schema=False)` returning `FileResponse(_MANIFEST, media_type="application/manifest+json")`.
- Add `@router.get("/sw.js", include_in_schema=False)` returning `FileResponse(_SERVICE_WORKER, media_type="text/javascript")`.
- Do not move `/static` mounting or add dynamic manifest generation.

Verification command:

```bash
uv run pytest tests/test_web_api.py -k "manifest or sw"
```

### 4. Link the manifest and register the service worker

Objective: make the shell advertise installability and start service-worker installation.

Files:

- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`

Tasks:

- In `index.html` `<head>`, add:
  - `<link rel="manifest" href="/manifest.webmanifest" />`
  - `<meta name="theme-color" content="..." />` using the same manifest theme color.
  - Optional iOS-friendly tags only if kept literal and minimal, such as `apple-mobile-web-app-capable` and `apple-mobile-web-app-title`.
- In `app.js`, add a small `registerServiceWorker()` function that:
  - checks `"serviceWorker" in navigator`.
  - calls `navigator.serviceWorker.register("/sw.js")` after the page loads or during current initialization.
  - catches registration failures and logs with `console.warn` only; do not block gameplay UI.
- Call `registerServiceWorker()` once during startup.

Verification command:

```bash
uv run pytest tests/test_web_api.py -k "index"
```

### 5. Add an online-required service worker

Objective: cache only the app shell/assets needed to open the installed app and show an honest offline response; keep gameplay network-first and online-required.

Files:

- `interfaces/web/static/sw.js`

Tasks:

- Define a versioned cache name, for example `storyteller-shell-v1`.
- Precache only:
  - `/`
  - `/static/style.css`
  - `/static/app.js`
  - `/manifest.webmanifest`
  - `/static/icons/icon-192.png`
  - `/static/icons/icon-512.png`
- On `install`, open the cache and add those URLs; call `self.skipWaiting()` after successful caching.
- On `activate`, delete old `storyteller-shell-*` caches and call `self.clients.claim()`.
- On `fetch`:
  - For non-GET requests, do not cache; try `fetch(event.request)` and if it fails return a JSON `503` response with `{"detail":"Storyteller needs an internet connection and model access to continue."}` and `Content-Type: application/json`.
  - For `GET` requests whose pathname starts with `/api/`, use network-only; if it fails return the same JSON `503` response.
  - For shell/static GET requests, try network first and fall back to cached response.
  - For navigation requests, try network first and fall back to cached `/`; if neither is available, return a small HTML response that says `Storyteller needs an internet connection and model access to continue.`
- Do not cache API responses, generated story state, player actions, auth/session data, or model output.

Verification commands:

```bash
uv run pytest tests/test_web_api.py -k "sw"
python -m compileall interfaces/web/static >/dev/null
```

Manual browser verification is in task 8.

### 6. Add player-visible offline/poor-network messaging in the UI

Objective: make online-required behavior clear when the app is installed or the connection drops.

Files:

- `interfaces/web/static/index.html`
- `interfaces/web/static/app.js`
- `interfaces/web/static/style.css`

Tasks:

- Add a small banner near the top of `<main id="app">`, initially hidden, with copy: `Storyteller needs an internet connection and model access to continue.`
- In `app.js`, add `offlineBanner` to `els`.
- Add helper functions:
  - `isProbablyOfflineError(err)` using `navigator.onLine === false` or failed fetch errors.
  - `setOfflineNotice(visible)` to show/hide the banner.
- Add `window` listeners for `online` and `offline` to update the banner immediately.
- In `loadCurrent`, `onStartGame`, `onUseTemplate`, and `onSubmitAction` catch blocks, show the banner when the failure is probably offline; keep existing status messages but change network-failure copy to the online-required message where appropriate.
- Do not disable the entire UI permanently; let players retry when they are back online.

Verification command:

```bash
uv run pytest tests/test_web_api.py -k "index"
```

Manual verification is in task 8 because the current test suite does not run browser JavaScript.

### 7. Run the focused automated test suite

Objective: prove the route contract and existing web API behavior still pass.

Files:

- No new files beyond this feature's implementation files.

Tasks:

- Run the focused FastAPI web tests.
- If failures appear outside PWA changes, investigate before broadening scope.

Verification command:

```bash
uv run pytest tests/test_web_api.py
```

### 8. Manual installability and online-required verification

Objective: verify real browser PWA behavior that unit tests cannot cover.

Files:

- No code changes unless verification reveals a defect.

Tasks:

- Start the local app:

```bash
uv run uvicorn interfaces.web.app:app --reload
```

- Open the app in Chrome/Edge at `http://127.0.0.1:8000/`.
- In DevTools > Application > Manifest, confirm:
  - manifest loads without errors.
  - icons load.
  - display mode is `standalone`.
  - installability criteria pass for localhost.
- Install the app from the browser UI and launch it.
- With the server online, confirm the shell loads and existing start/action flows still call the online API.
- In DevTools > Network, set Offline and reload the installed app:
  - shell opens from cache if previously installed/cached.
  - UI shows `Storyteller needs an internet connection and model access to continue.`
  - starting a game or submitting an action does not claim offline play.
- Restore the network and confirm retrying normal gameplay works.

### 9. Update beta onboarding docs only if they already exist in this branch

Objective: add install instructions without inventing a new docs structure.

Files:

- Prefer an existing Friends Beta onboarding/testing doc if present.
- If no such doc exists, defer this deliverable to the beta onboarding issue and mention it in the PR notes.

Tasks:

- Search for an existing tester onboarding/install instructions file.
- If present, add brief install steps:
  - open the beta URL.
  - use browser install/add-to-home-screen action.
  - note: `Gameplay requires an internet connection and model access.`
- Do not add broad privacy, auth, or release-process docs in this PWA issue.

Verification command:

```bash
uv run pytest tests/test_web_api.py
```

## Final quality gate

Run before opening the PR:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest
```

PR evidence should include:

- Output from `uv run pytest tests/test_web_api.py`.
- Output from the final quality gate, or a clear note for any pre-existing unrelated failures.
- Screenshot or short recording of browser manifest/installability state.
- Screenshot of the offline banner/message in the installed app.

## Out of scope

- Offline gameplay.
- Caching API responses, stories, turns, auth tokens, or model outputs.
- Background sync or queued offline actions.
- Push notifications.
- A frontend framework, bundler, or asset pipeline.
- Account/auth changes; those belong to the Friends Beta auth/invite workstream.
