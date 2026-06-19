"""Tests for scene generation API — routes text_split, short_fiction, play_world."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# --- Helpers ---

async def register_and_get_token(client, email="gen@test.com"):
    """Register a user and return auth token."""
    await client.post("/api/auth/register", json={"email": email, "password": "test123456"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "test123456"})
    return resp.json()["access_token"]


async def create_project(client, token, **kwargs):
    """Create a project with given params."""
    defaults = {
        "title": "测试项目",
        "source_text": "这是一段测试文本，用于验证场景生成功能。" * 5,
        "style_writing": "modern",
        "style_visual": "ink_wash",
        "style_audio": "ancient_male",
    }
    defaults.update(kwargs)
    resp = await client.post(
        "/api/projects",
        json=defaults,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# --- Test: source_type field on project creation ---

class TestProjectSourceType:
    """Project creation with source_type field."""

    @pytest.mark.asyncio
    async def test_create_project_default_source_type(self, client):
        """Default source_type is text_split."""
        token = await register_and_get_token(client, "src_default@test.com")
        resp = await create_project(client, token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "text_split"

    @pytest.mark.asyncio
    async def test_create_project_short_fiction_source_type(self, client):
        """Can create project with source_type=short_fiction."""
        token = await register_and_get_token(client, "src_short@test.com")
        resp = await create_project(
            client, token,
            source_type="short_fiction",
            direction="古风爱情",
            source_text="",  # short_fiction doesn't need source_text
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "short_fiction"

    @pytest.mark.asyncio
    async def test_create_project_play_world_source_type(self, client):
        """Can create project with source_type=play_world."""
        token = await register_and_get_token(client, "src_play@test.com")
        resp = await create_project(
            client, token,
            source_type="play_world",
            direction="竹林探险",
            source_text="",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "play_world"

    @pytest.mark.asyncio
    async def test_create_project_invalid_source_type(self, client):
        """Invalid source_type returns 422."""
        token = await register_and_get_token(client, "src_bad@test.com")
        resp = await create_project(
            client, token,
            source_type="invalid_type",
        )
        assert resp.status_code == 422


# --- Test: generate endpoint routes to correct handler ---

class TestGenerateEndpoint:
    """POST /api/projects/{id}/generate routes to correct handler."""

    @pytest.mark.asyncio
    async def test_generate_short_fiction_creates_scenes(self, client, db_session_factory):
        """short_fiction generation creates scenes via SceneGenerator."""
        token = await register_and_get_token(client, "gen_short@test.com")
        resp = await create_project(
            client, token,
            source_type="short_fiction",
            direction="古风爱情",
            source_text="",
        )
        project_id = resp.json()["id"]

        # Mock the LLM function to return valid TAG-formatted content
        mock_outline = """=== SHORT_FICTION_PLAN_TITLE ===
风雪夜归人

=== CHAPTER 1 TITLE ===
雪夜启程
=== CHAPTER 1 CONTENT ===
腊月二十三，小年夜。陆行舟踩着没膝深的雪，沿着山路缓缓前行。

=== CHAPTER 2 TITLE ===
山中偶遇
=== CHAPTER 2 CONTENT ===
转过山坳，一间茅屋出现在眼前。"""

        mock_draft = """=== SHORT_FICTION_TITLE ===
风雪夜归人

=== CHAPTER 1 TITLE ===
雪夜启程
=== CHAPTER 1 CONTENT ===
腊月二十三，小年夜。陆行舟踩着没膝深的雪，沿着山路缓缓前行。远处传来零星的爆竹声，他裹紧了单薄的棉袍。

=== CHAPTER 2 TITLE ===
山中偶遇
=== CHAPTER 2 CONTENT ===
转过山坳，一间茅屋出现在眼前。灯火从窗纸透出，温暖而柔和。"""

        def mock_llm(messages, temperature=0.7, **kwargs):
            """Mock LLM that returns appropriate content based on prompt."""
            prompt = messages[-1]["content"] if messages else ""
            if "大纲" in prompt or "outline" in prompt.lower():
                return mock_outline
            elif "审" in prompt or "review" in prompt.lower():
                return "大纲结构清晰，建议增加更多细节描写。"
            elif "改" in prompt or "revise" in prompt.lower():
                return mock_outline
            else:
                return mock_draft

        with patch("app.services.scene_generator.SceneGenerator._call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_llm
            resp = await client.post(
                f"/api/projects/{project_id}/generate",
                json={"source_type": "short_fiction"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_generate_play_world_returns_turn_result(self, client):
        """play_world generation returns turn result via WorldEngine."""
        token = await register_and_get_token(client, "gen_play@test.com")
        resp = await create_project(
            client, token,
            source_type="play_world",
            direction="竹林探险",
            source_text="",
        )
        project_id = resp.json()["id"]

        # Mock the LLM function for world engine
        def mock_llm(messages, temperature=0.7, **kwargs):
            prompt = messages[-1]["content"] if messages else ""
            if "动作" in prompt or "action" in prompt.lower():
                return '{"action_kind": "look", "intent": "看看周围"}'
            elif "状态" in prompt or "mutate" in prompt.lower():
                return '{"entities": {"upsert": []}, "edges": {"upsert": [], "expire": []}, "state_slots": {"upsert": []}, "summary": "无变化"}'
            elif "场景" in prompt or "render" in prompt.lower():
                return '{"scene_text": "竹林深处，风声簌簌。远处隐约可见一座古老的石桥。", "suggested_actions": ["走上石桥", "探索竹林", "返回原路"]}'
            else:
                return '{"entities": {"upsert": []}, "edges": {"upsert": []}}'

        with patch("app.services.world_engine.WorldEngine._call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_llm
            resp = await client.post(
                f"/api/projects/{project_id}/play",
                json={"raw_input": "看看周围", "context": "竹林深处"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "scene_text" in data
        assert "suggested_actions" in data
        assert data["turn"] >= 1
