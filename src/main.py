from contextlib import asynccontextmanager
import logging
from typing import Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import settings
from src.db import check_db_health, close_db_pool, fetch_all_runs, init_db_pool, insert_run
from src.schemas import HealthResponse, RunCreate, RunResponse

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("celesto-control-plane")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for connection pool."""
    logger.info("Starting Celesto Control Plane API...")
    try:
        await init_db_pool()
    except Exception as exc:
        logger.error("Database connection initialization failed during startup: %s", exc)
    yield
    logger.info("Shutting down Celesto Control Plane API...")
    await close_db_pool()


app = FastAPI(
    title="Celesto Sandbox Control Plane",
    description="Trusted host control plane API for sandbox verification runs and audit ledger.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Map request validation errors strictly to HTTP 400."""
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        errors.append(f"{loc}: {msg}")
    error_detail = "; ".join(errors)
    logger.warning("Rejected invalid request: %s", error_detail)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": error_detail},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle domain validation errors as HTTP 400."""
    logger.warning("Domain validation error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def get_health():
    """Health check endpoint. Returns HTTP 200 and {'status': 'ok'}."""
    is_db_healthy = await check_db_health()
    if not is_db_healthy:
        # If DB is not reachable, still report structured response or error
        logger.warning("Health check invoked but database is currently unreachable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "error": "Database ledger unreachable"},
        )
    return {"status": "ok"}


@app.get("/api/runs", response_model=list[RunResponse], status_code=status.HTTP_200_OK)
async def list_runs():
    """Return JSON array of all persisted run records."""
    try:
        runs = await fetch_all_runs()
        return runs
    except Exception as exc:
        logger.error("Failed to fetch runs from ledger: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve runs from database ledger.",
        )


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run_record(payload: RunCreate):
    """Create a new run record with strict validation. Returns HTTP 201 on success."""
    try:
        new_run = await insert_run(
            sandbox_name=payload.sandbox_name,
            state=payload.state,
            execution_target=payload.execution_target,
            task_id=payload.task_id,
            metadata=payload.metadata,
        )
        logger.info(
            "Created run record id=%d sandbox_name=%s state=%s",
            new_run["id"],
            new_run["sandbox_name"],
            new_run["state"],
        )
        return new_run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to insert run record: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error inserting run record.",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )
