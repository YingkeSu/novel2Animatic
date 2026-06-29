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

    def __init__(self, llm_fn=None) -> None:
        self.llm_fn = llm_fn
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
            # Log the full exception server-side; never expose raw internals in
            # the narration that gets returned to the client via /play.
            logger.warning("Mutation failed for world %s: %r", world_id, e, exc_info=True)
            mutation = {
                "entities": {"upsert": []},
                "edges": {"upsert": [], "expire": []},
                "state_slots": {"upsert": []},
                "blocked": True,
                "blocked_reason": "模型输出无法解析",
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

    async def _call_llm(self, messages, temperature=0.7, **kwargs):
        """Call the LLM function."""
        if not self.llm_fn:
            raise RuntimeError("No llm_fn provided to WorldEngine")
        return await self.llm_fn(messages, temperature=temperature, **kwargs)

    async def _interpret(self, raw_input: str, context: str) -> Dict[str, Any]:
        """Step 1: Normalize player input into structured action."""
        messages = [
            {"role": "system", "content": "你是一个游戏动作解析器。将玩家输入解析为结构化动作。输出JSON格式：{\"action_kind\": \"look/say/move/do/wait\", \"intent\": \"意图描述\"}"},
            {"role": "user", "content": f"当前场景：{context}\n玩家输入：{raw_input}\n\n请解析为JSON："},
        ]
        result = await self._call_llm(messages, temperature=self.interpreter_temp)
        import json as _json
        try:
            return _json.loads(result)
        except _json.JSONDecodeError:
            return {"action_kind": "do", "intent": raw_input}

    async def _mutate(
        self, turn: int, raw_input: str, action: Dict[str, Any], context: str
    ) -> Dict[str, Any]:
        """Step 2: Generate world state mutations from the action."""
        import json as _json
        messages = [
            {"role": "system", "content": "你是一个世界状态管理器。根据玩家动作生成状态变化。输出JSON格式：{\"entities\": {\"upsert\": []}, \"edges\": {\"upsert\": [], \"expire\": []}, \"state_slots\": {\"upsert\": []}, \"summary\": \"变化摘要\"}"},
            {"role": "user", "content": f"回合：{turn}\n场景：{context}\n玩家动作：{action}\n\n请生成状态变化JSON："},
        ]
        result = await self._call_llm(messages, temperature=self.mutator_temp)
        try:
            return _json.loads(result)
        except _json.JSONDecodeError:
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "summary": result[:100]}

    async def _render(
        self, raw_input: str, action: Dict[str, Any], mutation_summary: str, state_brief: str
    ) -> Dict[str, Any]:
        """Step 3: Render scene text and suggested actions."""
        import json as _json
        messages = [
            {"role": "system", "content": "你是一个场景渲染器。根据动作和状态变化生成生动的场景描述。输出JSON格式：{\"scene_text\": \"场景描述\", \"suggested_actions\": [\"建议1\", \"建议2\", \"建议3\"]}"},
            {"role": "user", "content": f"场景：{state_brief}\n玩家动作：{action}\n状态变化：{mutation_summary}\n\n请渲染场景JSON："},
        ]
        result = await self._call_llm(messages, temperature=self.renderer_temp)
        try:
            return _json.loads(result)
        except _json.JSONDecodeError:
            return {"scene_text": result, "suggested_actions": ["继续探索", "查看四周", "休息"]}

    async def _reconcile(
        self, mutation: Dict[str, Any], scene_text: str, state_brief: str
    ) -> Dict[str, Any]:
        """Step 4: Cross-check scene text against world graph, supplement missing entities."""
        import json as _json
        messages = [
            {"role": "system", "content": "你是一个场景校验器。检查场景文本是否与世界状态一致，补充遗漏的实体。输出JSON格式：{\"entities\": {\"upsert\": []}, \"edges\": {\"upsert\": []}}"},
            {"role": "user", "content": f"世界状态：{state_brief}\n状态变化：{mutation}\n场景文本：{scene_text}\n\n请校验并补充JSON："},
        ]
        result = await self._call_llm(messages, temperature=self.reconciler_temp)
        try:
            return _json.loads(result)
        except _json.JSONDecodeError:
            return {"entities": {"upsert": []}, "edges": {"upsert": []}}
