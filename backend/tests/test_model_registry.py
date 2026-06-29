"""Tests for model service registry and preset system.

Covers issue #3 acceptance criteria: preset definitions, custom service
registration with base_url+api_key+api_format, encrypted API key storage
(at rest + masked in responses), and CRUD over the Service table.
"""

import pytest
from app.services.model_registry import (
    get_preset_services,
    get_service_presets_by_group,
    get_preset_by_id,
    build_service_from_preset,
    create_service,
    list_services,
    list_services_as_dicts,
    get_service,
    delete_service,
    ServicePreset,
)
from app.services import crypto


class TestServicePresets:
    """预设服务定义测试。"""

    def test_preset_services_exist(self):
        """预设服务列表非空。"""
        presets = get_preset_services()
        assert len(presets) > 0

    def test_stepfun_preset_exists(self):
        """StepFun 预设存在。"""
        presets = get_preset_services()
        stepfun = [p for p in presets if p.id == "stepfun"]
        assert len(stepfun) == 1
        assert stepfun[0].name == "StepFun"
        assert stepfun[0].group == "china"

    def test_openai_preset_exists(self):
        """OpenAI 预设存在。"""
        presets = get_preset_services()
        openai = [p for p in presets if p.id == "openai"]
        assert len(openai) == 1
        assert openai[0].group == "overseas"

    def test_deepseek_preset_exists(self):
        """DeepSeek 预设存在。"""
        presets = get_preset_services()
        deepseek = [p for p in presets if p.id == "deepseek"]
        assert len(deepseek) == 1
        assert deepseek[0].group == "china"

    def test_anthropic_preset_exists(self):
        """Anthropic 预设存在。"""
        presets = get_preset_services()
        anthropic = [p for p in presets if p.id == "anthropic"]
        assert len(anthropic) == 1
        assert anthropic[0].group == "overseas"

    def test_preset_has_required_fields(self):
        """每个预设都有必要字段。"""
        for preset in get_preset_services():
            assert preset.id, f"Preset missing id"
            assert preset.name, f"Preset {preset.id} missing name"
            assert preset.group in ("overseas", "china", "aggregator", "custom"), \
                f"Preset {preset.id} has invalid group: {preset.group}"
            assert preset.base_url, f"Preset {preset.id} missing base_url"
            assert preset.api_format in ("openai_chat", "openai_responses", "anthropic"), \
                f"Preset {preset.id} has invalid api_format: {preset.api_format}"
            assert len(preset.models) > 0, f"Preset {preset.id} has no models"

    def test_filter_by_group(self):
        """按分组过滤预设。"""
        china = get_service_presets_by_group("china")
        assert all(p.group == "china" for p in china)
        assert len(china) >= 2  # StepFun + DeepSeek

        overseas = get_service_presets_by_group("overseas")
        assert all(p.group == "overseas" for p in overseas)
        assert len(overseas) >= 2  # OpenAI + Anthropic

    def test_build_service_from_preset(self):
        """从预设构建服务配置。"""
        preset = get_service_presets_by_group("china")[0]
        service = build_service_from_preset(preset, api_key="test-key")
        assert service.name == preset.name
        assert service.base_url == preset.base_url
        assert service.api_key == "test-key"
        assert service.api_format == preset.api_format


class TestServicePresetData:
    """预设数据完整性测试。"""

    def test_stepfun_default_models(self):
        """StepFun 默认模型包含 step-3.7-flash。"""
        presets = get_preset_services()
        stepfun = next(p for p in presets if p.id == "stepfun")
        assert "step-3.7-flash" in stepfun.models

    def test_openai_default_models(self):
        """OpenAI 默认模型包含 gpt-4o。"""
        presets = get_preset_services()
        openai = next(p for p in presets if p.id == "openai")
        assert "gpt-4o" in openai.models

    def test_deepseek_default_models(self):
        """DeepSeek 默认模型包含 deepseek-chat。"""
        presets = get_preset_services()
        deepseek = next(p for p in presets if p.id == "deepseek")
        assert "deepseek-chat" in deepseek.models

    def test_stepfun_base_url(self):
        """StepFun base_url 正确。"""
        presets = get_preset_services()
        stepfun = next(p for p in presets if p.id == "stepfun")
        assert "stepfun.com" in stepfun.base_url

    def test_preset_temperature_defaults(self):
        """预设有合理的默认温度。"""
        for preset in get_service_presets_by_group("china"):
            if preset.default_temperature is not None:
                assert 0 <= preset.default_temperature <= 2


# ── Encryption (issue #3: API Key 加密存储) ─────────────────────────

class TestApiKeyEncryption:
    """API Key 加密/解密/脱敏。"""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "sk-test-1234567890abcdef"
        enc = crypto.encrypt_api_key(plaintext)
        assert enc != plaintext
        assert crypto.decrypt_api_key(enc) == plaintext

    def test_encryption_key_not_stored_plaintext(self):
        """加密后的密文不能包含明文。"""
        enc = crypto.encrypt_api_key("sk-super-secret")
        assert "sk-super-secret" not in enc

    def test_mask_key_short(self):
        assert crypto.mask_key("") == ""
        # short keys: keep a small prefix, mask the rest, never reveal full
        masked = crypto.mask_key("sk-1234")
        assert masked != "sk-1234"
        assert "*" in masked

    def test_mask_key_long(self):
        masked = crypto.mask_key("sk-1234567890abcdef")
        assert masked != "sk-1234567890abcdef"
        assert "*" in masked


