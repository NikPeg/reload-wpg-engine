#!/usr/bin/env python3
"""
Main script to run the WPG Engine Telegram bot
Handles database initialization and startup
"""

import asyncio
import logging
import sys

from wpg_engine.adapters.telegram.bot import main as bot_main
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import get_db, init_db


async def check_and_init_database():
    """Check if database exists and initialize if needed"""
    print("🔍 Checking database...")

    try:
        # Try to get database session to check if it exists and is accessible
        async for db in get_db():
            # Try to query something simple to check if tables exist
            from sqlalchemy import select

            from wpg_engine.models.game import Game

            try:
                await db.execute(select(Game).limit(1))
                print("✅ Database exists and is accessible")
                return True
            except Exception:
                # Tables don't exist, need to initialize
                print("📊 Database exists but tables missing, initializing...")
                break
    except Exception as e:
        print(f"📊 Database not accessible: {e}")
        print("📊 Initializing database...")

    # Initialize database
    await init_db()
    print("✅ Database initialized")
    return False


async def create_initial_game_if_needed():
    """Create initial game and admin if no games exist"""
    async for db in get_db():
        engine = GameEngine(db)

        # Check if any games exist
        from sqlalchemy import select

        from wpg_engine.models.game import Game

        result = await db.execute(select(Game).limit(1))
        existing_game = result.scalar_one_or_none()

        if existing_game:
            print(f"✅ Game already exists: {existing_game.name}")
            return

        print("🎮 No games found, creating initial game...")

        # Create game
        game = await engine.create_game(
            name="Древний мир - Эпоха империй",
            description="Военно-политическая игра в сеттинге древнего мира",
            setting="Древний мир",
            max_players=8,
            years_per_day=5,
            max_points=30,
        )
        print(f"✅ Game created: {game.name} (ID: {game.id})")

        # Start the game
        await engine.start_game(game.id)
        print("✅ Game started")

        print(
            "ℹ️  Game is ready! Admin will be auto-assigned to the first player who registers."
        )
        break


async def run_migrations():
    """Run database migrations"""
    print("🔄 Running database migrations...")
    try:
        # Import and run migrations
        import importlib.util
        import os
        from pathlib import Path

        from migrations.migration_runner import migration_runner

        # Load and add all migrations
        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(
            [
                f
                for f in os.listdir(migrations_dir)
                if f.endswith(".py") and f[0].isdigit()
            ]
        )

        for migration_file in migration_files:
            migration_path = migrations_dir / migration_file
            try:
                # Load migration from file
                spec = importlib.util.spec_from_file_location(
                    "migration", migration_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Extract migration number from filename
                migration_number = migration_file.split("_")[0]
                migration_attr = f"migration_{migration_number}"

                migration = getattr(module, migration_attr)
                migration_runner.add_migration(migration)
                print(f"📦 Loaded migration: {migration_file}")
            except Exception as e:
                print(f"❌ Failed to load migration {migration_file}: {e}")

        # Run migrations
        await migration_runner.run_migrations()
        print("✅ Database migrations completed")

    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        # Don't fail startup if migrations fail - log and continue
        print("⚠️  Continuing startup despite migration errors...")


async def initialize_system():
    """Initialize the entire system"""
    print("🚀 Initializing WPG Engine...")

    # Check and initialize database
    db_existed = await check_and_init_database()

    # Run migrations after database initialization
    await run_migrations()

    # Create initial game if needed
    if not db_existed:
        await create_initial_game_if_needed()

    print("✅ System initialization complete")


async def start_bot():
    """Start the bot"""
    print("🤖 Starting Telegram bot...")
    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Run the bot
        await bot_main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)


async def main():
    """Main function"""
    print("🔄 Starting WPG Engine Telegram Bot...")

    # Initialize system
    await initialize_system()

    # Start new bot
    await start_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Startup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
