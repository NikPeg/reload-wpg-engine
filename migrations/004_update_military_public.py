"""
Migration 004: Update military_public to True for existing countries
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class UpdateMilitaryPublicMigration(Migration):
    """Update military_public to True for existing countries"""

    def __init__(self):
        super().__init__(
            version="004",
            description="Update military_public to True for existing countries",
        )

    async def up(self, session: AsyncSession) -> None:
        """Update military_public to True for all existing countries"""
        await session.execute(
            text(
                "UPDATE countries SET military_public = true WHERE military_public = false"
            )
        )
        await session.commit()
        print("✅ Updated military_public to True for existing countries")

    async def down(self, session: AsyncSession) -> None:
        """Revert military_public to False for all countries"""
        await session.execute(text("UPDATE countries SET military_public = false"))
        await session.commit()
        print("✅ Reverted military_public to False for all countries")


# Create migration instance
migration_004 = UpdateMilitaryPublicMigration()
