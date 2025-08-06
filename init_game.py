"""
Script to initialize a game with admin user
"""

import asyncio

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import PlayerRole, get_db, init_db


async def create_initial_game():
    """Create initial game and admin user"""
    print("🚀 Initializing WPG Engine...")

    # Initialize database
    await init_db()
    print("✅ Database initialized")

    async for db in get_db():
        engine = GameEngine(db)

        # Create game
        game = await engine.create_game(
            name="Древний мир - Эпоха империй",
            description="Военно-политическая игра в сеттинге древнего мира",
            setting="Древний мир",
            max_players=8,
            years_per_day=5,
        )
        print(f"✅ Game created: {game.name} (ID: {game.id})")

        # Create admin user (you'll need to replace with actual Telegram ID)
        admin_telegram_id = input("Enter admin Telegram ID: ")
        try:
            admin_telegram_id = int(admin_telegram_id)
        except ValueError:
            print("❌ Invalid Telegram ID")
            return

        admin_username = input("Enter admin username (optional): ") or None
        admin_display_name = input("Enter admin display name: ") or "Game Master"

        admin = await engine.create_player(
            game_id=game.id,
            telegram_id=admin_telegram_id,
            username=admin_username,
            display_name=admin_display_name,
            role=PlayerRole.ADMIN,
        )
        print(f"✅ Admin created: {admin.display_name} (ID: {admin.id})")

        # Start the game
        await engine.start_game(game.id)
        print("✅ Game started")

        print("\n🎉 Initialization complete!")
        print(f"Game: {game.name}")
        print(f"Admin: {admin.display_name} (Telegram ID: {admin.telegram_id})")
        print("\nYou can now start the bot with: python run_bot.py")

        break


if __name__ == "__main__":
    asyncio.run(create_initial_game())
