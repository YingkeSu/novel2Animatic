"""Tests for auth endpoints."""

import pytest
from httpx import AsyncClient
import warnings

from app.services.auth import hash_password, verify_password
from app.services.auth import create_access_token


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "testpassword123"
    })
    response = await client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "login@example.com",
        "password": "testpassword123"
    })
    response = await client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "email": "wrong@example.com",
        "password": "testpassword123"
    })
    response = await client.post("/api/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "testpassword123"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "email": "shortpass@example.com",
        "password": "123"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_rejects_invalid_email(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "email": "not-an-email",
        "password": "testpassword123"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_rejects_short_password(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "email": "shortpass@example.com",
        "password": "123"
    })
    assert response.status_code == 422


def test_password_hashing_roundtrip():
    hashed = hash_password("short-password")
    assert hashed != "short-password"
    assert verify_password("short-password", hashed) is True


def test_create_access_token_uses_timezone_aware_utc():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        token = create_access_token(1, "user")

    assert token
    assert not any("utcnow()" in str(item.message) for item in caught)
