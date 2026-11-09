# FinEx Flutter client — owned local application

The Flutter client runs natively on a developer machine; Docker and an
always-on mobile emulator are not required.

## Start the full application (S1 and S2 client)

The default `/` redirects to `/login`. The full application is **API-only**:
it never silently falls back to fixtures, device preferences, fabricated JWTs
or the older onboarding flow flags. Select `learner-a` or `learner-b`; this is
a trusted loopback-only synthetic identity simulation, not Google OAuth or
authentication of a real person. Do not enter real personal or financial data.

First start the native API using the
[local application runbook](../docs/runbooks/native-local-application.md).
It requires `APP_ENV=local`, `LOCAL_APP_ENABLED=true`, a loopback bind, and an
explicit frontend origin in `ALLOWED_ORIGINS`. SQLite runs inside the API:
no Docker, hosted database or cloud account is needed. Keep an active SQLite
database outside a synchronized OneDrive/Dropbox folder.

From a second PowerShell terminal, use one browser target:

```powershell
cd frontend_flutter
flutter pub get
flutter analyze --fatal-infos
flutter test --concurrency=1
flutter run -d chrome --web-hostname=127.0.0.1 --web-port=3002 `
  --dart-define=FINEX_API_BASE_URL=http://127.0.0.1:8000
