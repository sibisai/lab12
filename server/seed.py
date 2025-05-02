from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from server.models import SubscriptionPlan

DEFAULT_PLANS = (
    {"name": "free", "quota": 20,  "price": 0.00},
    {"name": "pro",  "quota": 100, "price": 4.99},
)

async def seed_subscription_plans(db: AsyncSession) -> None:
    """Insert default plans once; ignores duplicates."""
    stmt = (
        insert(SubscriptionPlan)
        .values(DEFAULT_PLANS)
        .on_conflict_do_nothing(index_elements=["name"])
    )
    await db.execute(stmt)
    await db.commit()