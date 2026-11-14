import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

import app.models
from app.api.routes import (
    admin_library,
    catalog,
    context,
    exam,
    generation,
    lessons,
    outputs,
    pedagogy,
    pilot,
    retrieval,
    router,
    sources,
    web_knowledge,
    workflow,
)
from app.core.config import get_settings
from app.core.pilot_auth import require_pilot_access
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.runtime_readiness import ReadinessCheck, runtime_readiness_checks

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.4.0", lifespan=lifespan)

app.include_router(router.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(context.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(lessons.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(catalog.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(exam.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(sources.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(retrieval.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(generation.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(pedagogy.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(outputs.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(workflow.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(pilot.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(admin_library.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])
app.include_router(web_knowledge.router, prefix="/api/v1", dependencies=[Depends(require_pilot_access)])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


async def _database_readiness_check() -> ReadinessCheck:
    async def query() -> tuple[bool, bool]:
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT "
                        "to_regclass('public.generation_runs') IS NOT NULL, "
                        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                    )
                )
            ).one()
            return bool(row[0]), bool(row[1])

    try:
        schema_ready, vector_ready = await asyncio.wait_for(query(), timeout=5)
    except Exception:
        return ReadinessCheck(
            "database",
            False,
            "Database readiness check failed.",
        )
    if not schema_ready:
        return ReadinessCheck("database", False, "Required database schema is missing.")
    if not vector_ready:
        return ReadinessCheck("database", False, "pgvector extension is missing.")
    return ReadinessCheck("database", True, "Database schema and pgvector are ready.")


@app.get("/ready")
async def readiness():
    checks = runtime_readiness_checks(settings)
    checks.append(await _database_readiness_check())
    ready = all(item.ok for item in checks)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "ready": ready,
            "release": settings.pilot_release_label,
        },
    )
