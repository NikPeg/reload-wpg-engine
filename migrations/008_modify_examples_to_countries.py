"""
Modify examples table to reference countries instead of storing text
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_runner import Migration


class ModifyExamplesTableMigration(Migration):
    """Modify examples table to reference countries"""

    def __init__(self):
        super().__init__(
            version="008",
            description="Modify examples table to reference countries instead of storing text",
        )

    async def up(self, session: AsyncSession) -> None:
        """Modify examples table structure"""
        # SQLite doesn't support ALTER TABLE DROP COLUMN or ADD COLUMN with constraints easily
        # So we need to recreate the table

        # 1. Create new table with correct structure
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS examples_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_id INTEGER NOT NULL UNIQUE,
                game_id INTEGER NOT NULL,
                created_by_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_id) REFERENCES players(id) ON DELETE CASCADE
            )
        """
            )
        )

        # 2. Drop old table (data will be lost, but that's ok for examples)
        await session.execute(text("DROP TABLE IF EXISTS examples"))

        # 3. Rename new table to examples
        await session.execute(text("ALTER TABLE examples_new RENAME TO examples"))

        await session.commit()

    async def down(self, session: AsyncSession) -> None:
        """Rollback to old structure"""
        # Recreate old table structure
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS examples_new (
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

        await session.execute(text("DROP TABLE IF EXISTS examples"))
        await session.execute(text("ALTER TABLE examples_new RENAME TO examples"))
        await session.commit()


# Create migration instance
migration_008 = ModifyExamplesTableMigration()
