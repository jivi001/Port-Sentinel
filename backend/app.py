"""
Application Factory — Assembles the FastAPI application and DI container.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.container import Container
from backend.infrastructure.config.settings import load_settings
from backend.infrastructure.network.dispatcher import Dispatcher
from backend.presentation.middleware.security import register_middleware
from backend.presentation.websocket.handlers import sio
from backend.application.events.handlers import EventHandlers

logger = logging.getLogger("vigilant.app")


def _find_frontend_dist() -> str | None:
    """Locate the built React frontend dist folder."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "frontend_dist"
        if bundled.is_dir():
            return str(bundled)
    project_root = Path(__file__).resolve().parent.parent
    dev_dist = project_root / "frontend" / "dist"
    if dev_dist.is_dir():
        return str(dev_dist)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    container: Container = app.state.container
    settings = container.settings

    logger.info("Starting %s v%s...", settings.product_full_name, settings.version)

    # 1. Wire Infrastructure
    container.wire_os_bridge()
    container.wire_threat_service()
    container.wire_influx()
    container.wire_sniffer()

    # 2. Register Events & Jobs
    event_handlers = EventHandlers(container)
    event_handlers.register_all()
    container.register_background_jobs()

    # 3. Start Background Services
    container.job_scheduler.start()
    container.plugin_registry.discover()
    container.plugin_registry.start_all()
    if container.sniffer_process:
        container.sniffer_process.start()

    # 4. Start Network Dispatcher
    dispatcher = Dispatcher(container)
    dispatcher.start()

    logger.info("%s initialized successfully.", settings.product_full_name)

    yield

    # Shutdown
    dispatcher.stop()
    container.shutdown()


def create_app() -> socketio.ASGIApp:
    """Create and configure the FastAPI application and DI container."""
    settings = load_settings()
    container = Container(settings)

    app = FastAPI(
        title=settings.product_full_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # Attach container to app state for dependency injection
    app.state.container = container

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    )

    # Security & Rate Limiting
    register_middleware(app)

    # Routers
    from backend.presentation.api.approvals import router as approvals_router
    from backend.presentation.api.control import router as control_router
    from backend.presentation.api.ports import router as ports_router
    from backend.presentation.api.system import router as system_router

    app.include_router(ports_router)
    app.include_router(control_router)
    app.include_router(approvals_router)
    app.include_router(system_router)

    # Static Frontend Serving
    frontend_path = _find_frontend_dist()
    if frontend_path:
        @app.get("/")
        async def serve_spa_root() -> FileResponse:
            return FileResponse(os.path.join(frontend_path, "index.html"))

        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(frontend_path, "assets")),
            name="static-assets",
        )

        @app.get("/{full_path:path}")
        async def serve_spa_fallback(full_path: str) -> FileResponse:
            file_path = os.path.join(frontend_path, full_path)
            resolved = os.path.realpath(file_path)
            safe_root = os.path.realpath(frontend_path)
            if resolved.startswith(safe_root) and os.path.isfile(resolved):
                return FileResponse(resolved)
            return FileResponse(os.path.join(frontend_path, "index.html"))

        logger.info("Frontend static files mounted from: %s", frontend_path)
    else:
        logger.warning("Frontend dist not found — API-only mode")

    # Wrap FastAPI with Socket.IO ASGIApp
    return socketio.ASGIApp(sio, other_asgi_app=app)
