from __future__ import annotations

from fastapi import FastAPI

from .api.v1.routes_auth import router as auth_router
from .api.v1.routes_health import router as health_router
from .api.v1.routes_history import router as history_router
from .api.v1.routes_tasks import router as tasks_router
from .api.v1.ws import router as ws_router
from .config import get_settings
from .logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    configure_logging(env=settings.app_env)

    app = FastAPI(
        title="Visa Docs Analysis API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(ws_router, prefix="/api/v1")

    return app


app = create_app()
