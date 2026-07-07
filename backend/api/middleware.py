"""
Vigilant API Middleware — Security headers, rate limiting, and request tracing.
"""

import time
import uuid
import logging
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("vigilant.middleware")

# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject enterprise security headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        # HSTS only on non-localhost
        if request.url.hostname not in ("localhost", "127.0.0.1"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID for audit tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Simple Rate Limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic in-memory rate limiter.

    - Read endpoints (GET):  200 requests / minute
    - Write endpoints (POST/PUT/DELETE): 30 requests / minute
    """

    def __init__(self, app, read_limit: int = 200, write_limit: int = 30,
                 window_seconds: int = 60):
        super().__init__(app)
        self.read_limit = read_limit
        self.write_limit = write_limit
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static assets
        path = request.url.path
        if path in ("/api/health", "/") or not path.startswith("/api"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        method = request.method.upper()
        is_write = method in ("POST", "PUT", "DELETE", "PATCH")
        limit = self.write_limit if is_write else self.read_limit

        bucket_key = f"{client_ip}:{'w' if is_write else 'r'}"
        now = time.time()

        # Prune expired entries
        timestamps = self._buckets[bucket_key]
        cutoff = now - self.window
        self._buckets[bucket_key] = [t for t in timestamps if t > cutoff]
        timestamps = self._buckets[bucket_key]

        if len(timestamps) >= limit:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Periodic cleanup of stale buckets (every ~1000 requests)
        if len(self._buckets) > 5000:
            stale_keys = [
                k for k, v in self._buckets.items()
                if not v or v[-1] < cutoff
            ]
            for k in stale_keys:
                del self._buckets[k]

        timestamps.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, limit - len(timestamps))
        )
        return response



def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI application in correct order."""
    # Order matters: outermost middleware executes first
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware)
