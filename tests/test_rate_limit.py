# tests/test_rate_limit.py
import os, importlib
# same in-memory sqlite override + other env
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["INITIAL_AUTH_SECRET"] = "testsecret"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["RATE_LIMIT_SUMMARIZE_MINUTE"] = "5/minute"
os.environ["RATE_LIMIT_SUMMARIZE_DAY"] = "100/day"
import db; importlib.reload(db)
import main; importlib.reload(main)

from main import app
import pytest_asyncio, pytest, asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import status

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def auth_token(client):
    # register + login
    await client.post("/register", data={"username": "rluser", "password": "rlpw"})
    resp = await client.post("/token", data={"username": "rluser", "password": "rlpw"})
    return resp.json()["access_token"]

@pytest.mark.asyncio
async def test_summarize_rate_limit_minute(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {"text": "rate-limit test"}

    # first 5 calls are either 500 (dummy key) or 200
    for _ in range(5):
        r = await client.post("/summarize", json=payload, headers=headers)
        assert r.status_code in (status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_200_OK)
        # tiny pause so our rate limiter clock can tick
        await asyncio.sleep(0.01)

    # the 6th within the same minute should be 429
    r = await client.post("/summarize", json=payload, headers=headers)
    assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Rate limit" in r.json()["detail"]