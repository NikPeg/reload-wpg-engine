"""
RAG (Retrieval-Augmented Generation) system for admin assistance
"""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wpg_engine.config.settings import settings
from wpg_engine.core.message_classifier import MessageClassifier
from wpg_engine.core.rag_analyzers import RAGAnalyzerFactory
from wpg_engine.models import Country, Message


class RAGSystem:
    """RAG system for analyzing player messages and providing context to admin"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Используем стандартные настройки
        self.api_key = settings.ai.openrouter_api_key
        self.model = settings.ai.default_model
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
        if not self.api_key:
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

        # Create appropriate analyzer based on message type
        analyzer = RAGAnalyzerFactory.create_analyzer(
            message_type, countries_data, sender_country_name
        )

        # Create prompt for LLM analysis
        prompt = analyzer.create_analysis_prompt(
            message_content, previous_admin_message
        )

        # Debug output: print the full prompt being sent to LLM
        print("=" * 80)
        print(f"🔍 RAG DEBUG: Тип сообщения: {message_type}")
        print("🔍 RAG DEBUG: Полный промпт для LLM:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        if previous_admin_message:
            print(
                f"✅ Найдено предыдущее сообщение админа: {previous_admin_message[:100]}..."
            )
        else:
            print("❌ Предыдущее сообщение админа НЕ найдено")
        print("=" * 80)

        try:
            # Get analysis from LLM
            context = await self._call_openrouter_api(prompt)
            return context
        except Exception as e:
            print(f"Error calling AI API: {e}")
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
            print(
                f"🎯 DEBUG: Найдено последнее сообщение админа: {latest_admin_message.content[:100]}..."
            )
            return latest_admin_message.content

        print("❌ DEBUG: Сообщения админа не найдены")
        return None

    async def _call_openrouter_api(self, prompt: str) -> str:
        """Call OpenRouter API"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,  # Увеличено для более полных ответов
            "temperature": 0.3,  # Низкая температура для более точных ответов
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
