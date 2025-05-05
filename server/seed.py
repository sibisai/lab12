import os
import asyncio
from dotenv import load_dotenv        # ← new
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from server.models import SubscriptionPlan, Role
from sqlalchemy.dialects.postgresql import insert

load_dotenv()                          # ← loads .env into os.environ
DATABASE_URL = os.getenv("DATABASE_URL")

DEFAULT_PLANS = [
    {"name": "free", "quota": 20,  "price": 0.00},
    {"name": "pro",  "quota": 100, "price": 4.99},
]
DEFAULT_ROLES = [
    {"name": "user"},
    {"name": "admin"},
]

async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # plans
        await conn.execute(
            insert(SubscriptionPlan)
            .values(DEFAULT_PLANS)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        # roles
        await conn.execute(
            insert(Role.__table__)
            .values(DEFAULT_ROLES)
            .on_conflict_do_nothing(index_elements=["name"])
        )
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())