"""Open world engine — 4-step turn pipeline.

Implements InkOS Play's 4-step pipeline:
  1. Action Interpreter (temp 0.15) — normalize player input
  2. World Mutator (temp 0.25) — generate state mutations
  3. Scene Renderer (temp 0.45) — generate scene text + suggested actions
  4. Scene Reconciler (temp 0.1) — cross-check scene vs graph

Key design: render-before-commit (all-or-nothing semantics).
Fail-open: individual malformed items are skipped, not crashed.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Result of a single world turn (one player action + system response)."""
    scene_text: str
    suggested_actions: List[str]
    mutation_summary: str
    turn: int
    action_kind: str

    def to_scene_dict(self) -> Dict[str, Any]:
        """Convert to Scene model-compatible dict for animatic pipeline."""
        # Generate a title from the first line of scene text
        first_line = self.scene_text.split("\n")[0][:50] if self.scene_text else f"回合 {self.turn}"
        return {
            "title": f"世界回合 {self.turn}: {first_line}",
            "text": self.scene_text,
            "shot_type": "medium",
            "narration": self.scene_text[:200],
            "edit_prompt": f"场景：{first_line}",
            "instruction": "自然推进",
            "character": "",
            "source_type": "play_world",
            "seq": self.turn,
        }


class WorldEngine:
    """4-step turn pipeline for interactive world simulation.

    Usage:
        engine = WorldEngine()
        result = await engine.step(world_id=1, turn=1, raw_input="看看周围", context="竹林")
        # result.scene_text, result.suggested_actions, result.to_scene_dict()
    """

    def __init__(self) -> None:
        self.interpreter_temp = 0.15
        self.mutator_temp = 0.25
        self.renderer_temp = 0.45
        self.reconciler_temp = 0.1

    async def step(
        self,
        world_id: int,
        turn: int,
        raw_input: str,
        context: str,
    ) -> TurnResult:
        """Execute a single world turn.

        Args:
            world_id: World database ID.
            turn: Turn number.
            raw_input: Player's raw input text.
            context: Current world context brief.

        Returns:
            TurnResult with scene text, suggested actions, and scene dict.
        """
        # Step 1: Interpret action (fail-open: fallback to "do")
        try:
            action = await self._interpret(raw_input, context)
        except Exception as e:
            logger.warning("Action interpretation failed, falling back to 'do': %s", e)
            action = {"action_kind": "do", "intent": raw_input}

        action_kind = action.get("action_kind", "do")

        # Step 2: Propose mutation (fail-open: blocked turn on failure)
        try:
            mutation = await self._mutate(turn, raw_input, action, context)
        except Exception as e:
            logger.warning("Mutation failed: %s", e)
            mutation = {
                "entities": {"upsert": []},
                "edges": {"upsert": [], "expire": []},
                "state_slots": {"upsert": []},
                "blocked": True,
                "blocked_reason": str(e),
                "summary": "模型输出无法解析",
            }

        # Handle blocked turn
        if mutation.get("blocked"):
            reason = mutation.get("blocked_reason", "你无法在这里做这件事")
            return TurnResult(
                scene_text=f"你无法在这里做这件事。{reason}",
                suggested_actions=["换个方向", "重新思考"],
                mutation_summary="blocked",
                turn=turn,
                action_kind=action_kind,
            )

        mutation_summary = mutation.get("summary", "")

        # Step 3: Render scene (fail-open: fallback to plain text)
        try:
            render_result = await self._render(raw_input, action, mutation_summary, context)
            scene_text = render_result.get("scene_text", "场景生成失败")
            suggested_actions = render_result.get("suggested_actions", [])
        except Exception as e:
            logger.warning("Scene rendering failed: %s", e)
            scene_text = f"场景渲染失败: {e}"
            suggested_actions = []

        # Step 4: Reconcile scene vs graph (optional, fail-open)
        try:
            supplement = await self._reconcile(mutation, scene_text, context)
            # Merge supplemental entities/edges into mutation
            if supplement.get("entities", {}).get("upsert"):
                mutation["entities"]["upsert"].extend(supplement["entities"]["upsert"])
            if supplement.get("edges", {}).get("upsert"):
                mutation["edges"]["upsert"].extend(supplement["edges"]["upsert"])
        except Exception as e:
            logger.debug("Reconciliation failed (non-critical): %s", e)

        return TurnResult(
            scene_text=scene_text,
            suggested_actions=suggested_actions[:3],  # Max 3 suggestions
            mutation_summary=mutation_summary,
            turn=turn,
            action_kind=action_kind,
        )

    async def _interpret(self, raw_input: str, context: str) -> Dict[str, Any]:
        """Step 1: Normalize player input into structured action."""
        raise NotImplementedError("LLM integration pending — mock this for tests")

    async def _mutate(
        self, turn: int, raw_input: str, action: Dict[str, Any], context: str
    ) -> Dict[str, Any]:
        """Step 2: Generate world state mutations from the action."""
        raise NotImplementedError("LLM integration pending — mock this for tests")

    async def _render(
        self, raw_input: str, action: Dict[str, Any], mutation_summary: str, state_brief: str
    ) -> Dict[str, Any]:
        """Step 3: Render scene text and suggested actions."""
        raise NotImplementedError("LLM integration pending — mock this for tests")

    async def _reconcile(
        self, mutation: Dict[str, Any], scene_text: str, state_brief: str
    ) -> Dict[str, Any]:
        """Step 4: Cross-check scene text against world graph, supplement missing entities."""
        raise NotImplementedError("LLM integration pending — mock this for tests")
