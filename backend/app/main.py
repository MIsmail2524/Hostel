from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import get_settings
from .db import SessionLocal, init_db
from .routers import admin, auth, listings, me, social, tours

log = logging.getLogger("kamra")
VIEWER_DIR = Path(__file__).parent / "viewer"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","log":"%(name)s","msg":"%(message)s"}')
    (s.storage_dir / "public").mkdir(parents=True, exist_ok=True)
    (s.storage_dir / "private").mkdir(parents=True, exist_ok=True)
    init_db()
    if s.run_worker_in_process and s.env != "test":
        from .recon.worker import start_background, stop_background

        start_background()
        yield
        stop_background()
    else:
        yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.app_name} API",
        version="1.0.0",
        description="Rooms, beds & spaces marketplace with photo/video → 3D walkthroughs.",
        lifespan=lifespan,
        docs_url=None if s.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if s.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=False,  # bearer tokens, no cookies → no CSRF surface
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    max_body = s.max_upload_mb * 1024 * 1024 + 1024 * 1024

    @app.middleware("http")
    async def guard(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_body:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if request.method in ("POST", "PUT", "PATCH") and not cl and "multipart/form-data" in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "Content-Length required for uploads"}, status_code=411)
        start = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        h = response.headers
        h["X-Request-ID"] = rid
        h["X-Content-Type-Options"] = "nosniff"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        if s.public_base_url.startswith("https://"):
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        if path.startswith("/viewer"):
            h["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
                "connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
                f"frame-ancestors {' '.join(s.viewer_frame_ancestors)}"
            )
            h["Cache-Control"] = "no-cache"
        elif path.startswith("/media"):
            h["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
            h["Cache-Control"] = "public, max-age=31536000, immutable"
            h["Cross-Origin-Resource-Policy"] = "cross-origin"
        elif path.startswith("/docs"):
            pass  # Swagger UI needs its own inline scripts; disabled in production
        else:
            h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            h["X-Frame-Options"] = "DENY"
            h["Cache-Control"] = "no-store"
        if path.startswith("/api"):
            log.info("%s %s %s %.0fms rid=%s", request.method, path, response.status_code, (time.perf_counter() - start) * 1000, rid)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path")]
            msg = str(e.get("msg", "Invalid value")).removeprefix("Value error, ")
            errors.append({"field": ".".join(loc), "message": msg})
        first = errors[0] if errors else {"field": "", "message": "Invalid request"}
        detail = f"{first['field'].replace('_', ' ').capitalize()}: {first['message']}" if first["field"] else first["message"]
        return JSONResponse({"detail": detail, "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)

    api_prefix = "/api/v1"
    for r in (auth.router, me.router, listings.router, tours.router, social.router, admin.router):
        app.include_router(r, prefix=api_prefix)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"ok": True}

    @app.get("/viewer", include_in_schema=False)
    def viewer_redirect(request: Request):
        return RedirectResponse(url="/viewer/" + (f"?{request.url.query}" if request.url.query else ""))

    (s.storage_dir / "public").mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=s.storage_dir / "public"), name="media")
    app.mount("/viewer", StaticFiles(directory=VIEWER_DIR, html=True), name="viewer")
    return app


app = create_app()
