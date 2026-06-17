"""Tests for projects endpoints."""

import pytest
from httpx import AsyncClient

from app.models.project import Project
from app.models.task import Task


async def register_and_get_token(client: AsyncClient, email: str = "proj@example.com") -> str:
    response = await client.post("/api/auth/register", json={
        "email": email,
        "password": "testpassword123"
    })
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    token = await register_and_get_token(client)
    response = await client.post("/api/projects", json={
        "title": "Test Project",
        "source_text": "这是一段测试文本。",
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Project"
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    token = await register_and_get_token(client, "list@example.com")
    await client.post("/api/projects", json={
        "title": "P1", "source_text": "林冲风雪山神庙是一段很长的故事文本用来测试。"
    }, headers={"Authorization": f"Bearer {token}"})
    response = await client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_list_projects_includes_latest_failure_message(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "list-failure@example.com")
    create_resp = await client.post("/api/projects", json={
        "title": "Failed Summary",
        "source_text": "林冲风雪山神庙是一段很长的故事文本用来测试失败原因展示。"
    }, headers={"Authorization": f"Bearer {token}"})
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        project = await db.get(Project, project_id)
        project.status = "failed"
        db.add(Task(project_id=project_id, user_id=project.user_id, status="failed", step="split_scenes", progress=10, error_msg="LLM JSON parse failed"))
        await db.commit()

    response = await client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    [project] = response.json()
    assert project["latest_error_msg"] == "LLM JSON parse failed"


@pytest.mark.asyncio
async def test_get_project_detail(client: AsyncClient):
    token = await register_and_get_token(client, "detail@example.com")
    create_resp = await client.post("/api/projects", json={
        "title": "Detail Test", "source_text": "武松打虎是一段很长的故事文本用来测试验证。"
    }, headers={"Authorization": f"Bearer {token}"})
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["title"] == "Detail Test"


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    response = await client.get("/api/projects")
    assert response.status_code == 401
