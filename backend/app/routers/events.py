"""SSE real-time event push router.

Auth uses the same manual ``Authorization: Bearer`` header pattern as the
asset routes (``_extract_token``), because the frontend consumes this stream
via ``fetch`` + ``ReadableStream`` (which CAN set headers) rather than the
browser-native ``EventSource`` (which cannot). No query-token is accepted —
that would leak credentials into URLs/logs.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["events"])


def _extract_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Pull the raw JWT out of an ``Authorization: Bearer <token>`` header.

    Mirrors :func:`app.routers.assets._extract_token` — kept duplicated (not
    imported) so the events router has no dependency on the assets router.
    """
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) != 2:
            raise HTTPException(status_code=401, detail="Invalid token")
        scheme, raw_token = parts
        token = raw_token.strip()
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return token
    raise HTTPException(status_code=401, detail="Missing token")


async def _resolve_user(token: str, db: AsyncSession) -> User:
    from jose import jwt, JWTError
    from app.config import get_settings

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


@router.get("/{project_id}/events")
async def project_events(
    project_id: int,
    token: str = Depends(_extract_token),
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint for real-time pipeline progress events.

    Returns a StreamingResponse with Content-Type text/event-stream.
    Events are pushed in real-time as the pipeline progresses.

    Event types:
    - progress: {step, progress, status, error_msg?}
    - scene_update: {scene_seq, type, status}
    - error: {step, error, project_id}
    - complete: {status, project_id}
    - tool_execution: {name, status, result}

    Auth: Bearer token via the ``Authorization`` header (same manual-header
    pattern as the asset routes). Ownership of ``project_id`` is verified
    against the resolved user.
    """
    user = await _resolve_user(token, db)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Subscribe AFTER auth/ownership pass so an unauthenticated client can't
    # pin a queue in memory.
    queue = event_bus.subscribe(str(project_id))

    async def event_stream():
        """Generator that yields SSE-formatted events."""
        # Initial keepalive comment — also confirms the stream is open.
        yield ": connected\n\n"

        try:
            async for event in event_bus.stream_events(str(project_id), queue):
                yield event.format_sse()
        except asyncio.CancelledError:
            logger.debug("SSE client disconnected from project %s", project_id)
        finally:
            # Ensure cleanup
            event_bus.unsubscribe(str(project_id), queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
