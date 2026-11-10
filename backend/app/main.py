from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import router as auth_router
from app.core.config import settings
from app.db.session import engine, get_db
from app.events.router import router as events_router
from app.schemas.health import HealthResponse, ReadinessResponse
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for application startup and shutdown."""
    # Startup: verification or resource warm-up if needed
    yield
    # Shutdown: dispose database connection pool cleanly
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Concurrency-safe Event Management & Ticket Booking API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness check",
)
async def health_check() -> HealthResponse:
    """Liveness probe to verify that the application server is responding."""
    return HealthResponse(
        status="ok",
        service=settings.PROJECT_NAME,
        version="0.1.0",
    )


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    tags=["Health"],
    summary="Readiness check",
)
async def readiness_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Readiness probe checking PostgreSQL and Redis connectivity."""
    db_status = "ok"
    redis_status = "ok"

    # Check Database connection
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        db_status = f"unhealthy: {e!s}"

    # Check Redis connection
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        await redis_client.aclose()
    except (aioredis.RedisError, OSError) as e:
        redis_status = f"unhealthy: {e!s}"

    is_ready = db_status == "ok" and redis_status == "ok"
    content = {
        "status": "ready" if is_ready else "not_ready",
        "database": db_status,
        "redis": redis_status,
        "service": settings.PROJECT_NAME,
    }

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=content)
