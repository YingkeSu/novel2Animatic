"""Tests for project delete."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import get_settings


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": "test123456"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    token = await register_and_get_token(client, "del1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create project
    r = await client.post("/api/projects", json={
        "title": "To Delete", "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
    }, headers=headers)
    pid = r.json()["id"]

    # Delete it
    r = await client.delete(f"/api/projects/{pid}", headers=headers)
    assert r.status_code == 200

    # Should be gone
    r = await client.get(f"/api/projects/{pid}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient):
    token = await register_and_get_token(client, "del2@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.delete("/api/projects/9999", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_user_project_forbidden(client: AsyncClient):
    # User A creates project
    token_a = await register_and_get_token(client, "del3a@example.com")
    r = await client.post("/api/projects", json={
        "title": "A's project", "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
    }, headers={"Authorization": f"Bearer {token_a}"})
    pid = r.json()["id"]

    # User B tries to delete it
    token_b = await register_and_get_token(client, "del3b@example.com")
    r = await client.delete(f"/api/projects/{pid}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404  # not found for B


@pytest.mark.asyncio
async def test_delete_project_removes_storage_files(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.projects.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "del4@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/projects", json={
        "title": "With Files",
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
    }, headers=headers)
    pid = r.json()["id"]
    payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
    user_id = payload["sub"]

    project_dir = tmp_path / str(user_id) / str(pid)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "scene_1.png").write_bytes(b"png")
    (project_dir / "scene_1.mp3").write_bytes(b"mp3")
    (project_dir / "final.mp4").write_bytes(b"mp4")

    r = await client.delete(f"/api/projects/{pid}", headers=headers)
    assert r.status_code == 200
    assert not project_dir.exists()