```

`flutter run -d chrome` is the lightest supported interactive target. It uses
the existing browser rather than an Android emulator, making it suitable for
8 GB and 16 GB laptops. Use `flutter devices` to see other locally supported
targets.

`FINEX_API_BASE_URL` must be an HTTP(S) loopback **origin**, not an `/api` path:
`localhost`, `127.0.0.1`, or `[::1]`, valid port, no URL credentials, query or
fragment. Nonlocal configuration fails visibly before acquiring/sending a
bearer. This non-secret compile-time value needs a restart/rebuild to change.
Never put tokens or secrets in `--dart-define` values.

The web HTTP transport explicitly uses `credentials: omit`, `cache: no-store`
and `redirect: error`. The native transport forces direct loopback connections;
ambient HTTP/HTTPS proxy settings cannot forward session authority. Bearers
travel only in the Authorization header, stay
in memory, and are neither printed nor saved in SharedPreferences or browser
storage. The request timeout includes the body and decoding. Responses are
limited to 262,144 bytes; web readers and native response streams are cancelled
as soon as the cap is exceeded, including a body that never finishes. A real 401 clears
current authority immediately; a late response from a previous learner does
not overwrite or sign out the new learner. Replacing the injected session/API
resets the owned journey/router and disposes only resources the app created.

## Saved journey and visible failure handling

1. Sign in, validate the server identity, then load the owned onboarding state.
2. Read `consent.v1`, explicitly check the synthetic education notice, and record
   the decision. Decline by leaving it unaccepted or explicitly withdraw it.
3. Save a partial profile draft: synthetic display label and optional experience.
   Draft saves are not completion; both nullable fields are a full replacement.
4. Enter a valid label and experience, record current consent, and click Complete.
   Only a valid server-confirmed completion unlocks the S1 saved dashboard.
5. Reload/close the app: it starts signed out. Sign into the same learner to
   resume server data. Sign into the other learner to verify separate data.
6. Sign out: only confirmed server revocation (or actual 401) clears authority.
   A failed network/storage logout retains this learner/input and offers retry.

Validation, unavailable API/storage, version mismatch and timeout have visible
safe feedback; raw response text is never displayed. Failed saves preserve input
and move feedback into view. Protected navigation checks fresh server state:
another client's consent withdrawal or changed profile cannot be authorized by
a stale client completion flag. Reacceptance alone is not recompletion.

## Owned S2 risk and manual portfolios

`/risk` uses the owned `/api/v1/local-risk/*` API, not the older five-question
calculator. It shows the server's ten ordered questions and approved versions,
saves or clears partial drafts, resumes server state, and reads immutable saved
results with their original input, rule snapshot, explanation and educational
limitation. History requests contain at most two assessments per page and keep
the server's sequence order. No risk score is computed on the device.

An uncertain assessment submission retains one deep immutable set of complete
answers and one UUIDv4. Only an explicit retry sends that same input/key; there
is no automatic POST replay. Discarding a pending retry does not delete an
assessment that the server may already have saved—reload history before making
a deliberately new submission.

`/portfolio` uses `/api/v1/local-portfolios*` for owned portfolio and holding
CRUD. Names and purposes are synthetic; currency is USD. Quantity uses exact
strings with up to six decimal places and average cost uses up to four. The
typed transport confirms normalized server records without binary floats. An
uncertain create keeps input and requires a successful list reload and an
explicit reconciliation decision before another new POST, since creates are
not idempotent. PUT retries and deletion confirmations remain deliberate.

Valuation, asset/sector allocations, concentration, gain/loss and educational
spread are server-produced decimal strings, not device financial calculations.
The UI distinguishes the fixed synthetic quote snapshot time (2026-01-01 UTC)
from calculation time, and shows CACHED/UNAVAILABLE plus EMPTY/COMPLETE/INCOMPLETE/
UNAVAILABLE valuation states. Missing prices keep required overall metrics and
allocations unavailable; they do not become zero or renormalized percentages.
Zero denominators stay explicitly unavailable. These are synthetic examples,
not refreshed market prices or investment advice.

Every page holds a private, revocable typed operation scope. A logout **attempt**,
fresh onboarding check, consent/profile mutation, owner change or screen
disposal permanently invalidates prior work—even if an adapter ignores
cancellation. Old successes, errors and 401s cannot update the new learner.
Transient failed logout retains only the already-authorized same owner's dirty
form, hidden from focus, semantics and input until a successful saved-state
recheck. Old dialogs/choice menus close; confirmed logout, current 401 or
ONBOARDING_REQUIRED discards owned form state. The full application exposes no
bearer getter or authenticated adapter to screens.

## Owned S3 foundation

`/market` searches `/api/v1/local-market/instruments` and reads explicit synthetic
quotes. Prices remain server strings, unavailable prices are not zero, and
domain STALE remains visibly distinct from the envelope's CACHED provenance.
The fixed source/snapshot/fixture timestamp is not a live or refreshed market.

`/watchlist` uses owned `/api/v1/local-watchlists*` CRUD, rename and supported
item add/remove. An uncertain non-idempotent create retains its input and needs
a successful owned-list reload plus an explicit reconciliation choice before
another POST. Peer-deleted selections are removed on successful refresh while
independent unsaved create input is kept. Catalogue/quote failures do not invent
saved records or prevent independent saved-list management.

`/account` reads the simulated paper account without opening it. Only the
explicit opening button sends `/api/v1/local-paper/account/open`, once funding
USD 10000.00 simulated cash with an immutable opening entry. Repeated API
opening returns the same account; there is no amount/deposit/broker input.
`/paper-trading` and `/goals` remain visibly pending Sprint 4. AI chat, alerts
and spending are not advertised as delivered.

The S3 adapter is an optional typed capability, separate from S1/S2 injections.
Missing capability fails visibly with no singleton/demo fallback. Its private
revocable owner scopes use the same attempt-time invalidation as S2. Nothing
stores a browser/device credential or exposes a bearer getter to pages.

`test/local_s3_contract_parity_test.dart` consumes original response bytes from
`FINEX_LOCAL_S3_CORPUS` plus `FINEX_LOCAL_S3_REPORT`. Set
`FINEX_REQUIRE_LOCAL_S3_CORPUS=1` to require the exact current clean revision,
source hashes, artifact digests, all 48 native cases and completed owned-process
cleanup; missing or malformed evidence fails closed. Without optional inputs,
the test explicitly skips, never inventing a capture. Padded captured names
are confirmed by normalization; illegal captured error requests are replayed
through legal typed calls for response mapping only. This is native-wire replay,
not a new TCP execution, device run or human UAT. Story-specific validation,
actual browser/API proof and #198 full S3 acceptance remain separate gates.

Native evidence replay also requires a Git executable that supports the global
`--no-lazy-fetch` flag. Check that capability locally with
`git --no-lazy-fetch --version`; unsupported Git exits fail closed rather than
falling back to a command that could fetch missing objects. S1/S2/S3 metadata
reads disable object replacement and filesystem monitors, suppress prompts and
optional locks, and remove inherited Git/credential overrides without removing
the ordinary Windows `PATH`, `PATHEXT`, or `SystemRoot` lookup values. This is a
local capability requirement, not a claim of a particular minimum Git version
or a request to change system settings.

## Separate compatibility pilot

The earlier tested stateless onboarding/risk experience remains at
`/pilot/onboarding`, `/pilot/consent` (alias), and `/pilot/risk`. It is visibly
labelled **nonpersistent compatibility pilot**. Its device flow flags and
stateless risk-contract results cannot authorize the full application or become
saved assessment history. Its approved fixtures remain unchanged.

The pilot defaults to deterministic fixtures. To exercise only its older
stateless API contract, use the pilot routes with:

```powershell
flutter run -d chrome `
  --dart-define=FINEX_ONBOARDING_MODE=api `
  --dart-define=FINEX_RISK_MODE=api `
  --dart-define=FINEX_API_BASE_URL=http://127.0.0.1:8000
```

This pilot switch does **not** change the full application's API-only mode.
The full application calls `/api/v1/local-auth/*` and
`/api/v1/local-onboarding/*`, plus the owned S2 namespaces above, through the
frozen `local.v1` transport. The `/pilot/*` fixtures and stateless API do not
populate these owned drafts, saved history or manual portfolios.

## Quality gates and evidence limits

Use Flutter 3.47.2 (Dart 3.13). Run analysis with fatal infos, the full tests
serially, and a web build against the actual loopback API before handing off:

```powershell
flutter analyze --no-pub --fatal-infos
flutter test --no-pub --concurrency=1 --reporter=expanded
flutter build web --no-pub `
  --dart-define=FINEX_API_BASE_URL=http://127.0.0.1:8000
```

`--no-pub` is appropriate only after valid dependencies were resolved. A cached
setup is not proof of a fresh developer machine. Run one heavy build at a time,
especially on 8 GB laptops. Actual command/target results belong in the
[S1 Flutter acceptance record](../docs/evidence/s1-owned-flutter-acceptance.md).
The [S2 Flutter validation record](../docs/evidence/s2-owned-flutter-validation.md)
separately records tests-first corrections, agent review, source fingerprints,
builds and controlled API-mode proof. Browser/widget proof is not human UAT.

`test/local_s2_review_wire_test.dart` has an optional, explicit
`FINEX_S2_REVIEW_RISK_WIRE` input for a particular historical, safe captured risk
response observation. It replays original UTF-8 through public typed methods
with an in-memory synthetic credential; it does not issue network requests,
capture login/headers, alter pages to fit limit2, or certify the current client
commit as native acceptance. When no input is provided it visibly skips, with
no fixture fallback. Its historical commit/tree binding is deliberate. Formal
cross-client S2 acceptance remains a separate delivery slice.

## Windows setup note

Flutter desktop/plugin builds on Windows require the normal symlink/toolchain
prerequisites; `flutter pub get` can report a symlink failure even when cached
dependency configuration permits `--no-pub` analysis, tests and web build.
Do not hide that failure or silently change OS settings. A native Windows build
also requires Visual Studio's C++ desktop toolchain. `flutter devices` lists
available targets. Browser proof is not Android/iOS/macOS device proof; only
targets actually built/run may be claimed.
