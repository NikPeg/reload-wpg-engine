"""
Migration 001: Add synonyms field to countries table
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from migrations.migration_runner import Migration


class AddCountrySynonymsMigration(Migration):
    """Add synonyms field to countries table"""
    
    def __init__(self):
        super().__init__(
            version="001",
            description="Add synonyms field to countries table"
        )
    
    async def up(self, session: AsyncSession) -> None:
        """Add synonyms column to countries table"""
        # Add synonyms column as JSON with default empty list
        await session.execute(text("""
            ALTER TABLE countries 
            ADD COLUMN synonyms TEXT DEFAULT '[]' NOT NULL
        """))
        await session.commit()
        
        print("Added synonyms column to countries table")
    
    async def down(self, session: AsyncSession) -> None:
        """Remove synonyms column from countries table"""
        # SQLite doesn't support DROP COLUMN directly, so we would need to recreate table
        # For now, just log that rollback is not implemented
        print("Rollback not implemented for SQLite - synonyms column will remain")


# Create migration instance
migration_001 = AddCountrySynonymsMigration()