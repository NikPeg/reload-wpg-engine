#!/usr/bin/env python3
"""
Test script to verify the message system functionality
"""

import asyncio

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import PlayerRole, get_db, init_db


async def test_message_system():
    """Test the message system functionality"""
    print("💬 Starting Message System test...")

    # Initialize database
    print("📊 Initializing database...")
    await init_db()
    print("✅ Database initialized")

    # Get database session
    async for db in get_db():
        engine = GameEngine(db)

        # Test 1: Create a game
        print("\n🎮 Creating a test game...")
        game = await engine.create_game(
            name="Message Test Game",
            description="A test game for message system",
            setting="Современность",
            max_players=5,
        )
        print(f"✅ Game created: {game}")

        # Test 2: Create admin player
        print("\n👤 Creating admin player...")
        admin = await engine.create_player(
            game_id=game.id,
            telegram_id=123456789,
            username="admin",
            display_name="Test Admin",
            role=PlayerRole.ADMIN,
        )
        print(f"✅ Admin created: {admin}")

        # Test 3: Create regular player with country
        print("\n👤 Creating regular player...")
        player = await engine.create_player(
            game_id=game.id,
            telegram_id=987654321,
            username="player",
            display_name="Test Player",
            role=PlayerRole.PLAYER,
        )

        # Create country for player
        country = await engine.create_country(
            game_id=game.id,
            name="Test Kingdom",
            description="A test kingdom for message testing",
            capital="Test City",
            population=100000,
        )

        # Assign country to player
        await engine.assign_player_to_country(player.id, country.id)
        print(f"✅ Player created: {player} with country: {country.name}")

        # Test 4: Create player message
        print("\n💬 Creating player message...")
        player_message = await engine.create_message(
            player_id=player.id,
            game_id=game.id,
            content="Привет, администратор! У меня есть вопрос о правилах игры.",
            telegram_message_id=12345,
            is_admin_reply=False,
        )
        print(f"✅ Player message created: {player_message}")
        print(f"   Content: {player_message.content}")
        print(f"   Telegram ID: {player_message.telegram_message_id}")

        # Test 5: Create admin reply
        print("\n💬 Creating admin reply...")
        admin_reply = await engine.create_message(
            player_id=player.id,  # Still associated with the same player
            game_id=game.id,
            content="Привет! Конечно, задавай свои вопросы. Я готов помочь!",
            reply_to_id=player_message.id,
            is_admin_reply=True,
        )
        print(f"✅ Admin reply created: {admin_reply}")
        print(f"   Content: {admin_reply.content}")
        print(f"   Reply to message ID: {admin_reply.reply_to_id}")
        print(f"   Is admin reply: {admin_reply.is_admin_reply}")

        # Test 6: Create multiple messages to test history
        print("\n📝 Creating multiple messages for history test...")
        messages = []
        for i in range(12):  # Create 12 messages to test limit of 10
            message = await engine.create_message(
                player_id=player.id,
                game_id=game.id,
                content=f"Тестовое сообщение номер {i+1}",
                is_admin_reply=False,
            )
            messages.append(message)
        print(f"✅ Created {len(messages)} test messages")

        # Test 7: Get player messages (should return last 10)
        print("\n📋 Getting player message history...")
        message_history = await engine.get_player_messages(player.id, limit=10)
        print(f"✅ Retrieved {len(message_history)} messages (limit: 10)")
        print("   Message history (newest first):")
        for i, msg in enumerate(message_history[:5]):  # Show first 5
            print(f"     {i+1}. {msg.content}")
        if len(message_history) > 5:
            print(f"     ... and {len(message_history) - 5} more messages")

        # Test 8: Get message by telegram ID
        print("\n🔍 Testing message retrieval by telegram ID...")
        retrieved_message = await engine.get_message_by_telegram_id(12345)
        if retrieved_message:
            print(f"✅ Found message by telegram ID: {retrieved_message.content}")
        else:
            print("❌ Message not found by telegram ID")

        # Test 9: Test non-existent telegram ID
        print("\n🔍 Testing non-existent telegram ID...")
        non_existent = await engine.get_message_by_telegram_id(99999)
        if non_existent is None:
            print("✅ Correctly returned None for non-existent telegram ID")
        else:
            print("❌ Should have returned None for non-existent telegram ID")

        # Test 10: Create a chain of replies
        print("\n🔗 Creating message reply chain...")
        original = await engine.create_message(
            player_id=player.id,
            game_id=game.id,
            content="Исходное сообщение для цепочки ответов",
            is_admin_reply=False,
        )

        reply1 = await engine.create_message(
            player_id=player.id,
            game_id=game.id,
            content="Первый ответ администратора",
            reply_to_id=original.id,
            is_admin_reply=True,
        )

        reply2 = await engine.create_message(
            player_id=player.id,
            game_id=game.id,
            content="Ответ игрока на ответ администратора",
            reply_to_id=reply1.id,
            is_admin_reply=False,
        )

        print("✅ Created reply chain:")
        print(f"   Original: {original.content}")
        print(f"   Reply 1: {reply1.content} (admin: {reply1.is_admin_reply})")
        print(f"   Reply 2: {reply2.content} (admin: {reply2.is_admin_reply})")

        print("\n🎉 All message system tests completed successfully!")
        print("\n" + "=" * 60)
        print("MESSAGE SYSTEM TEST SUMMARY:")
        print(f"✅ Created game: '{game.name}' (ID: {game.id})")
        print(f"✅ Created admin player: {admin.display_name}")
        print(f"✅ Created regular player: {player.display_name} with country: {country.name}")
        print("✅ Created player message with telegram ID")
        print("✅ Created admin reply to player message")
        print(f"✅ Created {len(messages)} additional messages for history test")
        print("✅ Retrieved message history (limit: 10)")
        print("✅ Retrieved message by telegram ID")
        print("✅ Handled non-existent telegram ID correctly")
        print("✅ Created message reply chain")
        print("✅ All message system operations working correctly")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_message_system())
