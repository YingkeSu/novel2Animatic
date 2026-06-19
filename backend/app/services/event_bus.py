"""In-memory event bus for SSE real-time push.

Provides pub/sub semantics for pipeline progress events.
Inspired by InkOS's SSE architecture.
"""

from __future__ import annotations
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Supported SSE event types."""
    PROGRESS = "progress"
    SCENE_UPDATE = "scene_update"
    ERROR = "error"
    COMPLETE = "complete"
    TOOL_EXECUTION = "tool_execution"

    @classmethod
    def values(cls) -> list[str]:
        return [e.value for e in cls]


SUPPORTED_EVENT_TYPES = EventType.values()


@dataclass
class SSEEvent:
    """Single SSE event."""
    type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    project_id: str = ""

    def format_sse(self) -> str:
        """Format as SSE wire format."""
        lines = [f"event: {self.type}", f"data: {__import__('json').dumps(self.data)}"]
        return "\n".join(lines) + "\n\n"


class EventBus:
    """In-memory pub/sub event bus.

    Each project_id has its own channel. Subscribers receive all events
    published to their subscribed project.
    """

    def __init__(self) -> None:
        # project_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, project_id: str) -> asyncio.Queue:
        """Subscribe to events for a project. Returns a queue to consume from."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[project_id].append(queue)
        logger.debug("Subscribed to project %s (total subscribers: %d)",
                     project_id, len(self._subscribers[project_id]))
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe a queue from a project."""
        if queue in self._subscribers[project_id]:
            self._subscribers[project_id].remove(queue)
        logger.debug("Unsubscribed from project %s (remaining: %d)",
                     project_id, len(self._subscribers[project_id]))

    async def publish(self, project_id: str, event_type: str, data: Dict[str, Any]) -> int:
        """Publish an event to all subscribers of a project.

        Returns the number of subscribers that received the event.
        """
        event = SSEEvent(type=event_type, data=data, project_id=project_id)
        subscribers = list(self._subscribers.get(project_id, []))

        dead_queues: List[asyncio.Queue] = []
        sent_count = 0

        for queue in subscribers:
            try:
                queue.put_nowait(event)
                sent_count += 1
            except asyncio.QueueFull:
                logger.warning("Queue full for project %s, removing subscriber", project_id)
                dead_queues.append(queue)

        # Clean up dead queues
        for q in dead_queues:
            self.unsubscribe(project_id, q)

        if sent_count:
            logger.debug("Published %s to project %s (%d subscribers)", event_type, project_id, sent_count)
        return sent_count

    async def stream_events(self, project_id: str, queue: asyncio.Queue) -> AsyncIterator[SSEEvent]:
        """Async generator that yields events from a subscribed queue.

        Handles cleanup when the generator is closed (client disconnects).
        """
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled for project %s", project_id)
        finally:
            self.unsubscribe(project_id, queue)


# Global singleton instance
event_bus = EventBus()
