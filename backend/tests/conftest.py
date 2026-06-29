"""Test configuration and fixtures."""

import os
from dataclasses import dataclass
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi.middleware.cors import CORSMiddleware

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("STEPFUN_API_KEY", "test-stepfun-api-key")

from app.database import Base, get_db
from app.config import get_settings
from app.routers import auth, projects, pipeline, styles, assets, events, generation, services

TEST_DATABASE_URL = "postgresql+asyncpg://novel2animatic:novel2animatic@localhost:5432/novel2animatic_test"


@dataclass
class TestDbContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _build_test_app() -> FastAPI:
    settings = get_settings()
    test_app = FastAPI(title="novel2Animatic", version="0.1.0")
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(auth.router)
    test_app.include_router(projects.router)
    test_app.include_router(pipeline.router)
    test_app.include_router(styles.router)
    test_app.include_router(assets.router)
    test_app.include_router(events.router)
    test_app.include_router(generation.router)
    test_app.include_router(services.router)

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    return test_app


@asynccontextmanager
async def _make_test_db_context():
    schema_name = f"test_{uuid4().hex}"
    quoted_schema = _quote_identifier(schema_name)
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    test_app = _build_test_app()
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA {quoted_schema}"))
            await conn.execute(text(f"SET search_path TO {quoted_schema}"))
            await conn.run_sync(Base.metadata.create_all)

        test_app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield TestDbContext(client=ac, session_factory=session_factory)
    finally:
        test_app.dependency_overrides.clear()
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"))
        await engine.dispose()


@pytest.fixture
def client_factory():
    @asynccontextmanager
    async def make_client():
        async with _make_test_db_context() as context:
            yield context.client

    return make_client


@pytest_asyncio.fixture
async def test_db_context():
    async with _make_test_db_context() as context:
        yield context


@pytest_asyncio.fixture
async def client(test_db_context):
    yield test_db_context.client


@pytest_asyncio.fixture
async def db_session_factory(test_db_context):
    yield test_db_context.session_factory
