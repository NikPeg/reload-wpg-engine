"""
Migration 005: Allow admins to exist without countries

This migration ensures that:
1. Admin players can have NULL country_id
2. Only player role requires a country
3. Supports both user and chat admins (negative telegram_id for chats)
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class AdminWithoutCountryMigration(Migration):
    """Allow admins to exist without countries"""

    def __init__(self):
        super().__init__(
            version="005", description="Allow admins to exist without countries"
        )

    async def up(self, session: AsyncSession) -> None:
        """
        Upgrade database schema to allow admins without countries.

        Note: country_id is already nullable in the schema, so we just need to
        ensure data integrity - admins can have NULL country_id while regular
        players should have a country assigned.
        """
        print("Running migration 005: Allow admins to exist without countries")

        # This migration is informational - the schema already supports NULL country_id
        # We're documenting that admins are allowed to not have countries

        # Verify that admin players can exist without countries
        result = await session.execute(
            text("""
                SELECT COUNT(*) as count
                FROM players
                WHERE role = 'admin' AND country_id IS NULL
            """)
        )
        admin_count = result.scalar()

        print(f"Found {admin_count} admin(s) without countries (this is OK)")

        # Log info about admin configuration
        result = await session.execute(
            text("""
                SELECT
                    role,
                    COUNT(*) as count,
                    SUM(CASE WHEN country_id IS NULL THEN 1 ELSE 0 END) as without_country
                FROM players
                GROUP BY role
            """)
        )

        print("\nPlayer statistics by role:")
        for row in result:
            print(
                f"  {row.role}: {row.count} total, {row.without_country} without country"
            )

        await session.commit()
        print("Migration 005 completed successfully")

    async def down(self, session: AsyncSession) -> None:
        """
        Downgrade - no schema changes needed as country_id was always nullable.

        Note: This migration doesn't change the schema, only documents that
        admins can exist without countries.
        """
        print("Downgrading migration 005: No changes needed")
        await session.commit()


# Create migration instance
migration_005 = AdminWithoutCountryMigration()
