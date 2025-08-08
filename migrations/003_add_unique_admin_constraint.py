"""
Migration 003: Add unique constraint for admin players
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class AddUniqueAdminConstraintMigration(Migration):
    """Add unique constraint to prevent multiple admins with same telegram_id"""

    def __init__(self):
        super().__init__(
            version="003",
            description="Add unique constraint for admin players"
        )

    async def up(self, session: AsyncSession) -> None:
        """Add unique constraint for telegram_id + role combination"""
        # First, clean up any duplicate admin records (just in case)
        await session.execute(text("""
            DELETE FROM players
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM players
                WHERE role = 'admin'
                GROUP BY telegram_id
            ) AND role = 'admin'
        """))

        # Add unique index for telegram_id + role combination
        await session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_admin_per_telegram
            ON players(telegram_id, role)
            WHERE role = 'admin'
        """))
        await session.commit()

        print("Added unique constraint for admin players")

    async def down(self, session: AsyncSession) -> None:
        """Remove unique constraint"""
        await session.execute(text("""
            DROP INDEX IF EXISTS idx_unique_admin_per_telegram
        """))
        await session.commit()
        print("Removed unique constraint for admin players")


# Create migration instance
migration_003 = AddUniqueAdminConstraintMigration()
