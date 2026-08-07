"""
Presentation Middleware — Security and request tracking.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Injects a unique request ID into each request and response."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting to prevent abuse."""

    def __init__(self, app: FastAPI, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict = {}

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old entries for this client
        if client_ip in self._clients:
            self._clients[client_ip] = [
                t for t in self._clients[client_ip] 
                if t > now - self.window_seconds
            ]
        else:
            self._clients[client_ip] = []
            
        requests = self._clients[client_ip]
        requests.append(now)
        
        if len(requests) > self.max_requests:
            return Response("Rate limit exceeded", status_code=429)
            
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:;"
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all custom middleware on the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=300, window_seconds=60)
    app.add_middleware(RequestIdMiddleware)
