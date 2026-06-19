"""World HUD — heads-up display data for the open world engine.

Provides structured data for the frontend world state panel:
- Entity roster (all entities with type, label, summary, status)
- Relationship web (from→to→type edges)
- Holdings (who holds what)
- State slots (grouped by kind: resource, pressure, clue, evidence, flag, timer)
- Evidence lifecycle (progression stages)
- Current scene text and turn number
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class HUDData:
    """Structured HUD data for frontend consumption."""
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    holdings: List[Dict[str, Any]]
    state_slots: Dict[str, List[Dict[str, Any]]]
    evidence_lifecycle: List[Dict[str, Any]]
    current_scene: str
    turn: int

    @classmethod
    def empty(cls) -> HUDData:
        """Create an empty HUD data object."""
        return cls(
            entities=[],
            relations=[],
            holdings=[],
            state_slots={},
            evidence_lifecycle=[],
            current_scene="",
            turn=0,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to frontend-compatible dict."""
        return {
            "entities": self.entities,
            "relations": self.relations,
            "holdings": self.holdings,
            "state_slots": self.state_slots,
            "evidence_lifecycle": self.evidence_lifecycle,
            "current_scene": self.current_scene,
            "turn": self.turn,
        }


class WorldHUD:
    """Query builder for world HUD data from the database.

    Usage:
        hud = WorldHUD(session)
        data = await hud.get_hud_data(world_id)
    """

    def __init__(self, session=None) -> None:
        self._session = session

    async def get_hud_data(self, world_id: int) -> HUDData:
        """Build HUD data from world state.

        Args:
            world_id: World database ID.

        Returns:
            HUDData with all HUD components.
        """
        if self._session is None:
            return HUDData.empty()

        from app.models.world import WorldEntity, WorldEdge, WorldStateSlot, WorldEvent
        from sqlalchemy import select

        # Entities
        result = await self._session.execute(
            select(WorldEntity).where(WorldEntity.world_id == world_id)
        )
        entities = [
            {"id": e.id, "entity_id": e.entity_id, "type": e.type, "label": e.label, "summary": e.summary, "status": e.status}
            for e in result.scalars().all()
        ]

        # Active edges (not soft-deleted)
        result = await self._session.execute(
            select(WorldEdge).where(
                WorldEdge.world_id == world_id,
                WorldEdge.valid_until_event.is_(None),
            )
        )
        edges = result.scalars().all()
        entity_map = {e.id: e.label for e in (await self._session.execute(select(WorldEntity).where(WorldEntity.world_id == world_id))).scalars().all()}

        relations = []
        holdings = []
        for edge in edges:
            from_label = entity_map.get(edge.from_entity_id, f"entity-{edge.from_entity_id}")
            to_label = entity_map.get(edge.to_entity_id, f"entity-{edge.to_entity_id}")
            entry = {"from": from_label, "to": to_label, "type": edge.type}

            # Classify as relation or holding based on edge type
            if edge.type in ("holds", "carries", "owns"):
                holdings.append({"holder": from_label, "item": to_label})
            else:
                relations.append(entry)

        # State slots grouped by kind
        result = await self._session.execute(
            select(WorldStateSlot).where(WorldStateSlot.world_id == world_id)
        )
        slots = result.scalars().all()
        state_slots: Dict[str, List[Dict[str, Any]]] = {}
        for slot in slots:
            kind = slot.kind
            if kind not in state_slots:
                state_slots[kind] = []
            state_slots[kind].append({
                "label": slot.label,
                "value": slot.value_json,
                "owner_entity_id": slot.owner_entity_id,
            })

        # Evidence lifecycle
        evidence_lifecycle = []
        for slot in slots:
            if slot.kind == "evidence":
                evidence_lifecycle.append({
                    "label": slot.label,
                    "value": slot.value_json,
                })

        # Current scene from latest event
        result = await self._session.execute(
            select(WorldEvent)
            .where(WorldEvent.world_id == world_id)
            .order_by(WorldEvent.turn.desc())
            .limit(1)
        )
        latest_event = result.scalar_one_or_none()
        current_scene = latest_event.outcome_summary if latest_event else ""
        turn = latest_event.turn if latest_event else 0

        return HUDData(
            entities=entities,
            relations=relations,
            holdings=holdings,
            state_slots=state_slots,
            evidence_lifecycle=evidence_lifecycle,
            current_scene=current_scene,
            turn=turn,
        )
