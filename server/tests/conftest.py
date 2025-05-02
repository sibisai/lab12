# tests/conftest.py
import os
import pytest_asyncio
from db import engine
import server.models as models

# Ensure environment variables for testing are set early
os.environ.setdefault("INITIAL_AUTH_SECRET", "testsecret")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("OPENAI_API_KEY", "dummy_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("RATE_LIMIT_SUMMARIZE_MINUTE", "5/minute")
os.environ.setdefault("RATE_LIMIT_SUMMARIZE_DAY", "100/day")

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """
    Create all tables before any tests run, and drop them after all tests complete.
    """
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
