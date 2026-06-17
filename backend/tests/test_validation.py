"""Tests for input validation."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": "test123456"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project_empty_text(client: AsyncClient):
    token = await register_and_get_token(client, "valid1@test.com")
    r = await client.post("/api/projects", json={
        "title": "Test",
        "source_text": "",
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_too_short(client: AsyncClient):
    token = await register_and_get_token(client, "valid2@test.com")
    r = await client.post("/api/projects", json={
        "title": "Test",
        "source_text": "短",
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_empty_title(client: AsyncClient):
    token = await register_and_get_token(client, "valid3@test.com")
    r = await client.post("/api/projects", json={
        "title": "",
        "source_text": "武松打虎是一段很长的故事文本用来测试验证。",
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_valid(client: AsyncClient):
    token = await register_and_get_token(client, "valid4@test.com")
    r = await client.post("/api/projects", json={
        "title": "武松打虎",
        "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。",
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["title"] == "武松打虎"
