"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from eyohe import __version__
from eyohe.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from eyohe.api.v1.router import api_router
from eyohe.core.config import get_settings
from eyohe.core.db import dispose_engine
from eyohe.core.errors import AppError
from eyohe.core.logging import configure_logging, get_logger

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    log.info("startup", version=__version__, env=settings.eyohe_env, job_backend=settings.job_backend)
    from eyohe.orchestrator.jobs import job_manager

    await job_manager.start()
    try:
        yield
    finally:
        await job_manager.stop()
        await dispose_engine()
        log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Eyohe OSINT API",
        version=__version__,
        description="Public Intelligence. Connected Evidence. — local-first OSINT investigation platform.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if exc.detail.get("retry_after_seconds"):
            headers["retry-after"] = str(exc.detail["retry_after_seconds"])
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict(), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "")} for e in exc.errors()
        ]
        first = errors[0] if errors else {"field": "", "message": "invalid request"}
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": f"Invalid value for '{first['field']}': {first['message']}",
                "detail": {"errors": errors},
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": f"Internal error ({type(exc).__name__}). Check the API logs with the request id.",
                "detail": {},
            },
        )

    app.include_router(api_router)
    return app


app = create_app()
