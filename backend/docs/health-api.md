# Health API

## Purpose

The Health API is used to verify that the FinEx backend is running correctly.

It is commonly used by:

- React Web Application
- Flutter Mobile Application
- DevOps Monitoring
- Load Balancers
- CI/CD Pipelines

---

## Endpoint

GET /api/v1/health

---

## Sample Response

```json
{
  "status": "healthy",
  "service": "FinEx Backend",
  "version": "0.1.0",
  "environment": "development"
}
```

---

## Status Code

200 OK

---

## Notes

This endpoint does not require authentication because it is intended for health monitoring.
