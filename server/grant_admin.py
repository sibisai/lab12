#!/usr/bin/env python3
import os
import asyncio
import argparse
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from server.models import User, Role, user_roles

def get_database_url() -> str:
    """Load DATABASE_URL from .env and return it."""
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set in environment")
    return url

async def grant_admin_role(username: str) -> None:
    """Grant the 'admin' role to the given username."""
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Fetch the user
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            print(f"No user found with username '{username}'")
            return

        # Fetch the admin role
        result = await session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        if not admin_role:
            print("Admin role not found in database")
            return

        # Insert association, ignoring if already exists
        stmt = (
            insert(user_roles)
            .values(user_id=user.id, role_id=admin_role.id)
            .on_conflict_do_nothing(index_elements=["user_id", "role_id"])
        )
        await session.execute(stmt)
        await session.commit()
        print(f"Granted 'admin' role to user '{username}'")

    await engine.dispose()

def main() -> None:
    parser = argparse.ArgumentParser(description="Grant admin role to a user")
    parser.add_argument("username", help="Username to grant admin privileges")
    args = parser.parse_args()
    asyncio.run(grant_admin_role(args.username))

if __name__ == "__main__":
    main()
