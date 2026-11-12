"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.config import get_settings
from app.db import check_connection


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Moo-ternity Watch Backend",
        version=__version__,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        """Liveness + readiness probe.

        Always returns 200 for liveness; ``database`` reports whether the DB
        connectivity probe currently succeeds.
        """
        try:
            db_ok = check_connection()
        except Exception:  # noqa: BLE001 - report any failure as not-ready
            db_ok = False

        return {
            "status": "ok",
            "version": __version__,
            "environment": settings.environment.value,
            "database": "ok" if db_ok else "unavailable",
        }

    return app


app = create_app()
