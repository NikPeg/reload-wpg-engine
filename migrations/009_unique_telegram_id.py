"""
Migration 009: Add unique constraint on telegram_id
This migration removes duplicate telegram_id entries and adds a unique constraint
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class UniqueTelegramIdMigration(Migration):
    """Add unique constraint on telegram_id"""

    def __init__(self):
        super().__init__(
            version="009",
            description="Add unique constraint on telegram_id, remove duplicates",
        )

    async def up(self, session: AsyncSession) -> None:
        """Add unique constraint and remove duplicates"""
        print("Running migration 009: Add unique constraint on telegram_id")

        # First, find duplicates and keep only the first occurrence (by id)
        print("🔍 Checking for duplicate telegram_id entries...")

        # Get duplicate telegram_ids
        result = await session.execute(
            text(
                """
                SELECT telegram_id, COUNT(*) as count
                FROM players
                WHERE telegram_id IS NOT NULL
                GROUP BY telegram_id
                HAVING COUNT(*) > 1
                """
            )
        )
        duplicates = result.fetchall()

        if duplicates:
            print(f"⚠️  Found {len(duplicates)} telegram_id values with duplicates")

            for telegram_id, count in duplicates:
                print(f"   Processing telegram_id={telegram_id} ({count} entries)")

                # Get all player ids with this telegram_id
                players_result = await session.execute(
                    text(
                        """
                        SELECT id FROM players
                        WHERE telegram_id = :telegram_id
                        ORDER BY id ASC
                        """
                    ),
                    {"telegram_id": telegram_id},
                )
                player_ids = [row[0] for row in players_result.fetchall()]

                # Keep the first one, delete the rest
                ids_to_delete = player_ids[1:]
                if ids_to_delete:
                    print(
                        f"   Keeping player id={player_ids[0]}, deleting {len(ids_to_delete)} duplicates"
                    )

                    # Create placeholders for IN clause
                    placeholders = ",".join([str(id) for id in ids_to_delete])

                    # Delete related records first (due to foreign key constraints)
                    # Delete messages
                    await session.execute(
                        text(
                            f"""
                            DELETE FROM messages
                            WHERE player_id IN ({placeholders})
                            """
                        )
                    )

                    # Delete posts
                    await session.execute(
                        text(
                            f"""
                            DELETE FROM posts
                            WHERE author_id IN ({placeholders})
                            """
                        )
                    )

                    # Delete verdicts
                    await session.execute(
                        text(
                            f"""
                            DELETE FROM verdicts
                            WHERE admin_id IN ({placeholders})
                            """
                        )
                    )

                    # Now delete the duplicate players
                    await session.execute(
                        text(
                            f"""
                            DELETE FROM players
                            WHERE id IN ({placeholders})
                            """
                        )
                    )

                    print(f"   ✅ Deleted {len(ids_to_delete)} duplicate player(s)")
        else:
            print("✅ No duplicate telegram_id entries found")

        await session.commit()
        print("✅ Duplicate cleanup completed")

        # Now add the unique constraint
        # SQLite doesn't support ALTER TABLE ADD CONSTRAINT directly
        # We need to recreate the table or use a unique index
        print("Adding unique constraint on telegram_id...")

        # Check if unique index already exists
        result = await session.execute(
            text(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_players_telegram_id_unique'
                """
            )
        )
        index_exists = result.scalar() is not None

        if index_exists:
            print("⚠️  Unique index already exists, skipping creation")
        else:
            # Drop existing non-unique index if it exists
            await session.execute(text("DROP INDEX IF EXISTS idx_players_telegram_id"))
            print("   Dropped old non-unique index")

            # Create unique index on telegram_id (excluding NULLs)
            try:
                await session.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX idx_players_telegram_id_unique
                        ON players(telegram_id)
                        WHERE telegram_id IS NOT NULL
                        """
                    )
                )
                print("✅ Added unique constraint on telegram_id")
            except Exception as e:
                print(f"❌ Error creating unique index: {e}")
                raise

        await session.commit()
        print("Migration 009 completed successfully")

    async def down(self, session: AsyncSession) -> None:
        """Remove unique constraint"""
        print("Downgrading migration 009: Remove unique constraint on telegram_id")

        # Drop unique index
        await session.execute(
            text("DROP INDEX IF EXISTS idx_players_telegram_id_unique")
        )

        # Recreate regular index
        await session.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_players_telegram_id
                ON players(telegram_id)
                """
            )
        )

        await session.commit()
        print("Migration 009 downgrade completed")


# Create migration instance
migration_009 = UniqueTelegramIdMigration()
