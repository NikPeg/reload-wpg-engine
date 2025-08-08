#!/usr/bin/env python3
"""
Migration script to add max_points field to existing games
"""

import asyncio

from sqlalchemy import text

from wpg_engine.models import get_db


async def migrate_max_points():
    """Add max_points column to games table and set default value"""

    async for db in get_db():
        try:
            # Check if column already exists (SQLite specific)
            result = await db.execute(text("PRAGMA table_info(games)"))
            columns = result.fetchall()

            column_exists = any(col[1] == "max_points" for col in columns)

            if column_exists:
                print("✅ Column max_points already exists in games table")
                return

            # Add the column (SQLite doesn't support DEFAULT with NOT NULL in ALTER TABLE)
            await db.execute(
                text(
                    """
                ALTER TABLE games
                ADD COLUMN max_points INTEGER DEFAULT 30
            """
                )
            )

            # Update existing games to have max_points = 30
            result = await db.execute(
                text(
                    """
                UPDATE games
                SET max_points = 30
                WHERE max_points IS NULL
            """
                )
            )

            await db.commit()

            print("✅ Successfully added max_points column to games table")
            print(f"✅ Updated {result.rowcount} existing games with default max_points = 30")

        except Exception as e:
            print(f"❌ Migration failed: {e}")
            await db.rollback()
            raise

        break


if __name__ == "__main__":
    print("🔄 Running max_points migration...")
    asyncio.run(migrate_max_points())
    print("✅ Migration completed!")
