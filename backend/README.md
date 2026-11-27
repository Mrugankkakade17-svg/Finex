# Finex Backend

FastAPI backend for the Finex application.

## Local development

Run the backend commands from the **repository root**, not from this `backend`
folder. FinEx has a repository-level `ai` package as well as the FastAPI
application, so starting Uvicorn directly from `backend` will not load every
project module.

1. Bootstrap the Python environment:

```powershell
.\scripts\bootstrap.ps1 -Component Backend
```

2. Start the API with the repository-aware helper:

```powershell
.\scripts\run-backend.ps1 -EnableLocalApplication -Reload
```

The helper keeps the repository root available to Python, uses `backend` as the
application directory, and watches only the Python source directories during
reload. `-EnableLocalApplication` sets `APP_ENV=local` and opts this
loopback-only run into the synthetic local persona API. It is the supported
command for Windows development machines; Docker is not required.

Confirm that it is running:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

The health endpoint and tests work without Databricks or production secrets.
If your task uses an external provider, put its local values in `backend/.env`
and never commit that file. See [the full local-development guide](../docs/local-development.md)
for React, Flutter, verification commands, and troubleshooting.

## Production configuration and request controls

UAT and production startup require a non-placeholder `SECRET_KEY` with at least
32 characters, explicit HTTPS `API_BASE_URL`, and explicit non-wildcard
`ALLOWED_ORIGINS`. `OPENAI_API_KEY` is required when
`LLM_PROVIDER=openai`; `MARKET_DATA_API_KEY` is required when the selected
market provider is Alpha Vantage or Polygon. PostgreSQL deployments must set
`APP_PERSISTENCE=postgresql` and `APP_DATABASE_URL` (or `DATABASE_URL`). The
settings validator rejects missing or unsafe required values before the app
starts.

The API applies a process-local sliding-window limit to versioned API requests:
1000 requests per client per 60 seconds by default, with a stricter 100 per 60
seconds for authentication routes. Adjust `RATE_LIMIT_REQUESTS_PER_WINDOW`,
`RATE_LIMIT_WINDOW_SECONDS`, `AUTH_RATE_LIMIT_REQUESTS_PER_WINDOW`, and
`AUTH_RATE_LIMIT_WINDOW_SECONDS` for the deployment. The health endpoints are
exempt so service probes continue to work during traffic bursts. Authentication
attempt throttling also retains the existing persistent login tracker.

`app.services.audit_service.write_audit_event` writes one allowlisted JSON
record to the `finex.audit` application logger. Include the request's
`correlation_id`; the event deliberately has no arbitrary metadata or request
body field, so credentials and financial payloads are not copied into audit
logs. Production deployments should collect and retain this append-only log
stream in their configured log sink.

## Project Structure

```text
backend/
├── app/
│   ├── auth/            # Authentication & authorization
│   ├── config/          # Application configuration
│   ├── core/            # Shared utilities and common components
│   ├── exceptions/      # Custom exceptions and exception handlers
│   ├── models/          # Database models
│   ├── ports/           # Application interfaces (Protocols)
│   ├── repositories/    # Data access layer
│   ├── routers/         # API route handlers
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   ├── __init__.py
│   └── main.py          # FastAPI application entry point
├── docs/                # Backend documentation
├── tests/               # Backend test suite
├── .env.example         # Example environment variables
├── .gitignore           # Git ignore rules
├── .gitkeep             # Preserve empty directories
├── README.md            # Backend documentation
└── requirements.txt     # Python dependencies
```
