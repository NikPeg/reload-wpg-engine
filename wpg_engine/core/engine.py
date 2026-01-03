"""
Basic GameEngine class
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wpg_engine.models import (
    Country,
    Game,
    GameStatus,
    Message,
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
        description: str | None = None,
        setting: str = "Современность",
        max_players: int = 10,
        years_per_day: int = 1,
        max_points: int = 30,
        max_population: int = 10_000_000,
        settings: dict | None = None,
    ) -> Game:
        """Create a new game"""
        game = Game(
            name=name,
            description=description,
            setting=setting,
            max_players=max_players,
            years_per_day=years_per_day,
            max_points=max_points,
            max_population=max_population,
            settings=settings or {},
        )
        self.db.add(game)
        await self.db.commit()
        await self.db.refresh(game)
        return game

    async def get_game(self, game_id: int) -> Game | None:
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

    async def update_game_settings(
        self,
        game_id: int,
        name: str | None = None,
        description: str | None = None,
        setting: str | None = None,
        max_players: int | None = None,
        years_per_day: int | None = None,
        max_points: int | None = None,
        max_population: int | None = None,
    ) -> Game | None:
        """Update game settings"""
        game = await self.get_game(game_id)
        if not game:
            return None

        if name is not None:
            game.name = name
        if description is not None:
            game.description = description
        if setting is not None:
            game.setting = setting
        if max_players is not None:
            game.max_players = max_players
        if years_per_day is not None:
            game.years_per_day = years_per_day
        if max_points is not None:
            game.max_points = max_points
        if max_population is not None:
            game.max_population = max_population

        await self.db.commit()
        await self.db.refresh(game)
        return game

    # Country management
    async def create_country(
        self,
        game_id: int,
        name: str,
        description: str | None = None,
        aspects: dict | None = None,
        capital: str | None = None,
        population: int | None = None,
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

    async def get_country(self, country_id: int) -> Country | None:
        """Get country by ID"""
        result = await self.db.execute(
            select(Country)
            .options(selectinload(Country.player))
            .where(Country.id == country_id)
        )
        return result.scalar_one_or_none()

    async def update_country_aspects(
        self, country_id: int, aspects: dict
    ) -> Country | None:
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

    async def update_country_aspect_description(
        self, country_id: int, aspect: str, description: str
    ) -> Country | None:
        """Update specific aspect description"""
        country = await self.get_country(country_id)
        if not country:
            return None

        description_field = f"{aspect}_description"
        if hasattr(country, description_field):
            setattr(country, description_field, description)
            await self.db.commit()
            await self.db.refresh(country)
            return country

        return None

    async def update_country_aspect_value(
        self, country_id: int, aspect: str, value: int
    ) -> Country | None:
        """Update specific aspect value"""
        country = await self.get_country(country_id)
        if not country:
            return None

        if hasattr(country, aspect) and 1 <= value <= 10:
            setattr(country, aspect, value)
            await self.db.commit()
            await self.db.refresh(country)
            return country

        return None

    async def update_country_basic_info(
        self, country_id: int, **kwargs
    ) -> Country | None:
        """Update country basic information (name, description, capital, population)"""
        country = await self.get_country(country_id)
        if not country:
            return None

        allowed_fields = ["name", "description", "capital", "population"]
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(country, field):
                setattr(country, field, value)

        await self.db.commit()
        await self.db.refresh(country)
        return country

    async def update_country_synonyms(
        self, country_id: int, synonyms: list[str]
    ) -> Country | None:
        """Update country synonyms"""
        country = await self.get_country(country_id)
        if not country:
            return None

        country.synonyms = synonyms
        await self.db.commit()
        await self.db.refresh(country)
        return country

    async def delete_country(self, country_id: int) -> bool:
        """Delete a country and unassign all players from it"""
        country = await self.get_country(country_id)
        if not country:
            return False

        # Unassign player from this country (one-to-one relationship)
        if country.player:
            country.player.country_id = None

        # Delete the country
        await self.db.delete(country)
        await self.db.commit()
        return True

    # Player management
    async def create_player(
        self,
        game_id: int,
        telegram_id: int | None = None,
        vk_id: int | None = None,
        username: str | None = None,
        display_name: str | None = None,
        role: PlayerRole = PlayerRole.PLAYER,
        country_id: int | None = None,
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
        reply_to_id: int | None = None,
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

    async def get_game_posts(self, game_id: int) -> list[Post]:
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
        self, post_id: int, admin_id: int, result: str, reasoning: str | None = None
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

    async def get_countries_message_stats(self, game_id: int) -> list[dict]:
        """Get message statistics by countries for the last week"""
        # Calculate date one week ago
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Query to get message count by country for the last week
        # Only count messages from players (not admin replies)
        result = await self.db.execute(
            select(
                Country.name.label("country_name"),
                func.count(Message.id).label("message_count"),
            )
            .select_from(Country)
            .outerjoin(Player, Country.id == Player.country_id)
            .outerjoin(
                Message,
                (Player.id == Message.player_id)
                & (~Message.is_admin_reply)
                & (Message.created_at >= week_ago),
            )
            .where(Country.game_id == game_id)
            .group_by(Country.id, Country.name)
            .order_by(func.count(Message.id).desc(), Country.name)
        )

        stats = []
        for row in result:
            stats.append(
                {"country_name": row.country_name, "message_count": row.message_count}
            )

        return stats

    # Message management
    async def create_message(
        self,
        player_id: int,
        game_id: int,
        content: str,
        telegram_message_id: int | None = None,
        admin_telegram_message_id: int | None = None,
        reply_to_id: int | None = None,
        is_admin_reply: bool = False,
    ) -> Message:
        """Create a new message"""
        message = Message(
            player_id=player_id,
            game_id=game_id,
            content=content,
            telegram_message_id=telegram_message_id,
            admin_telegram_message_id=admin_telegram_message_id,
            reply_to_id=reply_to_id,
            is_admin_reply=is_admin_reply,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_player_messages(
        self, player_id: int, limit: int = 10
    ) -> list[Message]:
        """Get recent messages for a player (last 10 by default)"""
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.player), selectinload(Message.reply_to))
            .where(Message.player_id == player_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_message_by_telegram_id(
        self, telegram_message_id: int
    ) -> Message | None:
        """Get message by telegram message ID"""
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.player), selectinload(Message.game))
            .where(Message.telegram_message_id == telegram_message_id)
        )
        return result.scalar_one_or_none()

    async def get_message_by_id(self, message_id: int) -> Message | None:
        """Get message by database ID"""
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.player), selectinload(Message.game))
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_message_by_admin_telegram_id(
        self, admin_telegram_message_id: int
    ) -> Message | None:
        """Get message by admin's telegram message ID"""
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.player), selectinload(Message.game))
            .where(Message.admin_telegram_message_id == admin_telegram_message_id)
        )
        return result.scalar_one_or_none()

    async def get_previous_message_for_player(
        self, player_id: int, game_id: int, current_message_id: int | None = None
    ) -> Message | None:
        """Get the previous message in the conversation for a player"""
        query = (
            select(Message)
            .options(selectinload(Message.player))
            .where(Message.game_id == game_id)
            .where(Message.player_id == player_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
        )

        # If we have a current message ID, exclude it and get the one before it
        if current_message_id:
            query = query.where(Message.id < current_message_id)

        query = query.limit(1)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def find_country_by_name_or_synonym(
        self, game_id: int, search_name: str
    ) -> Country | None:
        """Find country by name or synonym (case-insensitive)

        This method searches ALL countries in the game, including NPC countries
        (countries without players). It uses a direct database query to ensure
        all countries are found regardless of whether they have a player assigned.
        """
        search_name_lower = search_name.lower().strip()

        # Get all countries in the game using direct query
        # This ensures we find ALL countries, including NPC countries without players
        result = await self.db.execute(
            select(Country).where(Country.game_id == game_id)
        )
        countries = result.scalars().all()

        for country in countries:
            # Check exact name match
            if country.name.lower() == search_name_lower:
                return country

            # Check synonyms
            if country.synonyms:
                for synonym in country.synonyms:
                    if synonym.lower() == search_name_lower:
                        return country

        return None
