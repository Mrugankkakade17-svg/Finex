"""Small, process-local sliding-window limiter for API ingress."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.responses import APIResponse


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Result of admitting one request to a sliding time window."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Thread-safe process-local request limiter with periodic stale-key cleanup."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._next_cleanup = 0.0

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: float,
        now: float | None = None,
    ) -> RateLimitDecision:
        """Consume one slot for ``key`` or return how long until the next slot."""
        if not key:
            raise ValueError("rate-limit key must not be empty")
        if isinstance(limit, bool) or limit < 1:
            raise ValueError("rate-limit limit must be at least 1")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("rate-limit window must be a positive finite number")

        current = self._clock() if now is None else now
        if not math.isfinite(current):
            raise ValueError("rate-limit time must be finite")
        cutoff = current - window_seconds
        with self._lock:
            if current >= self._next_cleanup:
                for stale_key, events in tuple(self._events.items()):
                    while events and events[0] <= cutoff:
                        events.popleft()
                    if not events:
                        self._events.pop(stale_key, None)
                self._next_cleanup = current + min(window_seconds, 60.0)

            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (current - events[0])))
                return RateLimitDecision(False, limit, 0, retry_after)

            events.append(current)
            return RateLimitDecision(True, limit, limit - len(events), 0)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply configured per-client limits to versioned API requests."""

    def __init__(
        self,
        app,
        *,
        requests_per_window: int = 1000,
        window_seconds: float = 60.0,
        auth_requests_per_window: int = 100,
        auth_window_seconds: float = 60.0,
        limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.auth_requests_per_window = auth_requests_per_window
        self.auth_window_seconds = auth_window_seconds
        self.limiter = limiter or SlidingWindowRateLimiter()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1/") or path.startswith("/api/v1/health"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        is_authentication = path.startswith("/api/v1/auth/")
        if is_authentication:
            limit = self.auth_requests_per_window
            window_seconds = self.auth_window_seconds
            key = f"auth:{client_host}"
        else:
            limit = self.requests_per_window
            window_seconds = self.window_seconds
            key = f"api:{client_host}"

        decision = self.limiter.check(
            key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not decision.allowed:
            response = APIResponse.error(
                message="Too many requests. Please retry after the rate limit window.",
                error_code="RATE_LIMIT_EXCEEDED",
                status_code=429,
                correlation_id=getattr(request.state, "correlation_id", "unknown"),
            )
            response.headers["Retry-After"] = str(decision.retry_after_seconds)
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        return response
