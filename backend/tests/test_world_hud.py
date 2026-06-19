"""Tests for open world HUD data query API."""

import pytest
from app.services.world_hud import WorldHUD, HUDData


class TestWorldHUD:
    """HUD 数据查询测试。"""

    def test_hud_data_structure(self):
        """HUDData 包含必要字段。"""
        data = HUDData(
            entities=[{"id": 1, "type": "actor", "label": "玩家"}],
            relations=[{"from": "玩家", "to": "NPC", "type": "ally"}],
            holdings=[{"holder": "玩家", "item": "剑"}],
            state_slots={"resource": [{"label": "health", "value": "100"}]},
            evidence_lifecycle=[],
            current_scene="你站在竹林中",
            turn=1,
        )
        assert data.turn == 1
        assert len(data.entities) == 1
        assert data.current_scene == "你站在竹林中"

    def test_hud_data_empty(self):
        """空 HUD 数据。"""
        data = HUDData.empty()
        assert data.entities == []
        assert data.relations == []
        assert data.turn == 0

    def test_hud_format_for_frontend(self):
        """HUD 数据可序列化为前端格式。"""
        data = HUDData(
            entities=[],
            relations=[],
            holdings=[],
            state_slots={},
            evidence_lifecycle=[],
            current_scene="",
            turn=0,
        )
        d = data.to_dict()
        assert "entities" in d
        assert "relations" in d
        assert "holdings" in d
        assert "state_slots" in d
        assert "evidence_lifecycle" in d
        assert "current_scene" in d
        assert "turn" in d
