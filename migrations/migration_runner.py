"""
Migration runner for database schema changes
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.models.base import AsyncSessionLocal


class Migration:
    """Base migration class"""

    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description

    async def up(self, session: AsyncSession) -> None:
        """Apply migration"""
        raise NotImplementedError

    async def down(self, session: AsyncSession) -> None:
        """Rollback migration"""
        raise NotImplementedError


class MigrationRunner:
    """Migration runner"""

    def __init__(self):
        self.migrations: list[Migration] = []

    def add_migration(self, migration: Migration) -> None:
        """Add migration to runner"""
        self.migrations.append(migration)

    async def create_migration_table(self, session: AsyncSession) -> None:
        """Create migrations table if it doesn't exist"""
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        await session.commit()

    async def get_applied_migrations(self, session: AsyncSession) -> list[str]:
        """Get list of applied migration versions"""
        result = await session.execute(
            text("SELECT version FROM migrations ORDER BY version")
        )
        return [row[0] for row in result.fetchall()]

    async def mark_migration_applied(
        self, session: AsyncSession, migration: Migration
    ) -> None:
        """Mark migration as applied"""
        await session.execute(
            text(
                """
            INSERT INTO migrations (version, description) VALUES (:version, :description)
        """
            ),
            {"version": migration.version, "description": migration.description},
        )
        await session.commit()

    async def run_migrations(self) -> None:
        """Run all pending migrations"""
        async with AsyncSessionLocal() as session:
            await self.create_migration_table(session)
            applied_migrations = await self.get_applied_migrations(session)

            for migration in self.migrations:
                if migration.version not in applied_migrations:
                    print(
                        f"Applying migration {migration.version}: {migration.description}"
                    )
                    await migration.up(session)
                    await self.mark_migration_applied(session, migration)
                    print(f"Migration {migration.version} applied successfully")
                else:
                    print(f"Migration {migration.version} already applied, skipping")


# Global migration runner instance
migration_runner = MigrationRunner()
