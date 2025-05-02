"""
Quota enforcement for /summarize and similar endpoints.
"""

from typing import Annotated

from fastapi             import Depends, HTTPException, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

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
    db:           AsyncSession = Depends(get_db),
):
    """
    1. Look up the user row.
    2. If their monthly quota is exhausted → raise **402 Payment Required**.
    3. Return the `User` ORM object so the calling route can reuse it.
    """
    user = await get_user_by_username(db, current_user)

    plan = _PLAN_MAP.get(user.subscription_plan, _FREE_PLAN)
    if user.summarize_call_count >= plan["quota"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Quota exceeded for {user.subscription_plan} plan.",
        )

    return user