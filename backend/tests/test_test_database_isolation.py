"""Regression tests for database isolation in test fixtures."""

import pytest


@pytest.mark.asyncio
async def test_client_factory_isolates_concurrent_database_lifetimes(client_factory):
    async with client_factory() as first, client_factory() as second:
        response = await first.post(
            "/api/auth/register",
            json={"email": "same@example.com", "password": "testpassword123"},
        )
        assert response.status_code == 200

        response = await second.post(
            "/api/auth/register",
            json={"email": "same@example.com", "password": "testpassword123"},
        )
        assert response.status_code == 200

    async with client_factory() as first, client_factory() as second:
        response = await first.post(
            "/api/auth/register",
            json={"email": "closed@example.com", "password": "testpassword123"},
        )
        assert response.status_code == 200

        await first.aclose()

        response = await second.post(
            "/api/auth/register",
            json={"email": "still-open@example.com", "password": "testpassword123"},
        )
        assert response.status_code == 200
