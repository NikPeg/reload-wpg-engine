"""
Test for /gen command database storage
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.handlers.admin import (
    generate_game_event,
)
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Message, Player, PlayerRole


@pytest.mark.asyncio
async def test_gen_command_saves_events_to_database(db_session):
    """Test that /gen command saves events to database for RAG context"""

    # Create game engine
    game_engine = GameEngine(db_session)

    # Create a test game
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for gen command",
        setting="Тестовый сеттинг",
        max_players=10,
        years_per_day=1,
        max_points=30,
        max_population=10_000_000,
    )

    # Create admin player
    admin = await game_engine.create_player(
        game_id=game.id,
        telegram_id=12345,
        username="admin",
        display_name="Test Admin",
        role=PlayerRole.ADMIN,
    )

    # Create admin country
    admin_country = await game_engine.create_country(
        game_id=game.id,
        name="Админская Республика",
        description="Страна администратора",
        capital="Столица",
        population=1000000,
        aspects={
            "economy": 8,
            "military": 7,
            "foreign_policy": 9,
            "territory": 6,
            "technology": 8,
            "religion_culture": 7,
            "governance_law": 10,
            "construction_infrastructure": 7,
            "social_relations": 8,
            "intelligence": 9,
        },
    )

    # Assign admin to country
    await game_engine.assign_player_to_country(admin.id, admin_country.id)

    # Create test player and country
    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=67890,
        username="testplayer",
        display_name="Test Player",
        role=PlayerRole.PLAYER,
    )

    country = await game_engine.create_country(
        game_id=game.id,
        name="Тестовая Страна",
        description="Тестовая страна для проверки",
        capital="Тест-Сити",
        population=5000000,
        aspects={
            "economy": 5,
            "military": 4,
            "foreign_policy": 6,
            "territory": 7,
            "technology": 3,
            "religion_culture": 8,
            "governance_law": 5,
            "construction_infrastructure": 6,
            "social_relations": 7,
            "intelligence": 4,
        },
    )

    # Assign player to country
    await game_engine.assign_player_to_country(player.id, country.id)

    # Test 1: Generate event for specific country
    rag_system = RAGSystem(db_session)

    # Generate event for specific country
    event_text, selected_tone = await generate_game_event(
        rag_system, game.id, "Тестовая Страна", game.setting
    )

    assert event_text is not None
    assert selected_tone is not None
    assert len(event_text) > 10  # Should be a meaningful event

    # Simulate saving the event to database (like in process_gen_callback)
    saved_message = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content=event_text,
        is_admin_reply=True,
    )

    # Verify the message was saved
    assert saved_message.id is not None
    assert saved_message.player_id == player.id
    assert saved_message.game_id == game.id
    assert saved_message.content == event_text
    assert saved_message.is_admin_reply is True

    # Test 2: Generate global event
    global_event_text, global_tone = await generate_game_event(
        rag_system, game.id, None, game.setting  # None means global event
    )

    assert global_event_text is not None
    assert global_tone is not None
    assert len(global_event_text) > 10

    # Simulate saving global event for all players
    all_players_result = await db_session.execute(
        select(Player)
        .where(Player.game_id == game.id)
        .where(Player.role == PlayerRole.PLAYER)
    )
    all_players = all_players_result.scalars().all()

    saved_global_messages = []
    for test_player in all_players:
        saved_global_message = await game_engine.create_message(
            player_id=test_player.id,
            game_id=game.id,
            content=global_event_text,
            is_admin_reply=True,
        )
        saved_global_messages.append(saved_global_message)

    # Verify global messages were saved
    assert len(saved_global_messages) == 1  # Only one player in test
    assert saved_global_messages[0].content == global_event_text
    assert saved_global_messages[0].is_admin_reply is True

    # Test 3: Verify RAG system can find these messages
    # Check that RAG system can retrieve the admin messages
    latest_admin_message = await rag_system._get_previous_admin_message(
        player.id, game.id
    )

    # Should find the most recent admin message (global event)
    assert latest_admin_message is not None
    assert latest_admin_message == global_event_text

    # Test 4: Check all messages in database
    all_messages_result = await db_session.execute(
        select(Message)
        .options(selectinload(Message.player))
        .where(Message.game_id == game.id)
        .where(Message.is_admin_reply)
        .order_by(Message.created_at.desc())
    )
    all_admin_messages = all_messages_result.scalars().all()

    # Should have 2 admin messages: one specific + one global
    assert len(all_admin_messages) == 2

    # Verify both messages are marked as admin replies
    for msg in all_admin_messages:
        assert msg.is_admin_reply is True
        assert msg.game_id == game.id
        assert msg.content in [event_text, global_event_text]


@pytest.mark.asyncio
async def test_gen_vs_event_command_consistency(db_session):
    """Test that /gen and /event commands save messages consistently"""

    game_engine = GameEngine(db_session)

    # Create test game and player
    game = await game_engine.create_game(
        name="Consistency Test",
        setting="Тест",
    )

    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=11111,
        username="testuser",
        display_name="Test User",
        role=PlayerRole.PLAYER,
    )

    country = await game_engine.create_country(
        game_id=game.id,
        name="Тест Страна",
        capital="Тест",
        population=1000000,
    )

    await game_engine.assign_player_to_country(player.id, country.id)

    # Simulate /event command message saving
    event_message = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content="Тестовое событие от /event команды",
        is_admin_reply=True,
    )

    # Simulate /gen command message saving
    gen_message = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content="Тестовое событие от /gen команды",
        is_admin_reply=True,
    )

    # Both should be saved identically
    assert event_message.is_admin_reply == gen_message.is_admin_reply
    assert event_message.player_id == gen_message.player_id
    assert event_message.game_id == gen_message.game_id

    # RAG system should find both
    rag_system = RAGSystem(db_session)
    latest_message = await rag_system._get_previous_admin_message(
        player.id, game.id
    )

    # Should find the most recent one (gen_message)
    assert latest_message == "Тестовое событие от /gen команды"
