"""
Migration 006: Add performance indexes for frequently queried fields
This migration adds indexes to improve query performance
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class PerformanceIndexesMigration(Migration):
    """Add indexes for performance optimization"""

    def __init__(self):
        super().__init__(
            version="006", description="Add performance indexes for frequently queried fields"
        )

    async def up(self, session: AsyncSession) -> None:
        """Add indexes for performance optimization"""
        print("Running migration 006: Add performance indexes")
        
        # Add index on players.telegram_id (most frequently queried field)
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_players_telegram_id 
            ON players(telegram_id)
            """
            )
        )
        print("✅ Added index on players.telegram_id")

        # Add index on players.game_id (for game-related queries)
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_players_game_id 
            ON players(game_id)
            """
            )
        )
        print("✅ Added index on players.game_id")

        # Add index on players.role (for admin checks)
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_players_role 
            ON players(role)
            """
            )
        )
        print("✅ Added index on players.role")

        # Add composite index for common query pattern (telegram_id + role)
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_players_telegram_id_role 
            ON players(telegram_id, role)
            """
            )
        )
        print("✅ Added composite index on players(telegram_id, role)")

        # Add index on messages.player_id for message queries
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_messages_player_id 
            ON messages(player_id)
            """
            )
        )
        print("✅ Added index on messages.player_id")

        # Add index on messages.game_id for game-related message queries
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_messages_game_id 
            ON messages(game_id)
            """
            )
        )
        print("✅ Added index on messages.game_id")

        # Add index on messages.created_at for time-based queries
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_messages_created_at 
            ON messages(created_at)
            """
            )
        )
        print("✅ Added index on messages.created_at")

        # Add index on messages.is_admin_reply for filtering messages
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_messages_is_admin_reply 
            ON messages(is_admin_reply)
            """
            )
        )
        print("✅ Added index on messages.is_admin_reply")

        await session.commit()
        print("Migration 006 completed successfully")

    async def down(self, session: AsyncSession) -> None:
        """Remove performance indexes"""
        print("Downgrading migration 006: Remove performance indexes")
        
        await session.execute(text("DROP INDEX IF EXISTS idx_players_telegram_id"))
        await session.execute(text("DROP INDEX IF EXISTS idx_players_game_id"))
        await session.execute(text("DROP INDEX IF EXISTS idx_players_role"))
        await session.execute(text("DROP INDEX IF EXISTS idx_players_telegram_id_role"))
        await session.execute(text("DROP INDEX IF EXISTS idx_messages_player_id"))
        await session.execute(text("DROP INDEX IF EXISTS idx_messages_game_id"))
        await session.execute(text("DROP INDEX IF EXISTS idx_messages_created_at"))
        await session.execute(text("DROP INDEX IF EXISTS idx_messages_is_admin_reply"))
        
        await session.commit()
        print("Migration 006 downgrade completed")


# Create migration instance
migration_006 = PerformanceIndexesMigration()

