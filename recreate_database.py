#!/usr/bin/env python3
"""
Script to recreate the database with new Message model
"""

import asyncio
import os
from pathlib import Path

from wpg_engine.models.base import Base, engine


async def recreate_database():
    """Drop and recreate all database tables"""
    print("🗑️  Dropping existing database...")

    # Remove existing database file if it exists
    db_file = Path("wpg_engine.db")
    if db_file.exists():
        os.remove(db_file)
        print("✅ Existing database file removed")

    print("🔨 Creating new database tables...")

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database recreated successfully!")
    print("📋 New tables created:")
    print("   - games")
    print("   - countries")
    print("   - players")
    print("   - posts")
    print("   - verdicts")
    print("   - messages (NEW)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(recreate_database())
