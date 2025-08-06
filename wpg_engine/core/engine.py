"""
Basic GameEngine class
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wpg_engine.models import (
    Country,
    Game,
    GameStatus,
    Player,
    PlayerRole,
    Post,
    Verdict,
)


class GameEngine:
    """Core game engine for managing WPG games"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # Game management
    async def create_game(
        self,
        name: str,
        description: Optional[str] = None,
        max_players: int = 10,
        turn_duration_hours: int = 24,
        settings: Optional[dict] = None,
    ) -> Game:
        """Create a new game"""
        game = Game(
            name=name,
            description=description,
            max_players=max_players,
            turn_duration_hours=turn_duration_hours,
            settings=settings or {},
        )
        self.db.add(game)
        await self.db.commit()
        await self.db.refresh(game)
        return game

    async def get_game(self, game_id: int) -> Optional[Game]:
        """Get game by ID with all relationships"""
        result = await self.db.execute(
            select(Game)
            .options(
                selectinload(Game.countries),
                selectinload(Game.players),
                selectinload(Game.posts),
            )
            .where(Game.id == game_id)
        )
        return result.scalar_one_or_none()

    async def start_game(self, game_id: int) -> bool:
        """Start a game"""
        game = await self.get_game(game_id)
        if not game or game.status != GameStatus.CREATED:
            return False

        game.status = GameStatus.ACTIVE
        await self.db.commit()
        return True

    # Country management
    async def create_country(
        self,
        game_id: int,
        name: str,
        description: Optional[str] = None,
        aspects: Optional[dict] = None,
        capital: Optional[str] = None,
        population: Optional[int] = None,
    ) -> Country:
        """Create a new country in a game"""
        country_data = {
            "game_id": game_id,
            "name": name,
            "description": description,
            "capital": capital,
            "population": population,
        }

        # Set aspects if provided
        if aspects:
            for aspect, value in aspects.items():
                if hasattr(Country, aspect):
                    country_data[aspect] = value

        country = Country(**country_data)
        self.db.add(country)
        await self.db.commit()
        await self.db.refresh(country)
        return country

    async def get_country(self, country_id: int) -> Optional[Country]:
        """Get country by ID"""
        result = await self.db.execute(
            select(Country)
            .options(selectinload(Country.players))
            .where(Country.id == country_id)
        )
        return result.scalar_one_or_none()

    async def update_country_aspects(
        self, country_id: int, aspects: dict
    ) -> Optional[Country]:
        """Update country aspects"""
        country = await self.get_country(country_id)
        if not country:
            return None

        for aspect, value in aspects.items():
            if hasattr(country, aspect):
                setattr(country, aspect, value)

        await self.db.commit()
        await self.db.refresh(country)
        return country

    # Player management
    async def create_player(
        self,
        game_id: int,
        telegram_id: Optional[int] = None,
        vk_id: Optional[int] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        role: PlayerRole = PlayerRole.PLAYER,
        country_id: Optional[int] = None,
    ) -> Player:
        """Create a new player"""
        player = Player(
            game_id=game_id,
            telegram_id=telegram_id,
            vk_id=vk_id,
            username=username,
            display_name=display_name,
            role=role,
            country_id=country_id,
        )
        self.db.add(player)
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def assign_player_to_country(self, player_id: int, country_id: int) -> bool:
        """Assign player to a country"""
        result = await self.db.execute(select(Player).where(Player.id == player_id))
        player = result.scalar_one_or_none()

        if not player:
            return False

        player.country_id = country_id
        await self.db.commit()
        return True

    # Post management
    async def create_post(
        self,
        author_id: int,
        game_id: int,
        content: str,
        reply_to_id: Optional[int] = None,
    ) -> Post:
        """Create a new post"""
        post = Post(
            author_id=author_id,
            game_id=game_id,
            content=content,
            reply_to_id=reply_to_id,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def get_game_posts(self, game_id: int) -> List[Post]:
        """Get all posts for a game"""
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.verdicts))
            .where(Post.game_id == game_id)
            .order_by(Post.created_at)
        )
        return list(result.scalars().all())

    # Verdict management
    async def create_verdict(
        self, post_id: int, admin_id: int, result: str, reasoning: Optional[str] = None
    ) -> Verdict:
        """Create a verdict for a post"""
        verdict = Verdict(
            post_id=post_id, admin_id=admin_id, result=result, reasoning=reasoning
        )
        self.db.add(verdict)
        await self.db.commit()
        await self.db.refresh(verdict)
        return verdict

    # Statistics and reporting
    async def get_game_statistics(self, game_id: int) -> dict:
        """Get basic game statistics"""
        game = await self.get_game(game_id)
        if not game:
            return {}

        return {
            "game_id": game_id,
            "game_name": game.name,
            "status": game.status,
            "countries_count": len(game.countries),
            "players_count": len(game.players),
            "posts_count": len(game.posts),
            "created_at": game.created_at,
            "updated_at": game.updated_at,
        }
