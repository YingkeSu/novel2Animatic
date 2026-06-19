"""Tests for open world engine — 4-step turn pipeline."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.world_engine import WorldEngine, TurnResult


class TestWorldEngine:
    """世界引擎核心测试。"""

    def test_engine_instantiation(self):
        """引擎可实例化。"""
        engine = WorldEngine()
        assert engine is not None

    def test_turn_result_structure(self):
        """TurnResult 包含必要字段。"""
        result = TurnResult(
            scene_text="你环顾四周，发现自己在一片竹林中",
            suggested_actions=["继续探索", "寻找水源", "原地休息"],
            mutation_summary="新增 1 个实体，更新 2 条边",
            turn=1,
            action_kind="look",
        )
        assert result.turn == 1
        assert result.action_kind == "look"
        assert len(result.suggested_actions) == 3

    @pytest.mark.asyncio
    async def test_step_calls_agents_in_order(self):
        """step 调用 4 个 agent 按正确顺序。"""
        engine = WorldEngine()
        call_order = []

        async def mock_interpret(raw_input, context):
            call_order.append("interpret")
            return {"action_kind": "look", "intent": "看看周围"}

        async def mock_mutate(turn, raw_input, action, context):
            call_order.append("mutate")
            return {
                "entities": {"upsert": []},
                "edges": {"upsert": [], "expire": []},
                "state_slots": {"upsert": []},
                "blocked": False,
                "summary": "无变化",
            }

        async def mock_render(raw_input, action, mutation_summary, state_brief):
            call_order.append("render")
            return {
                "scene_text": "你环顾四周，发现自己在一片竹林中。",
                "suggested_actions": ["探索竹林", "寻找出路"],
            }

        async def mock_reconcile(mutation, scene_text, state_brief):
            call_order.append("reconcile")
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}}

        engine._interpret = mock_interpret
        engine._mutate = mock_mutate
        engine._render = mock_render
        engine._reconcile = mock_reconcile

        result = await engine.step(
            world_id=1,
            turn=1,
            raw_input="看看周围",
            context="竹林深处",
        )

        assert call_order == ["interpret", "mutate", "render", "reconcile"]
        assert result.scene_text == "你环顾四周，发现自己在一片竹林中。"
        assert result.turn == 1

    @pytest.mark.asyncio
    async def test_step_returns_suggested_actions(self):
        """step 返回建议动作列表。"""
        engine = WorldEngine()

        async def mock_interpret(raw_input, context):
            return {"action_kind": "look", "intent": "看看"}

        async def mock_mutate(turn, raw_input, action, context):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "blocked": False, "summary": ""}

        async def mock_render(raw_input, action, mutation_summary, state_brief):
            return {"scene_text": "场景文本", "suggested_actions": ["动作A", "动作B", "动作C"]}

        async def mock_reconcile(mutation, scene_text, state_brief):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}}

        engine._interpret = mock_interpret
        engine._mutate = mock_mutate
        engine._render = mock_render
        engine._reconcile = mock_reconcile

        result = await engine.step(world_id=1, turn=1, raw_input="看看", context="")
        assert len(result.suggested_actions) == 3

    @pytest.mark.asyncio
    async def test_step_handles_interpret_failure(self):
        """interpret 失败时降级为 do 动作。"""
        engine = WorldEngine()

        async def mock_interpret(raw_input, context):
            raise Exception("LLM 调用失败")

        async def mock_mutate(turn, raw_input, action, context):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "blocked": False, "summary": ""}

        async def mock_render(raw_input, action, mutation_summary, state_brief):
            return {"scene_text": "降级场景", "suggested_actions": []}

        async def mock_reconcile(mutation, scene_text, state_brief):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}}

        engine._interpret = mock_interpret
        engine._mutate = mock_mutate
        engine._render = mock_render
        engine._reconcile = mock_reconcile

        result = await engine.step(world_id=1, turn=1, raw_input="随便", context="")
        assert result.action_kind == "do"  # Fallback

    @pytest.mark.asyncio
    async def test_step_handles_mutate_blocked(self):
        """mutate 返回 blocked 时渲染提示场景。"""
        engine = WorldEngine()

        async def mock_interpret(raw_input, context):
            return {"action_kind": "do", "intent": "做某事"}

        async def mock_mutate(turn, raw_input, action, context):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "blocked": True, "blocked_reason": "你无法在这里做这件事", "summary": "blocked"}

        async def mock_render(raw_input, action, mutation_summary, state_brief):
            return {"scene_text": "你无法在这里做这件事。", "suggested_actions": ["换个方向"]}

        async def mock_reconcile(mutation, scene_text, state_brief):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}}

        engine._interpret = mock_interpret
        engine._mutate = mock_mutate
        engine._render = mock_render
        engine._reconcile = mock_reconcile

        result = await engine.step(world_id=1, turn=1, raw_input="做某事", context="")
        assert "无法" in result.scene_text

    @pytest.mark.asyncio
    async def test_step_scene_compatible_with_scene_model(self):
        """step 输出的场景兼容 Scene 模型。"""
        engine = WorldEngine()

        async def mock_interpret(raw_input, context):
            return {"action_kind": "look", "intent": "看"}

        async def mock_mutate(turn, raw_input, action, context):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "blocked": False, "summary": ""}

        async def mock_render(raw_input, action, mutation_summary, state_brief):
            return {"scene_text": "场景文本", "suggested_actions": []}

        async def mock_reconcile(mutation, scene_text, state_brief):
            return {"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}}

        engine._interpret = mock_interpret
        engine._mutate = mock_mutate
        engine._render = mock_render
        engine._reconcile = mock_reconcile

        result = await engine.step(world_id=1, turn=1, raw_input="看", context="")
        scene = result.to_scene_dict()
        assert scene["source_type"] == "play_world"
        assert "title" in scene
        assert "text" in scene
        assert "shot_type" in scene
        assert "narration" in scene


class TestWorldEngineDefaults:
    """默认配置测试。"""

    def test_action_interpreter_temperature(self):
        """Action Interpreter 使用低温度 (0.15)。"""
        engine = WorldEngine()
        assert engine.interpreter_temp == 0.15

    def test_world_mutator_temperature(self):
        """World Mutator 使用低温度 (0.25)。"""
        engine = WorldEngine()
        assert engine.mutator_temp == 0.25

    def test_scene_renderer_temperature(self):
        """Scene Renderer 使用中温度 (0.45)。"""
        engine = WorldEngine()
        assert engine.renderer_temp == 0.45

    def test_scene_reconciler_temperature(self):
        """Scene Reconciler 使用最低温度 (0.1)。"""
        engine = WorldEngine()
        assert engine.reconciler_temp == 0.1
