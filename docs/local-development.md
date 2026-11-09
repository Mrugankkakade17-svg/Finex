# FinEx local development

## Operating model

FinEx runs as native processes on a developer workstation. Do not use Docker for
local development: it adds unnecessary memory pressure for the 8 GB laptops used
by the team. Start only the component you are changing.

For the least friction on Windows, clone the repository to a local development
folder such as `C:\src\Finex` rather than a synchronized OneDrive folder. This
avoids file-lock and line-ending noise from generated Flutter files.

## Required tools

| Component | Required toolchain | Why |
| --- | --- | --- |
| API | Python 3.13 | Matches the backend quality workflow. |
| Web | Node.js 24.20.0 LTS and npm | Matches `.nvmrc` and the React workflow. |
| Flutter | Flutter 3.47.2 with Dart 3.13 | Matches the SDK constraint and Flutter workflow. |
| Windows client | Visual Studio with Desktop development with C++ | Required only for `flutter build windows` or `flutter run -d windows`. |

The bootstrap script checks these versions. It does not install system software
or access cloud credentials.

## First-time setup

Open PowerShell at the repository root. If PowerShell blocks local scripts for
this terminal only, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Bootstrap one component at a time to conserve memory:

```powershell
.\scripts\bootstrap.ps1 -Component Backend
.\scripts\bootstrap.ps1 -Component React
.\scripts\bootstrap.ps1 -Component Flutter
```

Use `-CheckOnly` to validate installed toolchains without downloading packages:

```powershell
.\scripts\bootstrap.ps1 -Component Backend -CheckOnly
```

## Run locally

### Backend API

Start the backend from the repository root:

```powershell
.\scripts\run-backend.ps1 -Reload
```

The helper keeps the repository root on the Python import path and starts
Uvicorn with `backend` as the app directory. Do not run `uvicorn app.main:app`
from inside `backend`; that command cannot resolve the repository-level `ai`
package.

Confirm the API is live:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

The health endpoint and unit tests work without Databricks or production
secrets. If a task uses an external provider, keep its values in `backend/.env`
and never commit that file.

### React web client

```powershell
Push-Location .\frontend-react
npm start
```

Use a second terminal for the API when the feature needs it.

### Flutter client

```powershell
Push-Location .\frontend_flutter
flutter run -d windows
```

For low-memory development, run widget tests or analysis instead of keeping the
desktop client and the web client open at the same time.

## Verification commands

Run only the checks for the component you changed.

```powershell
# Backend
Push-Location .\backend
.\.venv\Scripts\python.exe -m ruff check . --no-cache
.\.venv\Scripts\python.exe -m ruff format --check . --no-cache
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m app.fixtures.s1_dat_01 --format json
.\.venv\Scripts\python.exe .\verify_r0_thin_slice.py --format json

# React
Push-Location .\frontend-react
npm test -- --watchAll=false
npm run build

# Flutter
Push-Location .\frontend_flutter
flutter analyze --fatal-infos
flutter test
flutter build windows --debug
```

## Pull-request expectations

Every feature branch must be small enough to test locally and must include the
relevant automated tests. Do not commit `.env`, virtual environments,
`node_modules`, Flutter build output, or generated local tool caches.

If a feature depends on another unfinished feature, record that dependency in
its GitHub issue before coding; do not silently merge an incomplete dependency
into a release candidate.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `Python 3.13 was not found` | Install Python 3.13 and ensure the Python Launcher (`py`) is available, then rerun bootstrap. |
| Flutter rejects the Dart SDK | Run Flutter 3.47.2; the project requires Dart 3.13 or newer. |
| Windows build cannot find `runner.exe.manifest` | Pull the latest branch; the required manifest is version-controlled. |
| Generated Flutter files appear modified without meaningful content changes | Pull the latest `.gitattributes`, then reclone or refresh the working tree instead of committing the files. |
| API fails to import `ai` | Use `scripts/run-backend.ps1` from the repository root. |
