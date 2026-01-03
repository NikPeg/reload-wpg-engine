"""
Migration 002: Add max_population field to games table
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class AddMaxPopulationMigration(Migration):
    """Add max_population field to games table"""

    def __init__(self):
        super().__init__(
            version="002", description="Add max_population field to games table"
        )

    async def up(self, session: AsyncSession) -> None:
        """Add max_population column to games table"""
        # Check if column already exists
        result = await session.execute(text("PRAGMA table_info(games)"))
        columns = [row[1] for row in result.fetchall()]

        if "max_population" not in columns:
            await session.execute(
                text(
                    """
                ALTER TABLE games
                ADD COLUMN max_population INTEGER DEFAULT 10000000 NOT NULL
            """
                )
            )
            await session.commit()
            print("Added max_population column to games table")
        else:
            print("max_population column already exists, skipping")

    async def down(self, session: AsyncSession) -> None:
        """Remove max_population column from games table"""
        # SQLite doesn't support DROP COLUMN directly, so we would need to recreate table
        # For now, just log that rollback is not implemented
        print("Rollback not implemented for SQLite - max_population column will remain")


# Create migration instance
migration_002 = AddMaxPopulationMigration()
