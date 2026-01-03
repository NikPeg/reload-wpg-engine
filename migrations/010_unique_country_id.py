"""
Migration 010: Add unique constraint on country_id
This migration ensures one-to-one relationship between Player and Country
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class UniqueCountryIdMigration(Migration):
    """Add unique constraint on country_id in players table"""

    def __init__(self):
        super().__init__(
            version="010",
            description="Add unique constraint on country_id for one-to-one Player-Country relationship",
        )

    async def up(self, session: AsyncSession) -> None:
        """Add unique constraint and handle duplicates"""
        print("Running migration 010: Add unique constraint on country_id")

        # First, find duplicates and keep only the first occurrence (by id)
        print("🔍 Checking for duplicate country_id entries...")

        # Get duplicate country_ids
        result = await session.execute(
            text(
                """
                SELECT country_id, COUNT(*) as count
                FROM players
                WHERE country_id IS NOT NULL
                GROUP BY country_id
                HAVING COUNT(*) > 1
                """
            )
        )
        duplicates = result.fetchall()

        if duplicates:
            print(f"⚠️  Found {len(duplicates)} country_id values with duplicates")

            for country_id, count in duplicates:
                print(f"   Processing country_id={country_id} ({count} entries)")

                # Get all player ids with this country_id
                players_result = await session.execute(
                    text(
                        """
                        SELECT id FROM players
                        WHERE country_id = :country_id
                        ORDER BY id ASC
                        """
                    ),
                    {"country_id": country_id},
                )
                player_ids = [row[0] for row in players_result.fetchall()]

                # Keep the first one, unassign the rest
                ids_to_unassign = player_ids[1:]
                if ids_to_unassign:
                    print(
                        f"   Keeping player id={player_ids[0]}, unassigning country from {len(ids_to_unassign)} duplicate(s)"
                    )

                    # Create placeholders for IN clause
                    placeholders = ",".join([str(id) for id in ids_to_unassign])

                    # Unassign country from duplicate players
                    await session.execute(
                        text(
                            f"""
                            UPDATE players
                            SET country_id = NULL
                            WHERE id IN ({placeholders})
                            """
                        )
                    )

                    print(
                        f"   ✅ Unassigned country from {len(ids_to_unassign)} player(s)"
                    )
        else:
            print("✅ No duplicate country_id entries found")

        await session.commit()
        print("✅ Duplicate cleanup completed")

        # Now add the unique constraint
        print("Adding unique constraint on country_id...")

        # Check if unique index already exists
        result = await session.execute(
            text(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_players_country_id_unique'
                """
            )
        )
        index_exists = result.scalar() is not None

        if index_exists:
            print("⚠️  Unique index already exists, skipping creation")
        else:
            # Drop existing non-unique index if it exists
            await session.execute(text("DROP INDEX IF EXISTS idx_players_country_id"))
            print("   Dropped old non-unique index (if existed)")

            # Create unique index on country_id (excluding NULLs)
            try:
                await session.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX idx_players_country_id_unique
                        ON players(country_id)
                        WHERE country_id IS NOT NULL
                        """
                    )
                )
                print("✅ Added unique constraint on country_id")
            except Exception as e:
                print(f"❌ Error creating unique index: {e}")
                raise

        await session.commit()
        print("Migration 010 completed successfully")

    async def down(self, session: AsyncSession) -> None:
        """Remove unique constraint"""
        print("Downgrading migration 010: Remove unique constraint on country_id")

        # Drop unique index
        await session.execute(
            text("DROP INDEX IF EXISTS idx_players_country_id_unique")
        )

        # Recreate regular index
        await session.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_players_country_id
                ON players(country_id)
                """
            )
        )

        await session.commit()
        print("Migration 010 downgrade completed")


# Create migration instance
migration_010 = UniqueCountryIdMigration()
