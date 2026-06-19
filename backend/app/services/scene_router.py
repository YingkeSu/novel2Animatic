"""Scene source router — maps source types to handler pipelines.

Routes scene generation to the appropriate handler:
- text_split: existing pipeline (LLM splits text into scenes)
- short_fiction: three-sandwich pipeline (outline→review→revise→write→review→revise)
- play_world: 4-step turn pipeline (interpret→mutate→render→reconcile)

All three sources produce Scene-compatible dicts.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class SceneSource(str, Enum):
    """Supported scene source types."""
    TEXT_SPLIT = "text_split"
    SHORT_FICTION = "short_fiction"
    PLAY_WORLD = "play_world"


@dataclass
class RouteResult:
    """Result of routing a scene source to its handler."""
    source: SceneSource
    handler: str  # Module.function path for the handler


def route_scenes(source_type: str) -> RouteResult:
    """Route a scene source type to its handler.

    Args:
        source_type: One of "text_split", "short_fiction", "play_world".

    Returns:
        RouteResult with source enum and handler path.

    Raises:
        ValueError: If source_type is unknown.
    """
    try:
        source = SceneSource(source_type)
    except ValueError:
        raise ValueError(f"Unknown source type: {source_type}. Must be one of: {[s.value for s in SceneSource]}")

    handlers = {
        SceneSource.TEXT_SPLIT: "pipeline.split_scenes",
        SceneSource.SHORT_FICTION: "scene_generator.generate",
        SceneSource.PLAY_WORLD: "world_engine.step",
    }

    return RouteResult(
        source=source,
        handler=handlers[source],
    )
