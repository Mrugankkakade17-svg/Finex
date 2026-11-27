"""S2-LI01 audit logging, API rate limits, and production secret checks."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.core.exceptions import ConfigurationError
from app.core.middleware import CorrelationIdMiddleware
from app.core.rate_limit import RateLimitMiddleware, SlidingWindowRateLimiter
from app.core.responses import APIResponse
from app.services.audit_service import write_audit_event


def test_sliding_window_admits_exact_limit_then_resets_at_boundary() -> None:
    limiter = SlidingWindowRateLimiter(clock=lambda: 0.0)

    first = limiter.check("client", limit=2, window_seconds=10, now=1.0)
    second = limiter.check("client", limit=2, window_seconds=10, now=2.0)
    blocked = limiter.check("client", limit=2, window_seconds=10, now=3.0)
    after_window = limiter.check("client", limit=2, window_seconds=10, now=12.0)

    assert (first.allowed, first.remaining) == (True, 1)
    assert (second.allowed, second.remaining) == (True, 0)
    assert (blocked.allowed, blocked.retry_after_seconds) == (False, 8)
    assert (after_window.allowed, after_window.remaining) == (True, 1)


def test_sliding_window_isolates_keys_and_rejects_invalid_limits() -> None:
    limiter = SlidingWindowRateLimiter(clock=lambda: 1.0)

    assert limiter.check("client-a", limit=1, window_seconds=5).allowed
    assert limiter.check("client-b", limit=1, window_seconds=5).allowed
    assert not limiter.check("client-a", limit=1, window_seconds=5).allowed
    with pytest.raises(ValueError, match="key"):
        limiter.check("", limit=1, window_seconds=5)
    with pytest.raises(ValueError, match="at least 1"):
        limiter.check("client", limit=0, window_seconds=5)
    with pytest.raises(ValueError, match="positive finite"):
        limiter.check("client", limit=1, window_seconds=float("inf"))
    with pytest.raises(ValueError, match="finite"):
        limiter.check("client", limit=1, window_seconds=5, now=float("nan"))


def test_sliding_window_admission_is_atomic_under_concurrent_requests() -> None:
    limiter = SlidingWindowRateLimiter(clock=lambda: 1.0)
    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(
            pool.map(
                lambda _: limiter.check("shared-client", limit=5, window_seconds=60),
                range(64),
            )
        )

    assert sum(decision.allowed for decision in decisions) == 5


def test_api_rate_limit_preserves_error_envelope_and_health_availability() -> None:
    app = _rate_limited_app(
        requests_per_window=1,
        window_seconds=30,
    )
    with TestClient(app) as client:
        healthy = client.get("/api/v1/health")
        first = client.get("/api/v1/capabilities", headers={"X-Correlation-ID": "limit-test"})
        limited = client.get("/api/v1/capabilities", headers={"X-Correlation-ID": "limit-test-2"})

    assert healthy.status_code == 200
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "30"
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert limited.json()["error"]["correlationId"] == "limit-test-2"
    assert limited.headers["X-Correlation-ID"] == "limit-test-2"


def test_auth_routes_use_the_stricter_limit() -> None:
    app = _rate_limited_app(
        requests_per_window=100,
        auth_requests_per_window=1,
    )
    with TestClient(app) as client:
        first = client.post("/api/v1/auth/login")
        limited = client.post("/api/v1/auth/login")

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def _rate_limited_app(
    *,
    requests_per_window: int,
    window_seconds: float = 60,
    auth_requests_per_window: int = 10,
) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/capabilities")
    async def capabilities(request: Request):
        return APIResponse.success(correlation_id=request.state.correlation_id)

    @app.get("/api/v1/health")
    async def health(request: Request):
        return APIResponse.success(correlation_id=request.state.correlation_id)

    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        return APIResponse.success(correlation_id=request.state.correlation_id)

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_window=requests_per_window,
        window_seconds=window_seconds,
        auth_requests_per_window=auth_requests_per_window,
        auth_window_seconds=window_seconds,
    )
    app.add_middleware(CorrelationIdMiddleware)
    return app


def test_audit_writer_emits_allowlisted_append_only_json(caplog: pytest.LogCaptureFixture) -> None:
    happened_at = datetime(2026, 11, 27, 10, 30, tzinfo=timezone.utc)
    audit_logger = logging.getLogger("test.finex.audit")

    with caplog.at_level("INFO", logger="test.finex.audit"):
        event = write_audit_event(
            event_type="paper_order.created",
            outcome="success",
            correlation_id="request-123",
            actor_id="user-456",
            resource_type="paper_order",
            resource_id="order-789",
            occurred_at=happened_at,
            logger=audit_logger,
        )

    records = [record for record in caplog.records if record.name == "test.finex.audit"]
    assert len(records) == 1
    logged = json.loads(records[0].getMessage().removeprefix("audit_event="))
    assert logged == event.to_dict()
    assert logged["correlation_id"] == "request-123"
    assert logged["occurred_at"] == happened_at.isoformat()
    assert "password" not in logged


@pytest.mark.parametrize(
    "values, message",
    [
        ({"event_type": "Unsafe Event"}, "event_type"),
        ({"correlation_id": "bad\nrequest"}, "correlation_id"),
        ({"occurred_at": datetime(2026, 1, 1)}, "timezone-aware"),
        ({"actor_id": "user\nforged"}, "actor_id"),
    ],
)
def test_audit_writer_rejects_invalid_event_metadata(values: dict, message: str) -> None:
    arguments = {"event_type": "account.login", "correlation_id": "request-1"}
    arguments.update(values)
    with pytest.raises(ValueError, match=message):
        write_audit_event(**arguments)


def test_production_startup_requires_a_real_signing_secret() -> None:
    with pytest.raises(ConfigurationError, match="SECRET_KEY must be explicitly configured"):
        Settings(
            _env_file=None,
            app_env="prod",
            debug=False,
            api_base_url="https://api.finex.example",
            allowed_origins=["https://app.finex.example"],
            llm_provider="none",
            secret_key="",
        )


def test_production_startup_requires_enabled_provider_secrets() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY is required"):
        Settings(
            _env_file=None,
            app_env="prod",
            debug=False,
            api_base_url="https://api.finex.example",
            allowed_origins=["https://app.finex.example"],
            secret_key="a" * 48,
            llm_provider="openai",
            openai_api_key="",
        )

    with pytest.raises(ConfigurationError, match="MARKET_DATA_API_KEY is required"):
        Settings(
            _env_file=None,
            app_env="prod",
            debug=False,
            api_base_url="https://api.finex.example",
            allowed_origins=["https://app.finex.example"],
            secret_key="a" * 48,
            llm_provider="none",
            market_data_provider="polygon",
            market_data_api_key="",
        )
