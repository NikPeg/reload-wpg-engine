"""
RAG (Retrieval-Augmented Generation) system for admin assistance
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wpg_engine.core.message_classifier import MessageClassifier
from wpg_engine.core.openrouter_client import OpenRouterClient
from wpg_engine.core.rag_analyzers import RAGAnalyzerFactory
from wpg_engine.models import Country, Message

logger = logging.getLogger(__name__)


class RAGSystem:
    """RAG system for analyzing player messages and providing context to admin"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = OpenRouterClient()
        self.classifier = MessageClassifier()

    async def generate_admin_context(
        self,
        message_content: str,
        sender_country_name: str,
        game_id: int,
        player_id: int,
    ) -> str:
        """
        Generate context for admin based on player message

        Args:
            message_content: The player's message
            sender_country_name: Name of sender's country
            game_id: Game ID to get countries data
            player_id: Player ID to check for previous admin messages

        Returns:
            Context string for admin
        """
        if not self.client.api_key:
            return ""

        # Get all countries data from the game
        countries_data = await self._get_all_countries_data(game_id)

        if not countries_data:
            return ""

        # Check for previous admin message to provide context
        previous_admin_message = await self._get_previous_admin_message(
            player_id, game_id
        )

        # Classify message type
        message_type = await self.classifier.classify_message(
            message_content, sender_country_name
        )

        # For "иное" type messages, don't run RAG - just forward to admin
        if message_type == "иное":
            logger.info("=" * 80)
            logger.info(f"🔍 RAG DEBUG: Тип сообщения: {message_type}")
            logger.info(
                "❌ RAG не запускается для типа 'иное' - сообщение просто пересылается админу"
            )
            logger.info("=" * 80)
            return ""

        # Create appropriate analyzer based on message type
        analyzer = RAGAnalyzerFactory.create_analyzer(
            message_type, countries_data, sender_country_name
        )

        # Create prompt for LLM analysis
        prompt = analyzer.create_analysis_prompt(
            message_content, previous_admin_message
        )

        # Debug output: print the full prompt being sent to LLM
        logger.info("=" * 80)
        logger.info(f"🔍 RAG DEBUG: Тип сообщения: {message_type}")
        logger.info("🔍 RAG DEBUG: Полный промпт для LLM:")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)
        if previous_admin_message:
            logger.info(
                f"✅ Найдено предыдущее сообщение админа: {previous_admin_message[:100]}..."
            )
        else:
            logger.info("❌ Предыдущее сообщение админа НЕ найдено")
        logger.info("=" * 80)

        try:
            # Get analysis from LLM using shared client
            context = await self.client.call_api(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3,
                max_retries=2,
                timeout_seconds=60.0,
            )
            return context
        except Exception as e:
            logger.error(
                f"❌ Ошибка при вызове AI API для генерации контекста: {type(e).__name__}: {e}"
            )
            logger.exception("Full traceback:")
            return ""

    async def _get_all_countries_data(self, game_id: int) -> list[dict[str, Any]]:
        """Get data for all countries in the game"""
        result = await self.db.execute(
            select(Country).where(Country.game_id == game_id)
        )
        countries = result.scalars().all()

        countries_data = []
        for country in countries:
            aspects = country.get_aspects()

            country_info = {
                "name": country.name,
                "capital": country.capital or "Не указана",
                "population": country.population or 0,
                "synonyms": country.synonyms or [],
                "aspects": {
                    "economy": aspects["economy"]["value"],
                    "military": aspects["military"]["value"],
                    "foreign_policy": aspects["foreign_policy"]["value"],
                    "territory": aspects["territory"]["value"],
                    "technology": aspects["technology"]["value"],
                    "religion_culture": aspects["religion_culture"]["value"],
                    "governance_law": aspects["governance_law"]["value"],
                    "construction_infrastructure": aspects[
                        "construction_infrastructure"
                    ]["value"],
                    "social_relations": aspects["social_relations"]["value"],
                    "intelligence": aspects["intelligence"]["value"],
                },
                "descriptions": {
                    "economy": aspects["economy"]["description"],
                    "military": aspects["military"]["description"],
                    "foreign_policy": aspects["foreign_policy"]["description"],
                    "territory": aspects["territory"]["description"],
                    "technology": aspects["technology"]["description"],
                    "religion_culture": aspects["religion_culture"]["description"],
                    "governance_law": aspects["governance_law"]["description"],
                    "construction_infrastructure": aspects[
                        "construction_infrastructure"
                    ]["description"],
                    "social_relations": aspects["social_relations"]["description"],
                    "intelligence": aspects["intelligence"]["description"],
                },
            }
            countries_data.append(country_info)

        return countries_data

    async def _get_previous_admin_message(
        self, player_id: int, game_id: int
    ) -> str | None:
        """Get the most recent admin message for context if it exists"""

        # Get all admin messages for this player, ordered by creation time (most recent first)
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.player))
            .where(Message.player_id == player_id)
            .where(Message.game_id == game_id)
            .where(Message.is_admin_reply)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        latest_admin_message = result.scalar_one_or_none()

        if latest_admin_message:
            logger.debug(
                f"🎯 DEBUG: Найдено последнее сообщение админа: {latest_admin_message.content[:100]}..."
            )
            return latest_admin_message.content

        logger.debug("❌ DEBUG: Сообщения админа не найдены")
        return None
