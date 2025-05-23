"""
server/crud.py
Asynchronous helper functions for DB access.
"""

import datetime, secrets
from typing import Optional, Sequence
import sqlalchemy as sa
from sqlalchemy import select, update, insert, func
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
    EmailVerification,
    PasswordReset
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


# --- Email verification ----------------------------------------------------

# server/crud.py

async def create_verification_code(
    db: AsyncSession,
    email: str,
    user_id: int,
    *,
    ttl_minutes: int = 1440,
) -> str:
    # 1) Expire any previous codes
    await db.execute(
        sa.update(EmailVerification)
        .where(
            EmailVerification.user_id == user_id,
            EmailVerification.consumed.is_(False),
            EmailVerification.expires_at > datetime.datetime.utcnow()
        )
        .values(expires_at=datetime.datetime.utcnow())
    )

    # 2) Insert a new code
    code = f"{secrets.randbelow(900_000):06d}"
    ev = EmailVerification(
        user_id=user_id,
        email=email,
        code=code,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=ttl_minutes)
    )
    db.add(ev)
    await db.commit()
    return code

async def confirm_code(
    db: AsyncSession,
    email: str,
    code: str,
) -> bool:
    now = datetime.datetime.utcnow()
    row = (
        await db.execute(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.code == code,
                EmailVerification.consumed.is_(False),
                EmailVerification.expires_at > now
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if not row:
        return False

    # mark this code consumed
    row.consumed = True

    # mark the user verified
    await db.execute(
        sa.update(User)
        .where(User.id == row.user_id)
        .values(email_verified=True)
    )
    await db.commit()
    return True


async def create_password_reset_code(
    db: AsyncSession,
    email: str,
    user_id: int,
    *,
    ttl_minutes: int = 60
) -> str:
    # expire any previous
    await db.execute(
      sa.update(PasswordReset)
        .where(
          PasswordReset.user_id==user_id,
          PasswordReset.consumed.is_(False),
          PasswordReset.expires_at > datetime.datetime.utcnow()
        )
        .values(expires_at=datetime.datetime.utcnow())
    )

    code = f"{secrets.randbelow(900_000):06d}"
    pr = PasswordReset(
      user_id=user_id,
      email=email,
      code=code,
      expires_at=datetime.datetime.utcnow() +
                 datetime.timedelta(minutes=ttl_minutes),
    )
    db.add(pr)
    await db.commit()
    return code

async def confirm_password_reset_code(
    db: AsyncSession,
    email: str,
    code: str
) -> Optional[int]:
    """Returns user_id if OK, else None."""
    now = datetime.datetime.utcnow()
    row = (await db.execute(
      select(PasswordReset)
        .where(
          PasswordReset.email==email,
          PasswordReset.code==code,
          PasswordReset.consumed.is_(False),
          PasswordReset.expires_at>now
        )
        .with_for_update()
    )).scalar_one_or_none()
    if not row:
        return None

    row.consumed = True
    await db.commit()
    return row.user_id

async def update_user_password(db: AsyncSession, user_id: int, new_password: str):
    hashed = _pwd_ctx.hash(new_password)
    await db.execute(
      sa.update(User)
        .where(User.id==user_id)
        .values(hashed_password=hashed)
    )
    await db.commit()

async def count_verified_users(db: AsyncSession) -> int:
    q = select(func.count()).select_from(User).where(User.email_verified == True)
    return (await db.execute(q)).scalar_one()