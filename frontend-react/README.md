# FinEx React client — server-owned local application

The active application starts at `/login`. Sprint 1 implements approved synthetic persona sign-in/out, current educational consent, durable partial profiles, draft resume and explicit server-confirmed completion. It runs natively; Docker, cloud credentials and a mobile emulator are not required.

This is a loopback-only educational simulator, not production hosting, Google OAuth or real-person authentication. Anyone trusted to use the machine may deliberately select either `learner-a` or `learner-b`.

## Start the native backend

Use the repository toolchain (Python 3.13, Node 24.20.0 from `.nvmrc`). At the repository root:

```powershell
.\scripts\bootstrap.ps1 -Component Backend
$env:APP_ENV = 'local'
$env:LOCAL_APP_ENABLED = 'true'
$env:LOCAL_SESSION_TTL_MINUTES = '30'
$env:LOCAL_DB_PATH = Join-Path $env:LOCALAPPDATA 'FinEx\development\finex.sqlite3'
$env:ALLOWED_ORIGINS = 'http://127.0.0.1:3001'
$env:ALLOW_CREDENTIALS = 'false'
$env:LLM_PROVIDER = 'none'
$env:MARKET_DATA_PROVIDER = 'mock'
.\scripts\run-backend.ps1 -BindAddress '127.0.0.1' -Port 8000
```

Keep the database outside live OneDrive/Dropbox synchronization. Startup resumes saved data; it does not reset the database. See the [native application runbook](../docs/runbooks/native-local-application.md) for safe backup, troubleshooting and recovery. Never expose the simulator to a LAN, public binding or tunnel.

## Start React in a second terminal

```powershell
Set-Location frontend-react
npm ci
$env:HOST = '127.0.0.1'
$env:PORT = '3001'
$env:BROWSER = 'none'
$env:REACT_APP_FINEX_API_BASE_URL = 'http://127.0.0.1:8000'
$env:NODE_OPTIONS = '--max-old-space-size=1536'
npm start
```

Open `http://127.0.0.1:3001/login`. `/` redirects there. If those ports are occupied, choose unused loopback ports and update both the API origin and the backend's explicit allowed client origin. Do not stop another developer's existing process.

On an 8 GB machine, run the API and only the client you are developing; run tests serially and avoid overlapping builds. Prefer a normal local clone outside synchronization folders for `npm ci`, because sync clients can lock `node_modules` files.

`REACT_APP_FINEX_API_BASE_URL` is public build-time configuration, never a place for secrets. The persistent client accepts only an HTTP(S) loopback origin (`localhost`, `127.0.0.1`, `[::1]`) without credentials, query, fragment or a path. It rejects unsafe origins before login, omits cookies, forbids redirects and bounds both request and body-decoding time.

## Use the S1 journey

1. Select an approved synthetic persona. The server, not a supplied owner ID or browser flag, chooses its identity.
2. Read the `consent.v1` educational notice. A checkbox alone does not save it: use **Save consent choice**. Withdrawal remains available.
3. Enter only a non-sensitive display label (at most 80 Unicode characters) and self-declared experience. **Save draft** permits missing fields and does not imply completion.
4. Reload or close/reopen the client. It starts signed out; select the same persona again to resume its server draft.
5. Supply both profile fields and saved current consent; select **Complete onboarding**. Failed saves preserve input and never claim completion. The backend rechecks prerequisites atomically.
6. Use **Sign out**. Only server-confirmed logout or a current `401` clears owned client state. A network failure keeps the session/input with **Retry sign out**.

The bearer exists only in private React context memory, never localStorage, sessionStorage, a URL or a diagnostic. Session expiry and revocation are enforced by the backend. A persona change invalidates or ignores outstanding work, including stale success, logout and `401` responses.

`/onboarding` requires a validated session; `/consent` aliases its consent section. `/dashboard`, `/risk`, `/portfolio`, `/market`, `/watchlist`, `/paper-trading` and `/goals` require a fresh server check, completed profile and current accepted consent. Loading/errors cannot unlock them. Consent withdrawal, reacceptance without recompletion or a changed saved profile removes completion.

The S1 dashboard shows only saved profile, consent and completion. S2–S4 feature routes explicitly say delivery is pending until their slices are accepted. There are no invented balances, returns or pretend trades. Chat, alerts and spending are outside this delivery.

## Compatibility pilots are separate

Public `/pilot/consent`, `/pilot/onboarding` and `/pilot/risk` retain the older versioned, stateless contract demonstrations. They are visibly marked **Compatibility pilot — not saved to a persona**. Their separate browser journey marker is not identity and cannot unlock the persistent application.

Only these compatibility adapters use `REACT_APP_ONBOARDING_MODE=fixture|api` and `REACT_APP_RISK_MODE=fixture|api`; their existing defaults remain fixture-based. The active full application always uses `/api/v1/local-auth/*` and `/api/v1/local-onboarding/*`. It never silently falls back to a fixture when the API is unavailable or disabled.

## Verify before submitting a PR

```powershell
$env:CI = 'true'
$env:NODE_OPTIONS = '--max-old-space-size=1536'
npm test -- --runInBand --watchAll=false --no-cache
node .\node_modules\typescript\bin\tsc --noEmit
npm run build
```

Keep the original 65 legacy regressions. New tests cover contract scope/version/nullability, origin/timeout/error safety, memory-only session lifetime, generation races, exact operation confirmation, current server route guards, draft retries, consent lifecycle and pilot separation. Component/mock tests do not replace a real HTTP/browser journey. Record the exact commands, results and tested SHA; see the [delivery contract](../docs/features/local-application/S1-S4-delivery-contract.md) and acceptance evidence for the actual verified boundary and remaining external gates.
