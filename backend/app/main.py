"""FastAPI application entrypoint.

App import path: `app.main:app` (used by uvicorn and by tests).

Table creation uses `Base.metadata.create_all(bind=engine)` on startup so
the app works out of the box without a manual migration step. For a real
production deployment, replace this with Alembic migrations (future
enhancement) so schema changes are versioned instead of implicitly synced.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import crud, price_service
from .database import Base, engine
from .routers import holdings, portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: no manual migration step needed for this training project —
    # tables are created automatically if they don't already exist.
    # Alembic-based migrations are a natural future enhancement for real
    # schema evolution/versioning.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Portfolio Manager API",
    version="1.0.0",
    description="Single-user, single-currency portfolio manager REST API.",
    lifespan=lifespan,
)

# Dev-only: allow all origins so the static frontend (served from any port,
# or opened directly as a file://) can call this API without CORS friction.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(holdings.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "portfolio-manager-api"}


# ---------------------------------------------------------------------------
# Shared error envelope (§5 of the spec)
# ---------------------------------------------------------------------------


def _error_response(status_code: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()

    # Body wasn't parseable JSON at all -> 400 with no `details` array.
    if errors and all("json" in str(e.get("type", "")).lower() for e in errors):
        return _error_response(400, "VALIDATION_ERROR", "Request body is not valid JSON.")

    details = []
    for e in errors:
        loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
        field = ".".join(loc) if loc else "body"
        details.append({"field": field, "message": e.get("msg", "invalid value")})

    return _error_response(400, "VALIDATION_ERROR", "Request validation failed.", details)


@app.exception_handler(crud.ValidationError)
async def crud_validation_handler(request: Request, exc: crud.ValidationError):
    return _error_response(400, "VALIDATION_ERROR", exc.message, exc.details)


@app.exception_handler(crud.HoldingNotFoundError)
async def not_found_handler(request: Request, exc: crud.HoldingNotFoundError):
    return _error_response(404, "NOT_FOUND", f"Holding {exc.holding_id} not found.")


@app.exception_handler(price_service.TickerNotFoundError)
async def ticker_not_found_handler(request: Request, exc: price_service.TickerNotFoundError):
    return _error_response(422, "TICKER_NOT_FOUND", str(exc))


@app.exception_handler(price_service.UpstreamUnavailableError)
async def upstream_unavailable_handler(request: Request, exc: price_service.UpstreamUnavailableError):
    return _error_response(502, "UPSTREAM_UNAVAILABLE", str(exc))
