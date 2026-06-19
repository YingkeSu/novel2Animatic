"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.config import get_settings
from app.routers import auth, projects, pipeline, styles, assets, events, generation

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: recover stuck tasks. Shutdown: noop."""
    from app.database import async_session
    from app.models.task import Task
    from app.models.project import Project

    async with async_session() as db:
        # Find tasks stuck in running/pending
        result = await db.execute(
            select(Task).where(Task.status.in_(["running", "pending"]))
        )
        stuck_tasks = result.scalars().all()
        task_ids = [t.id for t in stuck_tasks]
        project_ids_from_tasks = list(set(t.project_id for t in stuck_tasks))

        # Also find projects stuck in running with no active tasks
        result2 = await db.execute(
            select(Project).where(Project.status == "running")
        )
        running_projects = result2.scalars().all()
        running_project_ids = [p.id for p in running_projects]
        orphan_project_ids = [pid for pid in running_project_ids if pid not in project_ids_from_tasks]

        all_project_ids = list(set(project_ids_from_tasks + orphan_project_ids))

        if task_ids or orphan_project_ids:
            if task_ids:
                logger.warning("Recovering %d stuck tasks: %s", len(task_ids), task_ids)
                await db.execute(
                    update(Task).where(Task.id.in_(task_ids)).values(
                        status="failed", error_msg="服务器重启，任务被中断"
                    )
                )
            if orphan_project_ids:
                logger.warning("Recovering %d orphan running projects: %s", len(orphan_project_ids), orphan_project_ids)
            if all_project_ids:
                await db.execute(
                    update(Project).where(Project.id.in_(all_project_ids), Project.status == "running").values(
                        status="failed"
                    )
                )
            await db.commit()
            logger.info("Recovered %d tasks and %d projects", len(task_ids), len(all_project_ids))

    yield


app = FastAPI(title="novel2Animatic", version="0.1.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(styles.router)
app.include_router(assets.router)
app.include_router(events.router)
app.include_router(generation.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
