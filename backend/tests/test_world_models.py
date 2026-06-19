"""Tests for open world engine data models."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.world import (
    World, WorldEntity, WorldEdge, WorldStateSlot, WorldEvent
)


class TestWorldModel:
    """World 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_world_create(self, test_db_context):
        """创建 World 记录。"""
        async with test_db_context.session_factory() as session:
            world = World(
                project_id=None,
                title="江湖风云",
                premise="一个武侠世界的冒险故事",
                world_contract="角色不会突然死亡",
                visual_contract="水墨风格",
                mode="open",
                language="zh",
            )
            session.add(world)
            await session.commit()
            await session.refresh(world)

            assert world.id is not None
            assert world.title == "江湖风云"
            assert world.mode == "open"
            assert world.language == "zh"

    @pytest.mark.asyncio
    async def test_world_default_values(self, test_db_context):
        """World 默认值正确。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test World", premise="Test premise")
            session.add(world)
            await session.commit()
            await session.refresh(world)

            assert world.mode == "open"
            assert world.language == "zh"
            assert world.world_contract == ""
            assert world.visual_contract == ""


class TestWorldEntity:
    """WorldEntity 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_entity_create(self, test_db_context):
        """创建 WorldEntity 记录。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            entity = WorldEntity(
                world_id=world.id,
                entity_id="actor_player",
                type="actor",
                label="玩家",
                summary="主角",
                status="活跃",
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)

            assert entity.id is not None
            assert entity.entity_id == "actor_player"
            assert entity.type == "actor"

    @pytest.mark.asyncio
    async def test_entity_query_by_type(self, test_db_context):
        """按 type 查询实体。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            session.add(WorldEntity(
                world_id=world.id, entity_id="actor_1", type="actor",
                label="Player", summary="Main character", status="active"
            ))
            session.add(WorldEntity(
                world_id=world.id, entity_id="loc_1", type="location",
                label="Forest", summary="Dark forest", status="known"
            ))
            session.add(WorldEntity(
                world_id=world.id, entity_id="item_1", type="item",
                label="Sword", summary="Magic sword", status="owned"
            ))
            await session.commit()

        async with test_db_context.session_factory() as session:
            result = await session.execute(
                select(WorldEntity).where(
                    WorldEntity.world_id == world.id,
                    WorldEntity.type == "actor"
                )
            )
            actors = result.scalars().all()
            assert len(actors) == 1
            assert actors[0].entity_id == "actor_1"


class TestWorldEdge:
    """WorldEdge 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_edge_create(self, test_db_context):
        """创建 WorldEdge 记录。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            e1 = WorldEntity(
                world_id=world.id, entity_id="actor_1", type="actor",
                label="Player", summary="Main", status="active"
            )
            e2 = WorldEntity(
                world_id=world.id, entity_id="actor_2", type="actor",
                label="NPC", summary="Friend", status="active"
            )
            session.add_all([e1, e2])
            await session.flush()

            edge = WorldEdge(
                world_id=world.id,
                from_entity_id=e1.id,
                to_entity_id=e2.id,
                type="ally",
                value_json='{"role": "relation"}',
                valid_from_event="evt-1",
                valid_until_event=None,
            )
            session.add(edge)
            await session.commit()
            await session.refresh(edge)

            assert edge.id is not None
            assert edge.type == "ally"
            assert edge.valid_until_event is None

    @pytest.mark.asyncio
    async def test_edge_soft_delete(self, test_db_context):
        """Edge 软删除（设置 valid_until_event）。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            e1 = WorldEntity(
                world_id=world.id, entity_id="actor_1", type="actor",
                label="Player", summary="Main", status="active"
            )
            e2 = WorldEntity(
                world_id=world.id, entity_id="actor_2", type="actor",
                label="NPC", summary="Friend", status="active"
            )
            session.add_all([e1, e2])
            await session.flush()

            edge = WorldEdge(
                world_id=world.id,
                from_entity_id=e1.id,
                to_entity_id=e2.id,
                type="ally",
                value_json='{}',
                valid_from_event="evt-1",
            )
            session.add(edge)
            await session.commit()
            await session.refresh(edge)
            edge_id = edge.id

        # Soft delete
        async with test_db_context.session_factory() as session:
            edge = await session.get(WorldEdge, edge_id)
            edge.valid_until_event = "evt-5"
            await session.commit()

        # Query only active edges
        async with test_db_context.session_factory() as session:
            result = await session.execute(
                select(WorldEdge).where(
                    WorldEdge.world_id == world.id,
                    WorldEdge.valid_until_event.is_(None),
                )
            )
            active_edges = result.scalars().all()
            assert len(active_edges) == 0


class TestWorldStateSlot:
    """WorldStateSlot 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_state_slot_create(self, test_db_context):
        """创建 WorldStateSlot 记录。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            entity = WorldEntity(
                world_id=world.id, entity_id="actor_1", type="actor",
                label="Player", summary="Main", status="active"
            )
            session.add(entity)
            await session.flush()

            slot = WorldStateSlot(
                world_id=world.id,
                owner_entity_id=entity.id,
                kind="resource",
                label="health",
                value_json='"100"',
                updated_event="evt-1",
            )
            session.add(slot)
            await session.commit()
            await session.refresh(slot)

            assert slot.id is not None
            assert slot.kind == "resource"
            assert slot.label == "health"

    @pytest.mark.asyncio
    async def test_state_slot_query_by_kind(self, test_db_context):
        """按 kind 查询状态槽。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            session.add(WorldStateSlot(
                world_id=world.id, kind="resource", label="health",
                value_json='"100"', updated_event="evt-1"
            ))
            session.add(WorldStateSlot(
                world_id=world.id, kind="pressure", label="danger",
                value_json='"high"', updated_event="evt-1"
            ))
            session.add(WorldStateSlot(
                world_id=world.id, kind="resource", label="mana",
                value_json='"50"', updated_event="evt-1"
            ))
            await session.commit()

        async with test_db_context.session_factory() as session:
            result = await session.execute(
                select(WorldStateSlot).where(
                    WorldStateSlot.world_id == world.id,
                    WorldStateSlot.kind == "resource",
                )
            )
            resources = result.scalars().all()
            assert len(resources) == 2


class TestWorldEvent:
    """WorldEvent 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_event_create(self, test_db_context):
        """创建 WorldEvent 记录。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            event = WorldEvent(
                world_id=world.id,
                turn=1,
                action_kind="look",
                raw_input="看看周围",
                outcome_summary="你环顾四周，发现自己在一片竹林中",
                time_advance_json='{"elapsed": "几息", "anchor": "清晨"}',
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            assert event.id is not None
            assert event.turn == 1
            assert event.action_kind == "look"

    @pytest.mark.asyncio
    async def test_events_order_by_turn(self, test_db_context):
        """事件按 turn 排序。"""
        async with test_db_context.session_factory() as session:
            world = World(title="Test", premise="Test premise")
            session.add(world)
            await session.flush()

            for turn in [3, 1, 2]:
                session.add(WorldEvent(
                    world_id=world.id, turn=turn,
                    action_kind="do", raw_input=f"action {turn}",
                    outcome_summary=f"result {turn}",
                ))
            await session.commit()

        async with test_db_context.session_factory() as session:
            result = await session.execute(
                select(WorldEvent)
                .where(WorldEvent.world_id == world.id)
                .order_by(WorldEvent.turn)
            )
            events = result.scalars().all()
            assert [e.turn for e in events] == [1, 2, 3]
