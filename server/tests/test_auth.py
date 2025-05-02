# tests/test_auth.py
import os, importlib
# 1) force in-memory sqlite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["INITIAL_AUTH_SECRET"] = "testsecret"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing"
os.environ["REDIS_URL"] = "redis://localhost:6379"
# reload both modules so they pick up the new DATABASE_URL
import db; importlib.reload(db)
import server.main as main; importlib.reload(main)

from server.main import app
import pytest_asyncio, pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_token_success(client):
    # register the user first
    await client.post("/register", data={"username": "userA", "password": "testsecret"})
    resp = await client.post("/token", data={"username": "userA", "password": "testsecret"})
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_get_token_failure_wrong_secret(client):
    await client.post("/register", data={"username": "userB", "password": "testsecret"})
    resp = await client.post("/token", data={"username": "userB", "password": "wrong"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_access_protected_endpoint_no_token(client):
    resp = await client.post("/summarize", json={"text": "hello"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_access_protected_endpoint_invalid_token(client):
    resp = await client.post(
        "/summarize",
        json={"text": "hello"},
        headers={"Authorization": "Bearer totallyinvalid"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_access_protected_endpoint_valid_token(client):
    # register + get a valid token
    await client.post("/register", data={"username": "userC", "password": "pw"})
    tok = (await client.post("/token", data={"username": "userC", "password": "pw"})).json()["access_token"]

    # call summarize → with dummy OpenAI key you get a 500, but that's OK
    resp = await client.post(
        "/summarize",
        json={"text": "hello world"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code in (status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_429_TOO_MANY_REQUESTS)

@pytest.mark.asyncio
async def test_websocket_requires_and_rejects_and_accepts(client):
    # no token → connect should fail
    with pytest.raises(Exception):
        await client.websocket_connect("/ws/stt")

    # register + get token
    await client.post("/register", data={"username": "wsuser", "password": "wspw"})
    tok = (await client.post("/token", data={"username": "wsuser", "password": "wspw"})).json()["access_token"]

    # bad token → fail
    with pytest.raises(Exception):
        await client.websocket_connect(f"/ws/stt?token=bad")

    # good token → should open, then immediately error because model not loaded
    ws = await client.websocket_connect(f"/ws/stt?token={tok}")
    msg = await ws.receive_json()
    assert "error" in msg
    await ws.close()