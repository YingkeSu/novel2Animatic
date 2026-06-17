"""Tests for pipeline run guard behavior."""

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import get_settings
from app.models.project import Project
from app.models.task import Task
from tests.test_projects import register_and_get_token


@pytest.mark.asyncio
async def test_run_rejects_when_pending_task_exists(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "run-guard@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Run Guard",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        project = await db.get(Project, project_id)
        project.status = "created"
        db.add(Task(project_id=project_id, user_id=project.user_id, status="pending", step="split_scenes", progress=10))
        await db.commit()

    response = await client.post(
        f"/api/projects/{project_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Pipeline already running"


@pytest.mark.asyncio
async def test_run_allows_retry_after_terminal_task_state(client: AsyncClient, db_session_factory, monkeypatch):
    token = await register_and_get_token(client, "run-retry@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Run Retry",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        project = await db.get(Project, project_id)
        project.status = "failed"
        db.add(Task(project_id=project_id, user_id=project.user_id, status="failed", step="split_scenes", progress=10))
        await db.commit()

    async def fake_run_pipeline_task(task_id: int):
        return None

    monkeypatch.setattr("app.tasks.pipeline.run_pipeline_task", fake_run_pipeline_task)

    response = await client.post(
        f"/api/projects/{project_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_run_retry_removes_previous_storage_files(client: AsyncClient, db_session_factory, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.pipeline.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "run-retry-storage@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Run Retry Storage",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        project = await db.get(Project, project_id)
        project.status = "failed"
        db.add(Task(project_id=project_id, user_id=project.user_id, status="failed", step="generate_audio", progress=65))
        await db.commit()

    payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
    project_dir = tmp_path / payload["sub"] / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    stale_file = project_dir / "scene_1.png"
    stale_file.write_bytes(b"old image")

    async def fake_run_pipeline_task(task_id: int):
        return None

    monkeypatch.setattr("app.tasks.pipeline.run_pipeline_task", fake_run_pipeline_task)

    response = await client.post(
        f"/api/projects/{project_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert not stale_file.exists()


@pytest.mark.asyncio
async def test_progress_returns_newest_task(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "run-progress@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Run Progress",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        project = await db.get(Project, project_id)
        db.add(Task(project_id=project_id, user_id=project.user_id, status="failed", step="split_scenes", progress=10))
        db.add(Task(project_id=project_id, user_id=project.user_id, status="pending", step="generate_images", progress=40))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/progress",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["step"] == "generate_images"
    assert response.json()["progress"] == 40
