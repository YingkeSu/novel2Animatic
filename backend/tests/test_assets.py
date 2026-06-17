"""Tests for generated asset access."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.models.asset import Asset
from app.models.scene import Scene
from tests.test_projects import register_and_get_token


@pytest.mark.asyncio
async def test_reference_asset_downloads_with_authorization_header(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.assets.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "asset-reference@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Reference",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    reference_path = tmp_path / "test-assets" / str(project_id) / "reference.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
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
async def test_reference_asset_serves_latest_record_when_duplicates_exist(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.assets.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "asset-duplicate-reference@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Duplicate Reference",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    old_path = tmp_path / "test-assets" / str(project_id) / "old-reference.png"
    latest_path = tmp_path / "test-assets" / str(project_id) / "latest-reference.png"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old-reference")
    latest_path.write_bytes(b"latest-reference")

    async with db_session_factory() as db:
        db.add(Asset(project_id=project_id, scene_id=None, type="reference", file_path=str(old_path), file_size=len(b"old-reference")))
        await db.flush()
        db.add(Asset(project_id=project_id, scene_id=None, type="reference", file_path=str(latest_path), file_size=len(b"latest-reference")))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/reference",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.content == b"latest-reference"


@pytest.mark.asyncio
async def test_asset_path_outside_storage_root_is_not_served(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
):
    token = await register_and_get_token(client, "asset-path-safety@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Path Safety",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    outside_path = tmp_path / "outside-storage.mp4"
    outside_path.write_bytes(b"outside")

    async with db_session_factory() as db:
        db.add(Asset(project_id=project_id, scene_id=None, type="video", file_path=str(outside_path), file_size=7))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/video",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video file missing"


@pytest.mark.asyncio
async def test_video_asset_accepts_authorization_header(client: AsyncClient):
    token = await register_and_get_token(client, "asset-header@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Header",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
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
async def test_video_asset_accepts_bearer_token_with_extra_whitespace(client: AsyncClient):
    token = await register_and_get_token(client, "asset-bearer-whitespace@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Bearer Whitespace",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/projects/{project_id}/video",
        headers={"Authorization": f"Bearer   {token}  "},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


@pytest.mark.asyncio
async def test_video_asset_rejects_invalid_authorization_scheme(client: AsyncClient):
    token = await register_and_get_token(client, "asset-invalid-scheme@example.com")

    response = await client.get(
        "/api/projects/1/video",
        headers={"Authorization": f"Basic {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_video_asset_rejects_empty_bearer_token(client: AsyncClient):
    response = await client.get(
        "/api/projects/1/video",
        headers={"Authorization": "Bearer   "},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_video_asset_serves_latest_record_when_duplicates_exist(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.assets.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "asset-duplicate-video@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Duplicate Video",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    old_path = tmp_path / "test-assets" / str(project_id) / "old.mp4"
    latest_path = tmp_path / "test-assets" / str(project_id) / "latest.mp4"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old-video")
    latest_path.write_bytes(b"latest-video")

    async with db_session_factory() as db:
        db.add(Asset(project_id=project_id, scene_id=None, type="video", file_path=str(old_path), file_size=len(b"old-video")))
        await db.flush()
        db.add(Asset(project_id=project_id, scene_id=None, type="video", file_path=str(latest_path), file_size=len(b"latest-video")))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/video",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.content == b"latest-video"


@pytest.mark.asyncio
async def test_video_asset_accepts_lowercase_bearer_scheme(client: AsyncClient):
    token = await register_and_get_token(client, "asset-lower-bearer@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Lower Bearer",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
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
async def test_video_asset_rejects_query_token(client: AsyncClient):
    token = await register_and_get_token(client, "asset-query-rejected@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Query",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/projects/{project_id}/video?token={token}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


@pytest.mark.asyncio
async def test_video_asset_authorization_header_takes_precedence(client: AsyncClient):
    token = await register_and_get_token(client, "asset-precedence@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Precedence",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
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
async def test_scene_asset_invalid_file_type_without_auth_is_unauthorized(client: AsyncClient):
    response = await client.get("/api/projects/1/scenes/1/video")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


@pytest.mark.asyncio
async def test_scene_asset_invalid_file_type_still_bad_request(client: AsyncClient):
    token = await register_and_get_token(client, "asset-invalid-type@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Invalid Type",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
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


@pytest.mark.asyncio
async def test_scene_asset_serves_latest_record_when_duplicates_exist(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.assets.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "asset-duplicate-scene@example.com")
    create_resp = await client.post(
        "/api/projects",
        json={
            "title": "Asset Duplicate Scene",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = create_resp.json()["id"]
    scene_path = tmp_path / "test-assets" / str(project_id) / "scene_1.png"
    older_path = tmp_path / "test-assets" / str(project_id) / "scene_1-old.png"
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    older_path.write_bytes(b"older-scene")
    scene_path.write_bytes(b"newer-scene")

    async with db_session_factory() as db:
        scene = Scene(
            project_id=project_id,
            seq=1,
            title="Scene 1",
            text="Scene text",
            shot_type="中景",
            narration="Narration",
            edit_prompt="Prompt",
            instruction="语气自然",
        )
        db.add(scene)
        await db.flush()
        db.add(Asset(project_id=project_id, scene_id=scene.id, type="image", file_path=str(older_path), file_size=len(b"older-scene")))
        await db.flush()
        db.add(Asset(project_id=project_id, scene_id=scene.id, type="image", file_path=str(scene_path), file_size=len(b"newer-scene")))
        await db.commit()

    response = await client.get(
        f"/api/projects/{project_id}/scenes/1/image",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.content == b"newer-scene"


@pytest.mark.asyncio
async def test_scene_asset_must_belong_to_requested_project(
    client: AsyncClient,
    db_session_factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.assets.STORAGE_DIR", tmp_path)
    token = await register_and_get_token(client, "asset-scene-scope@example.com")
    first_resp = await client.post(
        "/api/projects",
        json={
            "title": "First Project",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    second_resp = await client.post(
        "/api/projects",
        json={
            "title": "Second Project",
            "source_text": "武松在路上行了几日，来到阳谷县地面。当日晌午，走得肚中饥渴，望见前面有一个酒店。店前挑着一面招旗，上头写着三碗不过冈。武松见了，便入店坐下，叫酒保筛酒来吃。酒肉",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    first_project_id = first_resp.json()["id"]
    second_project_id = second_resp.json()["id"]
    image_path = tmp_path / "test-assets" / str(first_project_id) / "scene_1.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"first-project-image")

    async with db_session_factory() as db:
        first_scene = Scene(
            project_id=first_project_id,
            seq=1,
            title="First scene",
            text="Scene text",
            shot_type="中景",
            narration="Narration",
            edit_prompt="Prompt",
            instruction="语气自然",
        )
        db.add(first_scene)
        await db.flush()
        db.add(
            Asset(
                project_id=second_project_id,
                scene_id=first_scene.id,
                type="image",
                file_path=str(image_path),
                file_size=len(b"first-project-image"),
            )
        )
        await db.commit()

    response = await client.get(
        f"/api/projects/{first_project_id}/scenes/1/image",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"
