"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, projects, pipeline, styles, assets, events

app = FastAPI(title="novel2Animatic", version="0.1.0")
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


@app.get("/health")
async def health():
    return {"status": "ok"}
