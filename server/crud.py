# crud.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
import server.models as models

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user_by_username(db: AsyncSession, username: str):
    q = await db.execute(select(models.User).where(models.User.username == username))
    return q.scalars().first()

async def create_user(db: AsyncSession, username: str, password: str):
    hashed = pwd_ctx.hash(password)
    user = models.User(username=username, hashed_password=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)
    if not user or not pwd_ctx.verify(password, user.hashed_password):
        return None
    return user