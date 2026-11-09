# FinEx API Standard v1

## 1. Purpose

This document defines the standard API response and error conventions for FinEx v1 APIs.

All FinEx API endpoints must follow these conventions. Frontend clients (React and Flutter) should rely on these structures rather than endpoint-specific response formats.

---

## 2. Success Response

All successful `2xx` responses use the following envelope:

```json
{
  "data": {},
  "meta": {
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

### 2.1 Fields

| Field | Type | Description |
| --- | --- | --- |
| `data` | object, array, or scalar | Endpoint-specific response data. |
| `meta.correlationId` | string | Unique identifier used to trace the request. |
| `meta.apiVersion` | string | API version that served the response. |
| `meta.dataAsOf` | string or null | ISO 8601 timestamp indicating when the underlying data was accurate. |
| `meta.dataStatus` | enum | Freshness or status of the underlying data. |

### 2.2 Data Status

Allowed values:

- `LIVE`
- `DELAYED`
- `END_OF_DAY`
- `CACHED`
- `UNAVAILABLE`

## 3. Error Response

All `4xx` and `5xx` responses use the following envelope:

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "Safe user-readable message",
    "fieldErrors": [],
    "correlationId": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

### 3.1 Error Fields

| Field | Type | Description |
| --- | --- | --- |
| `error.code` | string | Stable machine-readable error code. |
| `error.message` | string | Safe, user-readable message. |
| `error.fieldErrors` | array | Field-level validation errors, when applicable. |
| `error.correlationId` | string | Identifier used to trace the request. |

### 3.2 Field Error

Each field-level validation error uses:

```json
{
  "field": "quantity",
  "code": "MUST_BE_POSITIVE"
}
```

The `code` must be a stable machine-readable value.

## 4. Validation Errors

Validation failures use HTTP `422`.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "fieldErrors": [
      {
        "field": "email",
        "code": "INVALID_FORMAT"
      }
    ],
    "correlationId": "550e8400-e29b-41d4-a716-446655440002"
  }
}
```

Validation errors must not expose internal implementation details.

## 5. Pagination

Paginated endpoints must use a consistent pagination convention across FinEx APIs.

Pagination request and response fields must be defined in the endpoint-specific OpenAPI contract before implementation. Pagination must be deterministic so that clients can reliably navigate result sets.

## 6. Correlation ID

Every API request must have a correlation ID. It is used to trace a request across application processing and logs.

For successful responses, the correlation ID is returned in `meta.correlationId`. For error responses, it is returned in `error.correlationId`.

```json
{
  "data": {},
  "meta": {
    "correlationId": "550e8400-e29b-41d4-a716-446655440003",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

## 7. API Version

The current API version is `v1`. It is exposed through response metadata:

```json
{
  "apiVersion": "v1"
}
```

## 8. Data Freshness

Responses containing time-sensitive or externally sourced data must provide freshness metadata.

`dataAsOf` represents the time at which the underlying data was accurate. It is not necessarily the time at which the API response was generated.

```json
{
  "data": {},
  "meta": {
    "correlationId": "550e8400-e29b-41d4-a716-446655440004",
    "apiVersion": "v1",
    "dataAsOf": "2026-08-11T15:30:00Z",
    "dataStatus": "DELAYED"
  }
}
```

Allowed `dataStatus` values are `LIVE`, `DELAYED`, `END_OF_DAY`, `CACHED`, and `UNAVAILABLE`.

## 9. OpenAPI Examples

The API specification must provide examples for:

- Successful HTTP `200` response.
- Validation HTTP `422` response.
- Internal server HTTP `500` response.
- Correlation ID.
- Error responses.
- Paginated responses, where applicable.

Examples are part of the API contract and must remain consistent with the implemented response schemas.

## 10. Example Responses

### 10.1 Successful Response - HTTP 200

```json
{
  "data": {
    "id": "user-123",
    "name": "Example User"
  },
  "meta": {
    "correlationId": "550e8400-e29b-41d4-a716-446655440005",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

### 10.2 Validation Error - HTTP 422

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "fieldErrors": [
      {
        "field": "email",
        "code": "INVALID_FORMAT"
      }
    ],
    "correlationId": "550e8400-e29b-41d4-a716-446655440006"
  }
}
```

### 10.3 Internal Server Error - HTTP 500

```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred.",
    "fieldErrors": [],
    "correlationId": "550e8400-e29b-41d4-a716-446655440007"
  }
}
```

### 10.4 Correlation ID

Every API response must include a correlation ID.

Successful response:

```json
{
  "data": {},
  "meta": {
    "correlationId": "550e8400-e29b-41d4-a716-446655440008",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

Error response:

```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred.",
    "fieldErrors": [],
    "correlationId": "550e8400-e29b-41d4-a716-446655440009"
  }
}
```

## 11. Architecture Requirements

API implementations must follow this layering:

`Router -> Service -> Repository/Port`

Business logic must remain outside routers. Domain services must use approved provider adapters and ports rather than direct vendor SDK dependencies.

API implementations must include the required unit, contract, and integration tests. Authorization must be enforced for protected resources.

## 12. Implementation Notes

This document defines the API v1 contract.

The following implementation artifacts are required for `S1-API-02`:

- Pydantic response and error models.
- Correlation middleware.
- Unit tests.
- Contract and integration tests, as required.

The middleware will be registered through the FastAPI application factory created by `S1-API-01`.

While `S1-API-01` is blocked, this document and its example JSON provide the draft API contract for review.

## 13. Acceptance Criteria

`S1-API-02` is complete when a sample endpoint demonstrates:

- Standardized HTTP `200` response.
- Standardized HTTP `422` validation response.
- Standardized HTTP `500` error response.
- Correlation ID in the response.
- API schema approved by the React and Flutter reviewers.

Reviewers: Palak, Khyati, Shivraj