"""Tests for project-level reference image generation."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.project import Project
from app.models.user import User
from app.services.pipeline import generate_reference_asset


@pytest.mark.asyncio
async def test_generate_reference_asset_creates_project_reference(db_session_factory, tmp_path):
    client = MagicMock()
    client.image_generate.return_value = b"reference-image"
    project = Project(
        user_id=7,
        title="Test Project",
        source_text="原始文本",
        style_writing="modern",
        style_visual="ink_wash",
        style_audio="ancient_male",
        status="created",
    )
    scene = SimpleNamespace(id=101, title="主角登场", character="萧炎", edit_prompt="少年立于山巅")

    async with db_session_factory() as db:
        db.add(User(id=7, email="user@example.com", password_hash="hash"))
        db.add(project)
        await db.commit()

        asset = await generate_reference_asset(
            db=db,
            client=client,
            project=project,
            scenes=[scene],
            project_dir=tmp_path,
        )

    reference_path = tmp_path / "reference.png"
    assert reference_path.exists()
    assert reference_path.read_bytes() == b"reference-image"
    assert asset.project_id == project.id
    assert asset.scene_id is None
    assert asset.type == "reference"
    assert Path(asset.file_path) == reference_path
    assert asset.file_size == len(b"reference-image")
    client.image_generate.assert_called_once()
    prompt = client.image_generate.call_args.kwargs["prompt"]
    assert "萧炎" in prompt
    assert "少年立于山巅" in prompt
