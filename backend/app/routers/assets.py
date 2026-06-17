"""Assets router - serve generated files."""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.project import Project
from app.models.asset import Asset
from app.models.scene import Scene

router = APIRouter(prefix="/api/projects", tags=["assets"])


def _extract_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    token: str | None = Query(default=None),
) -> str:
    if authorization:
        scheme, _, raw_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not raw_token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return raw_token
    if token:
        return token
    raise HTTPException(status_code=401, detail="Missing token")


async def _resolve_user(token: str, db: AsyncSession) -> User:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, Exception):
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/{project_id}/video")
async def get_video(
    project_id: int,
    token: str = Depends(_extract_token),
    db: AsyncSession = Depends(get_db),
):
    user = await _resolve_user(token, db)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Asset).where(Asset.project_id == project_id, Asset.type == "video")
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file missing")

    return FileResponse(path=str(file_path), media_type="video/mp4", filename=f"project_{project_id}.mp4")


@router.get("/{project_id}/reference")
async def get_reference(
    project_id: int,
    token: str = Depends(_extract_token),
    db: AsyncSession = Depends(get_db),
):
    user = await _resolve_user(token, db)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Asset).where(Asset.project_id == project_id, Asset.type == "reference")
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Reference image not found")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Reference image file missing")

    return FileResponse(path=str(file_path), media_type="image/png", filename=f"project_{project_id}_reference.png")


@router.get("/{project_id}/scenes/{scene_seq}/{file_type}")
async def get_scene_file(
    project_id: int,
    scene_seq: int,
    file_type: str,
    token: str = Depends(_extract_token),
    db: AsyncSession = Depends(get_db),
):
    if file_type not in ("image", "audio"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    user = await _resolve_user(token, db)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    scene_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id, Scene.seq == scene_seq)
    )
    scene = scene_result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    result = await db.execute(
        select(Asset).where(Asset.scene_id == scene.id, Asset.type == file_type)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing")

    media_type = "image/png" if file_type == "image" else "audio/mpeg"
    return FileResponse(path=str(file_path), media_type=media_type)
