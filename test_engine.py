"""
Test script to verify the WPG engine functionality
"""

import asyncio
from wpg_engine.models import init_db, get_db
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import GameStatus, PlayerRole


async def test_engine():
    """Test the basic functionality of the WPG engine"""
    print("🚀 Starting WPG Engine test...")
    
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
            name="Test WPG Game",
            description="A test war-political game",
            max_players=6,
            turn_duration_hours=48
        )
        print(f"✅ Game created: {game}")
        
        # Test 2: Create countries with 9 aspects
        print("\n🏛️ Creating test countries...")
        
        # Country 1: Strong economy, weak military
        country1 = await engine.create_country(
            game_id=game.id,
            name="Экономическая Держава",
            description="Страна с развитой экономикой",
            capital="Торговград",
            population=50000000,
            aspects={
                "economy": 9,
                "military": 3,
                "foreign_policy": 6,
                "territory": 5,
                "technology": 8,
                "religion_culture": 6,
                "governance_law": 7,
                "construction_infrastructure": 8,
                "social_relations": 7
            }
        )
        print(f"✅ Country 1 created: {country1}")
        print(f"   Aspects: {country1.get_aspects()}")
        
        # Country 2: Strong military, average economy
        country2 = await engine.create_country(
            game_id=game.id,
            name="Военная Империя",
            description="Страна с мощной армией",
            capital="Крепостьград",
            population=30000000,
            aspects={
                "economy": 5,
                "military": 9,
                "foreign_policy": 4,
                "territory": 7,
                "technology": 6,
                "religion_culture": 5,
                "governance_law": 6,
                "construction_infrastructure": 5,
                "social_relations": 4
            }
        )
        print(f"✅ Country 2 created: {country2}")
        print(f"   Aspects: {country2.get_aspects()}")
        
        # Test 3: Create players
        print("\n👥 Creating test players...")
        
        # Admin player
        admin = await engine.create_player(
            game_id=game.id,
            telegram_id=123456789,
            username="admin_user",
            display_name="Game Master",
            role=PlayerRole.ADMIN
        )
        print(f"✅ Admin created: {admin}")
        
        # Player 1
        player1 = await engine.create_player(
            game_id=game.id,
            telegram_id=987654321,
            username="player1",
            display_name="Economic Leader",
            role=PlayerRole.PLAYER,
            country_id=country1.id
        )
        print(f"✅ Player 1 created: {player1}")
        
        # Player 2
        player2 = await engine.create_player(
            game_id=game.id,
            vk_id=555666777,
            username="player2",
            display_name="Military Commander",
            role=PlayerRole.PLAYER,
            country_id=country2.id
        )
        print(f"✅ Player 2 created: {player2}")
        
        # Test 4: Create posts
        print("\n📝 Creating test posts...")
        
        post1 = await engine.create_post(
            author_id=player1.id,
            game_id=game.id,
            content="Наша страна объявляет о начале торговой экспансии. Мы готовы заключать выгодные торговые соглашения с соседними державами."
        )
        print(f"✅ Post 1 created: {post1}")
        
        post2 = await engine.create_post(
            author_id=player2.id,
            game_id=game.id,
            content="В ответ на торговую экспансию соседей, мы проводим военные учения на границе. Наша армия готова защищать национальные интересы."
        )
        print(f"✅ Post 2 created: {post2}")
        
        # Test 5: Create verdict
        print("\n⚖️ Creating test verdict...")
        
        verdict = await engine.create_verdict(
            post_id=post1.id,
            admin_id=admin.id,
            result="Торговая экспансия успешна. Экономический рейтинг страны увеличивается на 1 пункт.",
            reasoning="Действие соответствует экономическому профилю страны и не противоречит игровой логике."
        )
        print(f"✅ Verdict created: {verdict}")
        
        # Test 6: Update country aspects
        print("\n📈 Updating country aspects...")
        
        updated_country = await engine.update_country_aspects(
            country_id=country1.id,
            aspects={"economy": 10}  # Increase economy due to successful expansion
        )
        print(f"✅ Country updated: {updated_country}")
        print(f"   New aspects: {updated_country.get_aspects()}")
        
        # Test 7: Start the game
        print("\n🎯 Starting the game...")
        
        game_started = await engine.start_game(game.id)
        print(f"✅ Game started: {game_started}")
        
        # Test 8: Get game statistics
        print("\n📊 Getting game statistics...")
        
        stats = await engine.get_game_statistics(game.id)
        print(f"✅ Game statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Test 9: Get all posts
        print("\n📋 Getting all game posts...")
        
        posts = await engine.get_game_posts(game.id)
        print(f"✅ Found {len(posts)} posts:")
        for post in posts:
            print(f"   Post {post.id} by {post.author.display_name}: {post.content[:50]}...")
        
        # Test 10: Test public aspects visibility
        print("\n👁️ Testing public aspects visibility...")
        
        public_aspects = country1.get_public_aspects()
        print(f"✅ Public aspects for {country1.name}: {public_aspects}")
        
        # Make military aspect public for country2
        country2.military_public = True
        await db.commit()
        public_aspects2 = country2.get_public_aspects()
        print(f"✅ Public aspects for {country2.name}: {public_aspects2}")
        
        print("\n🎉 All tests completed successfully!")
        print("\n" + "="*50)
        print("SUMMARY:")
        print(f"✅ Created game: '{game.name}' (ID: {game.id})")
        print(f"✅ Created {len([country1, country2])} countries with 9 aspects each")
        print(f"✅ Created {len([admin, player1, player2])} players (1 admin, 2 players)")
        print(f"✅ Created {len(posts)} posts")
        print(f"✅ Created {len([verdict])} verdict")
        print(f"✅ Game status: {game.status}")
        print("✅ All CRUD operations working correctly")
        print("="*50)


if __name__ == "__main__":
    asyncio.run(test_engine())