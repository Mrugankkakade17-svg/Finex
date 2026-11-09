# S1-API-02 — FinEx v1 API Contract

## Status

**Completed**

- Branch: `nayan/s1-api-02`
- Implementation commit: `a1414b7 feat(api): implement FinEx v1 API contract`

## Objective

Implement the FinEx v1 API response and error contract with:

- Standard success and error response envelopes
- Validation error handling
- Correlation ID propagation
- Pydantic response and error models
- Contract tests

## Implemented

### Response envelope

All standardized successful responses use:

```json
{
  "data": {},
  "meta": {
    "correlationId": "...",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

Supported `dataStatus` values:

- `LIVE`
- `DELAYED`
- `END_OF_DAY`
- `CACHED`
- `UNAVAILABLE`

### Error envelope

Standardized errors use:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Safe user-readable message",
    "fieldErrors": [],
    "correlationId": "..."
  }
}
```

### Pydantic models

Added [`backend/app/schemas/envelope.py`](../../../backend/app/schemas/envelope.py), containing:

- `Meta`
- `SuccessEnvelope`
- `FieldError`
- `ErrorDetail`
- `ErrorEnvelope`

### Correlation ID middleware

Added [`backend/app/core/middleware.py`](../../../backend/app/core/middleware.py).

It:

- Generates a UUID if `X-Correlation-ID` is not supplied.
- Preserves an incoming `X-Correlation-ID`.
- Stores the ID in `request.state.correlation_id`.
- Returns the ID in the response header.

### Exception handling

Updated [`backend/app/core/handlers.py`](../../../backend/app/core/handlers.py) with standardized handling for:

- `FinExException`
- `RequestValidationError`

Validation errors return HTTP 422 with stable field-level error codes.

### API response helper

Updated [`backend/app/core/responses.py`](../../../backend/app/core/responses.py). `APIResponse.success()` and `APIResponse.error()` return FinEx v1 envelopes.

### Application integration

Updated [`backend/app/main.py`](../../../backend/app/main.py) to register:

- `CorrelationIdMiddleware`
- The `FinExException` handler
- The `RequestValidationError` handler

### Existing routers

Updated these routers and their tests to follow the standardized envelope:

- `auth`
- `demo`
- `health`
- `users`

### Tests

Added [`backend/tests/test_api_contract.py`](../../../backend/tests/test_api_contract.py). Contract tests cover:

- HTTP 200 success envelope
- HTTP 400 error envelope
- HTTP 422 validation envelope
- HTTP 500 error envelope
- Generated correlation ID
- Preserved correlation ID

Existing tests were updated for the new response format.

## Verification

Final test run:

```text
80 passed
0 failed
72.19% coverage
```

Required coverage: **70%**.

Also verified:

```text
git diff --check
Result: clean
```

## Manual verification

### 400 error

`GET /api/v1/demo/error`

Verified:

- HTTP 400
- `DEMO_ERROR`
- Correlation ID in the response body and header

### 500 error

`GET /api/v1/demo/error500`

Verified:

- HTTP 500
- `INTERNAL_SERVER_ERROR`
- Safe error message
- Correlation ID in the response body and header

### 422 validation error

An invalid registration request returns:

- HTTP 422
- `VALIDATION_ERROR`
- Field-level validation errors
- Correlation ID in the response body and header

### Correlation ID propagation

An incoming header such as:

```http
X-Correlation-ID: finex-test-123
```

is preserved in both the response body and response header.

## Files changed

### Added

- `backend/app/core/middleware.py`
- `backend/app/schemas/envelope.py`
- `backend/tests/test_api_contract.py`

### Updated

- `backend/app/core/handlers.py`
- `backend/app/core/responses.py`
- `backend/app/main.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/demo.py`
- `backend/app/routers/health.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_auth_flow.py`
- `backend/tests/test_demo.py`
- `backend/tests/test_health.py`
- `backend/tests/test_users_router.py`

## API contract

The authoritative API contract is [`docs/api-standard-v1.md`](../../api-standard-v1.md). The implementation follows its success, error, validation, correlation ID, API version, and data-freshness conventions.

## Acceptance criteria

| Requirement | Status |
| --- | --- |
| Standardized HTTP 200 response | Complete |
| Standardized HTTP 422 validation response | Complete |
| Standardized HTTP 500 error response | Complete |
| Correlation ID in responses | Complete |
| Correlation ID propagation | Complete |
| Pydantic response/error models | Complete |
| Correlation middleware | Complete |
| Contract tests | Complete |
| Existing tests passing | Complete |
| Coverage >= 70% | Complete |

## Final status

S1-API-02 implementation complete.

Final verification: **80 passed · 0 failed · 72.19% coverage**.
