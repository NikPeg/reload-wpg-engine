#!/usr/bin/env python3
"""
Check for duplicate telegram_id entries in the database
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# noqa: E402 - imports after path modification
from sqlalchemy import text  # noqa: E402

from wpg_engine.models.base import AsyncSessionLocal  # noqa: E402


async def check_duplicates():
    """Check for duplicate telegram_id entries"""
    async with AsyncSessionLocal() as session:
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
            print(f"\n⚠️  Found {len(duplicates)} telegram_id values with duplicates:\n")

            for telegram_id, count in duplicates:
                print(f"   telegram_id={telegram_id}: {count} entries")

                # Get details of these players
                players_result = await session.execute(
                    text(
                        """
                        SELECT id, username, display_name, role, game_id, created_at
                        FROM players
                        WHERE telegram_id = :telegram_id
                        ORDER BY id ASC
                        """
                    ),
                    {"telegram_id": telegram_id},
                )
                players = players_result.fetchall()

                for player in players:
                    id, username, display_name, role, game_id, created_at = player
                    print(
                        f"      - id={id}, username={username}, display_name={display_name}, "
                        f"role={role}, game_id={game_id}, created_at={created_at}"
                    )
                print()

            print(
                "\n💡 Run migration 009 to fix these duplicates and add unique constraint"
            )
            return False
        else:
            print("✅ No duplicate telegram_id entries found")

            # Check if unique constraint exists
            result = await session.execute(
                text(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='idx_players_telegram_id_unique'
                    """
                )
            )
            has_constraint = result.scalar() is not None

            if has_constraint:
                print("✅ Unique constraint on telegram_id is in place")
            else:
                print("⚠️  Unique constraint on telegram_id is NOT in place")
                print("💡 Run migration 009 to add the unique constraint")

            return has_constraint


if __name__ == "__main__":
    result = asyncio.run(check_duplicates())
    sys.exit(0 if result else 1)
