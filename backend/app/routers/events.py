"""SSE real-time event push router."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["events"])


@router.get("/{project_id}/events")
async def project_events(project_id: str):
    """SSE endpoint for real-time pipeline progress events.

    Returns a StreamingResponse with Content-Type text/event-stream.
    Events are pushed in real-time as the pipeline progresses.

    Event types:
    - progress: {step, progress, status}
    - scene_update: {scene_seq, type, status}
    - error: {step, error}
    - complete: {status, message}
    - tool_execution: {name, status, result}
    """
    queue = event_bus.subscribe(project_id)

    async def event_stream():
        """Generator that yields SSE-formatted events."""
        # Initial keepalive comment
        yield ": connected\n\n"

        try:
            async for event in event_bus.stream_events(project_id, queue):
                yield event.format_sse()
        except asyncio.CancelledError:
            logger.debug("SSE client disconnected from project %s", project_id)
        finally:
            # Ensure cleanup
            event_bus.unsubscribe(project_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
