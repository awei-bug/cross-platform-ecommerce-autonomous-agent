from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_db, initialize_database
from app.schemas.common import HealthResponse, ReadinessResponse
from app.services.seed import seed_if_empty

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    from app.db.session import session_scope
    from app.services.competitor_repository import ensure_seed_competitors

    with session_scope() as db:
        seed_if_empty(db)
        ensure_seed_competitors(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="一站式多平台电商运营 AI 工作台后端 API。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(service=settings.app_name, version=settings.app_version)


@app.get("/ready", response_model=ReadinessResponse, tags=["system"])
def readiness(db: Annotated[Session, Depends(get_db)]) -> ReadinessResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库连接不可用",
        ) from exc
    database_backend = settings.database_url.split(":", maxsplit=1)[0]
    task_execution = "eager" if settings.celery_task_always_eager else "celery-worker"
    return ReadinessResponse(database=database_backend, task_execution=task_execution)
