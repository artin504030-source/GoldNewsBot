"""Runtime health checks that never expose credentials."""
from __future__ import annotations

from app.core.config import Settings
from goldnewsbot.storage import SQLiteNewsRepository


def health_report(settings: Settings | None = None) -> dict:
    settings = settings or Settings.from_env()
    checks = {"configuration": "ok", "database": "not_checked", "telegram_configured": settings.telegram_ready}
    status = "ok"
    try:
        SQLiteNewsRepository(settings.database_path).check()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        status = "degraded"
    return {
        "status": status,
        "environment": settings.app_env,
        "checks": checks,
        "secrets_exposed": False,
    }
