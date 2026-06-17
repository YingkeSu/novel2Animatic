"""Tests for projects endpoints."""

import pytest
from httpx import AsyncClient

from app.models.project import Project
from app.models.scene import Scene
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
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
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
        "title": "P1", "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
    }, headers={"Authorization": f"Bearer {token}"})
    response = await client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_list_projects_includes_latest_failure_message(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "list-failure@example.com")
    create_resp = await client.post("/api/projects", json={
        "title": "Failed Summary",
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
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
        "title": "Detail Test", "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
    }, headers={"Authorization": f"Bearer {token}"})
    project_id = create_resp.json()["id"]
    response = await client.get(f"/api/projects/{project_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["title"] == "Detail Test"


@pytest.mark.asyncio
async def test_get_project_detail_orders_scenes_by_sequence(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "detail-scenes-order@example.com")
    create_resp = await client.post("/api/projects", json={
        "title": "Scene Order",
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
    }, headers={"Authorization": f"Bearer {token}"})
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        for seq in [2, 1, 3]:
            db.add(Scene(
                project_id=project_id,
                seq=seq,
                title=f"Scene {seq}",
                text=f"Text {seq}",
                shot_type="中景",
                narration=f"Narration {seq}",
                edit_prompt=f"Prompt {seq}",
                instruction="语气自然",
            ))
        await db.commit()

    response = await client.get(f"/api/projects/{project_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [scene["seq"] for scene in response.json()["scenes"]] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_project_detail_includes_scene_prompt_fields(client: AsyncClient, db_session_factory):
    token = await register_and_get_token(client, "detail-scene-prompts@example.com")
    create_resp = await client.post("/api/projects", json={
        "title": "Scene Prompts",
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
    }, headers={"Authorization": f"Bearer {token}"})
    project_id = create_resp.json()["id"]

    async with db_session_factory() as db:
        db.add(Scene(
            project_id=project_id,
            seq=1,
            title="景阳冈",
            text="武松来到景阳冈。",
            shot_type="远景",
            narration="武松行至冈上。",
            edit_prompt="水墨风格，武松立于山冈，远处松林。",
            instruction="语气沉稳，略带紧张。",
        ))
        await db.commit()

    response = await client.get(f"/api/projects/{project_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    [scene] = response.json()["scenes"]
    assert scene["text"] == "武松来到景阳冈。"
    assert scene["edit_prompt"] == "水墨风格，武松立于山冈，远处松林。"
    assert scene["instruction"] == "语气沉稳，略带紧张。"


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    response = await client.get("/api/projects")
    assert response.status_code == 401