# ── CRUD over Service table ─────────────────────────────────────────

class TestServiceCRUD:
    """注册中心对 Service 表的 CRUD。"""

    @pytest.mark.asyncio
    async def test_create_custom_service_encrypts_key(self, db_session_factory):
        async with db_session_factory() as db:
            svc = await create_service(
                db,
                name="My Local LLM",
                group="custom",
                base_url="http://localhost:11434/v1",
                api_key="ollama-no-key",
                api_format="openai_chat",
                models=["llama3"],
            )
            assert svc.id is not None
            assert svc.is_preset is False
            assert svc.group == "custom"
            # api_key must be stored encrypted, not plaintext
            assert svc.api_key_encrypted != "ollama-no-key"
            assert crypto.decrypt_api_key(svc.api_key_encrypted) == "ollama-no-key"

    @pytest.mark.asyncio
    async def test_list_services(self, db_session_factory):
        async with db_session_factory() as db:
            svc = await create_service(
                db, name="A", group="custom",
                base_url="https://api.a.com/v1", api_key="sk-a",
                api_format="openai_chat",
            )
            services = await list_services(db)
            assert any(s.id == svc.id for s in services)

    @pytest.mark.asyncio
    async def test_get_and_delete_service(self, db_session_factory):
        async with db_session_factory() as db:
            svc = await create_service(
                db, name="Temp", group="custom",
                base_url="https://api.example.com/v1", api_key="sk-tmp",
                api_format="openai_chat",
            )
            fetched = await get_service(db, svc.id)
            assert fetched is not None
            assert fetched.name == "Temp"

            await delete_service(db, svc.id)
            assert await get_service(db, svc.id) is None

    @pytest.mark.asyncio
    async def test_list_as_dicts_masks_key(self, db_session_factory):
        async with db_session_factory() as db:
            await create_service(
                db, name="Masked", group="custom",
                base_url="https://api.example.com/v1", api_key="sk-1234567890abcdef",
                api_format="openai_chat",
            )
            rows = await list_services_as_dicts(db)
            assert len(rows) == 1
            assert rows[0]["api_key_masked"] != "sk-1234567890abcdef"
            assert "*" in rows[0]["api_key_masked"]
            # encrypted blob / plaintext must not leak
            assert "api_key_encrypted" not in rows[0]


# ── REST API ────────────────────────────────────────────────────────

async def _register_and_login(client):
    """注册并登录，返回带 Bearer token 的请求头。"""
    res = await client.post("/api/auth/register", json={
        "email": "svc-test@example.com",
        "password": "password123",
    })
    if res.status_code == 409:
        res = await client.post("/api/auth/login", json={
            "email": "svc-test@example.com",
            "password": "password123",
        })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestServicesRouter:
    """REST API: POST/GET/DELETE /api/services。"""

    @pytest.mark.asyncio
    async def test_create_get_delete_custom_service(self, client):
        headers = await _register_and_login(client)

        res = await client.post("/api/services", headers=headers, json={
            "name": "My Custom Endpoint",
            "group": "custom",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-custom-secret-key",
            "api_format": "openai_chat",
            "models": ["gpt-4o"],
        })
        assert res.status_code == 200, res.text
        created = res.json()
        assert created["name"] == "My Custom Endpoint"
        assert created["group"] == "custom"
        # masked key returned, never plaintext
        assert created["api_key"] != "sk-custom-secret-key"
        assert "*" in created["api_key"]
        svc_id = created["id"]

        # GET list
        res = await client.get("/api/services", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert any(s["id"] == svc_id for s in items)
        for s in items:
            assert s.get("api_key") != "sk-custom-secret-key"

        # GET single
        res = await client.get(f"/api/services/{svc_id}", headers=headers)
        assert res.status_code == 200

        # DELETE
        res = await client.delete(f"/api/services/{svc_id}", headers=headers)
        assert res.status_code == 200
        res = await client.get(f"/api/services/{svc_id}", headers=headers)
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_create_from_preset(self, client):
        headers = await _register_and_login(client)
        res = await client.post("/api/services", headers=headers, json={
            "preset_id": "openai",
            "api_key": "sk-openai-real-key-12345",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["is_preset"] is True
        assert body["name"] == "OpenAI"
        assert body["base_url"] == "https://api.openai.com/v1"
        assert "sk-openai-real-key-12345" not in body["api_key"]

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        res = await client.post("/api/services", json={
            "name": "x", "group": "custom", "base_url": "https://e.com/v1",
            "api_key": "sk", "api_format": "openai_chat",
        })
        assert res.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_invalid_api_format_rejected(self, client):
        headers = await _register_and_login(client)
        res = await client.post("/api/services", headers=headers, json={
            "name": "bad", "group": "custom", "base_url": "https://e.com/v1",
            "api_key": "sk", "api_format": "not-a-real-format",
        })
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_preset_rejected(self, client):
        headers = await _register_and_login(client)
        res = await client.post("/api/services", headers=headers, json={
            "preset_id": "no-such-preset", "api_key": "sk",
        })
        assert res.status_code == 404
