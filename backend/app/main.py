import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .config import settings
from .db import SessionLocal, engine
from .routers import auth, feedback, public, requirements
from .seed import seed_demo
from .services import Conflict, NotFound, recover_interrupted_analyses

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)
logger = logging.getLogger("feedbackflow")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def init_app_state() -> None:
    """Bring the database to the latest schema and prepare demo data. Safe to call repeatedly."""
    if settings.auto_migrate:
        from .migrate import upgrade_database

        upgrade_database()
    with SessionLocal() as db:
        if recovered := recover_interrupted_analyses(db):
            logger.warning("Marked %d interrupted analyses as failed", recovered)
        if settings.seed_demo:
            seed_demo(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_app_state()
    yield


def create_app(*, run_startup: bool = True) -> FastAPI:
    app = FastAPI(title="FeedbackFlow API", version=__version__, lifespan=lifespan if run_startup else None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(_: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not request.url.path.endswith("feedbackflow.js"):
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/api/health/live", tags=["system"])
    def liveness():
        # Process-only check for orchestrator liveness probes: a database outage should not restart pods.
        return {"ok": True}

    @app.get("/api/health", tags=["system"])
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001
            logger.exception("Health check failed")
            return JSONResponse({"ok": False, "database": "unavailable"}, status_code=503)
        return {"ok": True, "database": "ok", "version": __version__}

    for router in (auth.router, public.router, feedback.router, requirements.router):
        app.include_router(router)

    # The built dashboard and widget are served from the same origin in single-process deployments.
    if (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
