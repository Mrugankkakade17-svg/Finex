# FinEx Coding Standards

## Must Follow

- **SOLID Principles** — Single responsibility, open/closed, etc.
- **Clean Architecture** — Router → Service → Repository → Database
- **Type Hints** — All function parameters and return types must be typed
- **Docstrings** — All classes and public functions must have docstrings
- **Dependency Injection** — Use FastAPI `Depends()` for shared dependencies
- **No hardcoded secrets** — All secrets in `.env`, accessed via Settings
- **Configuration from `.env`** — Use `pydantic-settings` BaseSettings
- **Logging using project logger** — Use `from app.config.logging import logger`
- **Standard APIResponse format** — All endpoints return `APIResponse.success()` or raise exceptions
- **Standard FinExException handling** — All errors use `FinExException` subclasses

## API Documentation (Swagger)

Every endpoint must include:
- Description
- Summary
- Response Models
- Status Codes
- Example Requests
- Example Responses

## File Organization

```
Router    → Only HTTP handling. No business logic.
Service   → Business logic. Pure Python. No FastAPI imports.
Repository → Database access only. Interface for data layer.
Model     → Internal Python models (Pydantic BaseModel).
Schema    → API Request and Response validation.
```
