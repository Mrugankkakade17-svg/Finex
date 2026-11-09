# FinEx

FinEx is a financial education and decision-support application with a FastAPI
backend, React web client, and Flutter desktop/mobile client.

## Local development

FinEx is designed to run natively on developer machines. Docker is not required
for local development or tests.

1. Install Python 3.13, Node.js 24 LTS, and Flutter 3.47.2.
2. From PowerShell at the repository root, bootstrap only the component you need:

```powershell
.\scripts\bootstrap.ps1 -Component Backend
.\scripts\bootstrap.ps1 -Component React
.\scripts\bootstrap.ps1 -Component Flutter
```

3. Start the backend with the repository-aware helper:

```powershell
.\scripts\run-backend.ps1 -Reload
```

The full setup, test, and troubleshooting guide is in
[docs/local-development.md](docs/local-development.md).

The reproducible Sprint 1 consent-and-profile technical-UAT package, including
the acceptance matrix, visual state diagrams, limits, and evidence commands,
is in [docs/evidence/s1-uat-01-onboarding-pilot.md](docs/evidence/s1-uat-01-onboarding-pilot.md).

The Sprint 2 local acceptance record, complete consent-to-risk walkthrough,
exact native commands, and remaining release gates are in
[docs/evidence/s2-local-acceptance.md](docs/evidence/s2-local-acceptance.md).

Those records describe the stateless local pilot, not full S1/S2 delivery.
The approved full-product S1–S4 gap plan, requirement/card mapping, dependency
diagrams, native persistence/session contract and honest acceptance ledger are in
[the local application delivery supplement](docs/features/local-application/S1-S4-delivery-contract.md).
Track the new work in [delivery issue #184](https://github.com/IgnAite-Showcase/Finex/issues/184).

S1's owned local journey is accepted on W40. The next saved-risk API slice has
an explicit [S2 contract](docs/features/local-application/S2-saved-risk-contract.md),
[data dictionary](docs/features/local-application/local-data-dictionary.md) and
[acceptance record](docs/evidence/s2-saved-risk-api-acceptance.md).
Use the [native application runbook](docs/runbooks/native-local-application.md)
for isolated setup and evidence commands. Saved-risk API acceptance alone does
not mean the S2 portfolios or both clients are finished.

## Toolchain contract

| Component | Required version | Version file |
| --- | --- | --- |
| Backend | Python 3.13 | `.python-version` |
| React web | Node.js 24.20.0 LTS | `.nvmrc` |
| Flutter | Flutter 3.47.2 / Dart 3.13 | `frontend_flutter/.flutter-version` |

Run the relevant quality commands before opening a pull request. GitHub Actions
enforces backend, React, and Flutter checks independently.
