"""FastAPI middleware that writes every API call to compliance_audit_log."""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from shared.db import async_session_factory
from sqlalchemy import text


class ComplianceAuditMiddleware(BaseHTTPMiddleware):
    """Writes audit log row for every non-health-check request."""

    SKIP_PATHS = {"/health", "/metrics", "/favicon.ico", "/docs", "/openapi.json"}

    def __init__(self, app: ASGIApp, service_name: str = "dashboard") -> None:
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        user_id = request.headers.get("X-User-Id", "anonymous")
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))

        try:
            async with async_session_factory() as session:
                await session.execute(
                    text("""
                        INSERT INTO compliance_audit_log
                            (id, service, user_id, method, path, status_code,
                             duration_ms, correlation_id, created_at)
                        VALUES
                            (:id, :service, :user_id, :method, :path, :status_code,
                             :duration_ms, :correlation_id, NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "service": self.service_name,
                        "user_id": user_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "correlation_id": correlation_id,
                    },
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            pass  # never let audit failure break the request

        return response
