"""Tests for input validation."""

import pytest
from httpx import AsyncClient

VALID_SOURCE_TEXT = "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉"
SHORT_SOURCE_TEXT = "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒"


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
async def test_create_project_rejects_text_under_stable_scene_length(client: AsyncClient):
    token = await register_and_get_token(client, "valid-short-stable@test.com")
    r = await client.post("/api/projects", json={
        "title": "Short Stable Text",
        "source_text": SHORT_SOURCE_TEXT,
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert len(SHORT_SOURCE_TEXT) == 79
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_empty_title(client: AsyncClient):
    token = await register_and_get_token(client, "valid3@test.com")
    r = await client.post("/api/projects", json={
        "title": "",
        "source_text": VALID_SOURCE_TEXT,
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_rejects_unknown_style(client: AsyncClient):
    token = await register_and_get_token(client, "valid-style@test.com")
    r = await client.post("/api/projects", json={
        "title": "Unknown Style",
        "source_text": VALID_SOURCE_TEXT,
        "style_writing": "modern",
        "style_visual": "does_not_exist",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_valid(client: AsyncClient):
    token = await register_and_get_token(client, "valid4@test.com")
    r = await client.post("/api/projects", json={
        "title": "武松打虎",
        "source_text": VALID_SOURCE_TEXT,
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male"
    }, headers={"Authorization": f"Bearer {token}"})
    assert len(VALID_SOURCE_TEXT) == 80
    assert r.status_code == 200
    assert r.json()["title"] == "武松打虎"
