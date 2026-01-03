"""
Add examples table for storing example messages
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class AddExamplesMigration(Migration):
    """Add examples table"""

    def __init__(self):
        super().__init__(
            version="007",
            description="Add examples table for storing example messages",
        )

    async def up(self, session: AsyncSession) -> None:
        """Create examples table"""
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                game_id INTEGER NOT NULL,
                created_by_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_id) REFERENCES players(id) ON DELETE CASCADE
            )
        """
            )
        )
        await session.commit()

    async def down(self, session: AsyncSession) -> None:
        """Drop examples table"""
        await session.execute(text("DROP TABLE IF EXISTS examples"))
        await session.commit()


# Create migration instance
migration_007 = AddExamplesMigration()
