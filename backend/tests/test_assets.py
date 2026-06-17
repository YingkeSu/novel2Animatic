"""Tests for generated asset access."""

import pytest
from httpx import AsyncClient

from app.models.asset import Asset
from tests.test_projects import register_and_get_token


@pytest.mark.asyncio
async def test_reference_asset_downloads_with_authorization_header(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
):
    token = await register_and_get_token(client, "asset-reference@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Reference",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证参考图资产接口。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(b"reference")

    async with db_session_factory() as db:
        db.add(Asset(project_id=project_id, scene_id=None, type="reference", file_path=str(reference_path), file_size=9))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/reference",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.content == b"reference"
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_video_asset_accepts_authorization_header(client: AsyncClient):
    token = await register_and_get_token(client, "asset-header@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Header",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证资产接口认证。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/projects/{project_id}/video",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


@pytest.mark.asyncio
async def test_video_asset_accepts_lowercase_bearer_scheme(client: AsyncClient):
    token = await register_and_get_token(client, "asset-lower-bearer@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Lower Bearer",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证资产接口认证。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/projects/{project_id}/video",
        headers={"Authorization": f"bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


@pytest.mark.asyncio
async def test_video_asset_accepts_query_token(client: AsyncClient):
    token = await register_and_get_token(client, "asset-query@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Query",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证资产接口认证。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/projects/{project_id}/video?token={token}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


@pytest.mark.asyncio
async def test_video_asset_authorization_header_takes_precedence(client: AsyncClient):
    token = await register_and_get_token(client, "asset-precedence@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Precedence",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证资产接口认证。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/projects/{project_id}/video?token={token}",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_scene_asset_missing_auth_is_unauthorized(client: AsyncClient):
    response = await client.get("/api/projects/1/scenes/1/image")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


@pytest.mark.asyncio
async def test_scene_asset_invalid_file_type_still_bad_request(client: AsyncClient):
    token = await register_and_get_token(client, "asset-invalid-type@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Invalid Type",
            "source_text": "这是一段足够长的测试文本，用来创建项目并验证资产接口认证。",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/projects/{project_id}/scenes/1/video",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type"
