#!/usr/bin/env python3
"""Initialize database with admin user and API key."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, async_session_maker
from app.core.security import generate_api_key
from app.models.user import User
from app.models.api_key import APIKey


async def init_db():
    """Initialize database with default admin user."""
    async with async_session_maker() as session:
        # Check if admin exists
        result = await session.execute(
            text("SELECT id FROM users WHERE email = 'admin@localhost'")
        )
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            name="Admin",
            email="admin@localhost",
            is_active=True,
            is_admin=True,
        )
        session.add(admin)
        await session.flush()

        # Create API key
        key = generate_api_key()
        api_key = APIKey(
            user_id=admin.id,
            key=key,
            name="Default Admin Key",
            description="Default admin key - change in production",
        )
        session.add(api_key)
        await session.commit()

        print(f"Created admin user: admin@localhost")
        print(f"API Key: {key}")
        print("\nSave this API key - it won't be shown again!")


if __name__ == "__main__":
    asyncio.run(init_db())
