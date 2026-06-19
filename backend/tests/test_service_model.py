"""Tests for Service SQLAlchemy model and CRUD operations."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.service import Service


class TestServiceModel:
    """Service 数据模型测试。"""

    @pytest.mark.asyncio
    async def test_service_create(self, test_db_context):
        """创建 Service 记录。"""
        async with test_db_context.session_factory() as session:
            service = Service(
                name="StepFun",
                group="china",
                base_url="https://api.stepfun.com/v1",
                api_key_encrypted="encrypted-key",
                api_format="openai_chat",
                models_json='["step-3.7-flash"]',
                config_json='{"default_temperature": 0.7}',
            )
            session.add(service)
            await session.commit()
            await session.refresh(service)

            assert service.id is not None
            assert service.name == "StepFun"
            assert service.group == "china"

    @pytest.mark.asyncio
    async def test_service_list(self, test_db_context):
        """列出所有 Service。"""
        async with test_db_context.session_factory() as session:
            session.add(Service(
                name="Service A",
                group="china",
                base_url="https://a.example.com",
                api_key_encrypted="key-a",
                api_format="openai_chat",
                models_json="[]",
            ))
            session.add(Service(
                name="Service B",
                group="overseas",
                base_url="https://b.example.com",
                api_key_encrypted="key-b",
                api_format="openai_chat",
                models_json="[]",
            ))
            await session.commit()

        async with test_db_context.session_factory() as session:
            result = await session.execute(select(Service))
            services = result.scalars().all()
            assert len(services) == 2

    @pytest.mark.asyncio
    async def test_service_delete(self, test_db_context):
        """删除 Service。"""
        async with test_db_context.session_factory() as session:
            service = Service(
                name="ToDelete",
                group="custom",
                base_url="https://delete.me",
                api_key_encrypted="key",
                api_format="openai_chat",
                models_json="[]",
            )
            session.add(service)
            await session.commit()
            await session.refresh(service)
            service_id = service.id

        async with test_db_context.session_factory() as session:
            service = await session.get(Service, service_id)
            await session.delete(service)
            await session.commit()

        async with test_db_context.session_factory() as session:
            service = await session.get(Service, service_id)
            assert service is None
