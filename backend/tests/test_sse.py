"""Tests for SSE (Server-Sent Events) real-time push."""

import asyncio
import pytest
from app.services.event_bus import EventBus, EventType


class TestEventBus:
    """内存事件总线测试。"""

    def test_event_bus_singleton(self):
        """event_bus 单例可访问。"""
        from app.services.event_bus import event_bus
        assert event_bus is not None

    def test_subscribe_returns_queue(self):
        """subscribe 返回可迭代的队列。"""
        bus = EventBus()
        queue = bus.subscribe("project-1")
        assert queue is not None

    @pytest.mark.asyncio
    async def test_publish_received_by_subscriber(self):
        """publish 的事件被 subscriber 收到。"""
        bus = EventBus()
        queue = bus.subscribe("project-1")
        await bus.publish("project-1", "progress", {"step": 1, "progress": 50})
        assert not queue.empty()
        event = queue.get_nowait()
        assert event.type == "progress"
        assert event.data["progress"] == 50

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """多个 subscriber 各自收到事件。"""
        bus = EventBus()
        q1 = bus.subscribe("proj-1")
        q2 = bus.subscribe("proj-1")
        await bus.publish("proj-1", "complete", {})
        assert not q1.empty()
        assert not q2.empty()

    @pytest.mark.asyncio
    async def test_different_projects_isolated(self):
        """不同 project 的事件互不干扰。"""
        bus = EventBus()
        q1 = bus.subscribe("proj-a")
        q2 = bus.subscribe("proj-b")
        await bus.publish("proj-a", "progress", {"step": 1})
        assert not q1.empty()
        assert q2.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_events(self):
        """取消订阅后不再收到事件。"""
        bus = EventBus()
        q = bus.subscribe("proj-1")
        bus.unsubscribe("proj-1", q)
        await bus.publish("proj-1", "progress", {})
        assert q.empty()

    def test_event_types(self):
        """支持的事件类型。"""
        from app.services.event_bus import SUPPORTED_EVENT_TYPES
        assert "progress" in SUPPORTED_EVENT_TYPES
        assert "scene_update" in SUPPORTED_EVENT_TYPES
        assert "error" in SUPPORTED_EVENT_TYPES
        assert "complete" in SUPPORTED_EVENT_TYPES
        assert "tool_execution" in SUPPORTED_EVENT_TYPES

    @pytest.mark.asyncio
    async def test_publish_returns_subscriber_count(self):
        """publish 返回收到事件的订阅者数量。"""
        bus = EventBus()
        bus.subscribe("proj-1")
        bus.subscribe("proj-1")
        count = await bus.publish("proj-1", "progress", {})
        assert count == 2

    @pytest.mark.asyncio
    async def test_stream_events_generator(self):
        """stream_events 异步生成器正确产出事件。"""
        bus = EventBus()
        queue = bus.subscribe("proj-1")

        # 发布事件
        await bus.publish("proj-1", "progress", {"step": 1})

        # 获取一个事件
        async for event in bus.stream_events("proj-1", queue):
            assert event.type == "progress"
            break  # 只取第一个


class TestSSEEndpoint:
    """SSE 路由基本测试（不需要实际 HTTP）。"""

    def test_router_importable(self):
        """事件路由可导入。"""
        from app.routers.events import router
        assert router is not None

    def test_router_has_events_route(self):
        """路由包含 /{project_id}/events 端点。"""
        from app.routers.events import router
        routes = [r.path for r in router.routes]
        assert "/{project_id}/events" in routes or "/api/projects/{project_id}/events" in routes
