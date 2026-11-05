from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

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
from app.db.session import engine

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
