"""Tests for project delete."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": "test123456"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    token = await register_and_get_token(client, "del1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create project
    r = await client.post("/api/projects", json={
        "title": "To Delete", "source_text": "武松打虎是一段很长的故事文本用来测试验证。"
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
        "title": "A's project", "source_text": "武松打虎是一段很长的故事文本用来测试验证。"
    }, headers={"Authorization": f"Bearer {token_a}"})
    pid = r.json()["id"]

    # User B tries to delete it
    token_b = await register_and_get_token(client, "del3b@example.com")
    r = await client.delete(f"/api/projects/{pid}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404  # not found for B
