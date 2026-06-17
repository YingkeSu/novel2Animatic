"""Database initialization script."""

import asyncio
from app.database import engine, Base
from app.models import User, Project, Scene, Asset, Task


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")


if __name__ == "__main__":
    asyncio.run(init_db())
