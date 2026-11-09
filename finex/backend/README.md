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
.\scripts\run-backend.ps1 -Reload
```

The helper keeps the repository root available to Python, uses `backend` as the
application directory, and watches only the Python source directories during
reload. It is the supported command for Windows development machines; Docker
is not required.

Confirm that it is running:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

The health endpoint and tests work without Databricks or production secrets.
If your task uses an external provider, put its local values in `backend/.env`
and never commit that file. See [the full local-development guide](../docs/local-development.md)
for React, Flutter, verification commands, and troubleshooting.

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
