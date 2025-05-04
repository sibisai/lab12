"""
Quota enforcement for /summarize and similar endpoints.
"""

from typing import Annotated

from fastapi             import Depends, HTTPException, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from server.models import Role, user_roles
from sqlalchemy import select
from .db    import get_db
from .crud  import get_user_by_username, DEFAULT_PLANS


# --------------------------------------------------------------------------- #
# helper to pull `verify_token` only when this file is first *used*, not       #
# while the import graph is still being built – avoids the circular import.   #
# --------------------------------------------------------------------------- #
async def _current_user_from_cookie(
    access_token: Annotated[str | None, Cookie()] = None,
):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # lazy import here → `server.main` is fully initialised
    from server.main import verify_token

    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    return verify_token(access_token, cred_exc)


# ---------------------------- plan helpers --------------------------------- #
_PLAN_MAP  : dict[str, dict] = {p["name"]: p for p in DEFAULT_PLANS}
_FREE_PLAN = _PLAN_MAP["free"]


async def enforce_quota(
    current_user: Annotated[str, Depends(_current_user_from_cookie)],
    db: AsyncSession = Depends(get_db),
):
    # 1) look up the User ORM
    user = await get_user_by_username(db, current_user)

    # 2) check if they have the “admin” role
    row = await db.execute(
        select(Role.name)
        .select_from(Role)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user.id)
    )
    roles = {r[0] for r in row.all()}
    if "admin" in roles:
        return user  # admins are unlimited

    # 3) otherwise, enforce the normal plan/quota
    plan = _PLAN_MAP.get(user.subscription_plan, _FREE_PLAN)
    if user.summarize_call_count >= plan["quota"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Quota exceeded for {user.subscription_plan} plan.",
        )

    return user