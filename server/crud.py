"""
server/crud.py
Asynchronous helper functions for DB access.
"""

import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from server.models import (
    User,
    user_roles,
    UserFeedback,
    SummarizeCall,
    SubscriptionPlan,
    UserSubscriptionHistory,
    Role,
)

# ── Password hashing ────────────────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── User helpers ────────────────────────────────────────────────────────────
async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()


async def create_user(db: AsyncSession, username: str, password: str, full_name:str | None = None,) -> User:
    hashed = _pwd_ctx.hash(password)
    user = User(
        username=username,
        hashed_password=hashed,
        full_name = full_name,
        usage_period_start=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(user)
    await db.flush() # ← assigns user.id without committing

    free_plan = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
        )
    ).scalar_one()

    # 3) insert history row explicitly – no lazy load involved
    db.add(
        UserSubscriptionHistory(
            user_id=user.id,
            plan_id=free_plan.id,
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    default_role = (
        await db.execute(
            select(Role).where(Role.name == "user")
        )
    ).scalar_one()

    await db.execute(
        insert(user_roles).values(user_id=user.id, role_id=default_role.id)
    )

    # 4) one final commit
    await db.commit()
    await db.refresh(user)      # if you need the fresh object back

    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    user = await get_user_by_username(db, username)
    if not user or not _pwd_ctx.verify(password, user.hashed_password):
        return None
    return user


# ── Usage & analytics helpers ───────────────────────────────────────────────
async def bump_usage(
    db: AsyncSession,
    user_id: int,
    transcript_len: int,
    tokens_used: int,
) -> None:
    """Atomically increment usage counters and log the call."""
    # 1) atomic UPDATE
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            summarize_call_count=User.summarize_call_count + 1,
            last_summarize_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    # 2) per‑call log
    db.add(
        SummarizeCall(
            user_id=user_id,
            transcript_length=transcript_len,
            tokens_used=tokens_used,
        )
    )

    await db.commit()


# ── Feedback helpers ────────────────────────────────────────────────────────
async def store_feedback(
    db: AsyncSession, user_id: int, feedback_json: dict
) -> UserFeedback:
    fb = UserFeedback(user_id=user_id, feedback=feedback_json)
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb


# ── Subscription plan seeding (idempotent) ──────────────────────────────────
DEFAULT_PLANS: Sequence[dict] = (
    {"name": "free", "quota": 25, "price": 0.00},
    {"name": "pro", "quota": 100, "price": 4.99},
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

DEFAULT_ROLES = ({"name": "user"}, )

async def seed_roles(db: AsyncSession) -> None:
    await db.execute(
        insert(Role)
        .values(DEFAULT_ROLES)
        .on_conflict_do_nothing(index_elements=["name"])
    )
    await db.commit()