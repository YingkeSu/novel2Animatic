"""Open world engine data models.

Inspired by InkOS Play's graph database architecture.
Entities, edges, state slots, and events form the world state.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class World(Base):
    """World definition — the top-level container for an interactive world.

    Stores premise, contracts, and mode. A world belongs to a project
    (optional) and contains entities, edges, state slots, and events.
    """
    __tablename__ = "worlds"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    premise: Mapped[str] = mapped_column(Text)
    world_contract: Mapped[str] = mapped_column(Text, default="")
    visual_contract: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(20), default="open")  # open | guided
    language: Mapped[str] = mapped_column(String(10), default="zh")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entities: Mapped[list["WorldEntity"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    edges: Mapped[list["WorldEdge"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    state_slots: Mapped[list["WorldStateSlot"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    events: Mapped[list["WorldEvent"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )


class WorldEntity(Base):
    """Entity in the world graph — actors, locations, items, evidence, etc.

    Entity types are genre-neutral: actor (romance), location (adventure),
    evidence (mystery), item (fantasy), etc.
    """
    __tablename__ = "world_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(100))  # Stable ID like "actor_player"
    type: Mapped[str] = mapped_column(String(30))  # actor, location, item, evidence, clue, ...
    label: Mapped[str] = mapped_column(String(200))  # Human-readable name
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(100), default="")  # Status progression word
    created_event: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    updated_event: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    world: Mapped["World"] = relationship(back_populates="entities")


class WorldEdge(Base):
    """Relationship/edge between two entities in the world graph.

    Edges represent relations (ally, suspect), holdings (holds item),
    and observations. Supports temporal validity via valid_from/until.
    """
    __tablename__ = "world_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    from_entity_id: Mapped[int] = mapped_column(ForeignKey("world_entities.id"))
    to_entity_id: Mapped[int] = mapped_column(ForeignKey("world_entities.id"))
    type: Mapped[str] = mapped_column(String(50))  # ally, suspect, holds, observes, ...
    value_json: Mapped[str] = mapped_column(Text, default='{}')
    valid_from_event: Mapped[str] = mapped_column(String(50), default="")
    valid_until_event: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    strength: Mapped[Optional[float]] = mapped_column(nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    world: Mapped["World"] = relationship(back_populates="edges")


class WorldStateSlot(Base):
    """State slot attached to an entity or the world itself.

    Kinds: resource, relation, pressure, clue, evidence, flag, timer.
    Values are natural-language-first; numbers only for countdowns/quantities.
    """
    __tablename__ = "world_state_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    owner_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("world_entities.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30))  # resource, pressure, clue, evidence, flag, timer
    label: Mapped[str] = mapped_column(String(200))
    value_json: Mapped[str] = mapped_column(Text, default='""')
    updated_event: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    world: Mapped["World"] = relationship(back_populates="state_slots")


class WorldEvent(Base):
    """Immutable event in the world timeline.

    Events are append-only and represent player actions (look, say, move, do, wait)
    with their outcomes and time advancement.
    """
    __tablename__ = "world_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"), index=True)
    turn: Mapped[int] = mapped_column(Integer)
    action_kind: Mapped[str] = mapped_column(String(20))  # look, say, move, do, wait
    raw_input: Mapped[str] = mapped_column(Text, default="")
    outcome_summary: Mapped[str] = mapped_column(Text, default="")
    time_advance_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    world: Mapped["World"] = relationship(back_populates="events")
