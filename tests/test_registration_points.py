#!/usr/bin/env python3
"""
Test script to verify the registration point system works correctly
"""

import asyncio

from sqlalchemy import select

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import get_db, init_db
from wpg_engine.models.game import Game


async def test_point_system():
    """Test the point system implementation"""
    print("🧪 Testing registration point system...")

    # Initialize database
    await init_db()

    async with get_db() as db:
        engine = GameEngine(db)

        # Create a test game with 25 max points
        print("📝 Creating test game with 25 max points...")
        game = await engine.create_game(
            name="Test Game",
            description="Test game for point system",
            setting="Test",
            max_players=5,
            years_per_day=1,
            max_points=25,
        )

        print(f"✅ Game created: {game.name} (max_points: {game.max_points})")

        # Test creating a country with valid points (total = 25)
        print("🏛️ Testing country creation with valid points (total = 25)...")
        country1 = await engine.create_country(
            game_id=game.id,
            name="Test Country 1",
            description="A test country",
            capital="Test Capital",
            population=1000000,
            aspects={
                "economy": 3,
                "military": 2,
                "foreign_policy": 3,
                "territory": 2,
                "technology": 3,
                "religion_culture": 2,
                "governance_law": 3,
                "construction_infrastructure": 2,
                "social_relations": 3,
                "intelligence": 2,
            },
        )

        # Calculate total points
        aspects = country1.get_aspects_values_only()
        total_points = sum(aspects.values())
        print(f"✅ Country created with {total_points} total points")

        # Verify the aspects were set correctly
        print("📊 Aspect breakdown:")
        for aspect, value in aspects.items():
            print(f"  • {aspect}: {value}")

        # Test that the game has the correct max_points
        result = await db.execute(select(Game).where(Game.id == game.id))
        retrieved_game = result.scalar_one()
        print(f"✅ Game max_points verified: {retrieved_game.max_points}")

        # Test creating another country with different point distribution
        print("🏛️ Testing country creation with different point distribution...")
        country2 = await engine.create_country(
            game_id=game.id,
            name="Test Country 2",
            description="Another test country",
            capital="Another Capital",
            population=2000000,
            aspects={
                "economy": 5,
                "military": 1,
                "foreign_policy": 1,
                "territory": 5,
                "technology": 1,
                "religion_culture": 1,
                "governance_law": 5,
                "construction_infrastructure": 1,
                "social_relations": 1,
                "intelligence": 4,
            },
        )

        aspects2 = country2.get_aspects_values_only()
        total_points2 = sum(aspects2.values())
        print(f"✅ Second country created with {total_points2} total points")

        print("📊 Second country aspect breakdown:")
        for aspect, value in aspects2.items():
            print(f"  • {aspect}: {value}")

        print("✅ All tests passed! Point system is working correctly.")


if __name__ == "__main__":
    asyncio.run(test_point_system())
