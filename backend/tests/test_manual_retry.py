"""Tests for manual retry endpoint."""

import pytest
from sqlalchemy import select

from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.asset import Asset
from app.models.scene import Scene


@pytest.mark.asyncio
async def test_run_endpoint_allows_retry_after_failure(client, db_session_factory):
    """POST /run should allow re-running after a failed task."""
    # Register user first
    resp = await client.post("/api/auth/register",
                             json={"email": "manual-retry@example.com", "password": "test123456"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get user ID from DB
    async with db_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "manual-retry@example.com"))).scalar_one()
        project = Project(user_id=user.id, title="Retry Project",
                          source_text="足够长的文段用于验证手动重试。" * 5,
                          style_writing="modern", style_visual="ink_wash",
                          style_audio="ancient_male", status="failed")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id,
                    status="failed", step="generate_images", progress=40,
                    error_msg="API timeout")
        db.add(task)
        await db.commit()
        project_id = project.id

    # Retry
    resp = await client.post(f"/api/projects/{project_id}/run", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_run_endpoint_blocks_while_running(client, db_session_factory):
    """POST /run should return 409 if pipeline is already running."""
    resp = await client.post("/api/auth/register",
                             json={"email": "blocking-retry@example.com", "password": "test123456"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async with db_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "blocking-retry@example.com"))).scalar_one()
        project = Project(user_id=user.id, title="Blocking Project",
                          source_text="足够长的文段用于验证重复运行阻止。" * 5,
                          style_writing="modern", style_visual="ink_wash",
                          style_audio="ancient_male", status="running")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id,
                    status="running", step="generate_images", progress=40)
        db.add(task)
        await db.commit()
        project_id = project.id

    resp = await client.post(f"/api/projects/{project_id}/run", headers=headers)
    assert resp.status_code == 409
    assert "already running" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_progress_endpoint_returns_retry_info(client, db_session_factory):
    """GET /progress should return current task info including error details."""
    resp = await client.post("/api/auth/register",
                             json={"email": "progress-retry@example.com", "password": "test123456"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async with db_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == "progress-retry@example.com"))).scalar_one()
        project = Project(user_id=user.id, title="Progress Project",
                          source_text="足够长的文段用于验证进度返回。" * 5,
                          style_writing="modern", style_visual="ink_wash",
                          style_audio="ancient_male", status="failed")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id,
                    status="failed", step="generate_audio", progress=65,
                    error_msg="Rate limit exceeded")
        db.add(task)
        await db.commit()
        project_id = project.id

    resp = await client.get(f"/api/projects/{project_id}/progress", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["step"] == "generate_audio"
    assert data["progress"] == 65
    assert data["error_msg"] == "Rate limit exceeded"
