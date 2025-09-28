"""
Классификатор типов сообщений игроков с использованием LLM
"""

import httpx

from wpg_engine.config.settings import settings


class MessageClassifier:
    """Классификатор для определения типа сообщения игрока"""

    def __init__(self):
        self.api_key = settings.ai.openrouter_api_key
        self.model = settings.ai.default_model

    async def classify_message(
        self, message_content: str, sender_country_name: str
    ) -> str:
        """
        Классифицировать сообщение игрока по типу

        Args:
            message_content: Текст сообщения игрока
            sender_country_name: Название страны отправителя

        Returns:
            Тип сообщения: "вопрос", "приказ", "проект", "иное"
        """
        if not self.api_key:
            return "иное"

        prompt = self._create_classification_prompt(
            message_content, sender_country_name
        )

        try:
            classification = await self._call_openrouter_api(prompt)
            # Нормализуем ответ к одному из четырех типов
            return self._normalize_classification(classification)
        except Exception as e:
            print(f"Error classifying message: {e}")
            return "иное"

    def _create_classification_prompt(self, message: str, sender_country: str) -> str:
        """Создать промпт для классификации сообщения"""

        prompt = f"""Ты помощник администратора многопользовательской стратегической игры.

Игрок из страны "{sender_country}" отправил сообщение:
"{message}"

Твоя задача - определить ТИП этого сообщения. Есть 4 типа:

1. ВОПРОС - игрок спрашивает информацию, хочет что-то узнать
   Примеры: "какой сейчас год?", "какая страна на нас напала?", "с кем мы воюем?", "сколько у нас населения?"

2. ПРИКАЗ - игрок отдает конкретное указание, которое можно выполнить быстро (менее чем за год)
   Примеры: "отправить разведчиков", "объявить войну Вирджинии", "переименовать государство", "заключить мир"

3. ПРОЕКТ - игрок предлагает долгосрочное действие, которое займет много времени (год и более)
   Примеры: "захватить Вирджинию", "построить ракету", "перейти к демократии", "построить пирамиды"

4. ИНОЕ - все остальное (эмоциональные реакции, бессмысленные сообщения, неясные высказывания)
   Примеры: "ахахха", "понял", "ну ладно", "грустно", "хорошо"

ВАЖНО:
- Приказ отличается от проекта тем, что приказ можно выполнить быстро, менее чем за год
- Проект - это нечто долгосрочное, например строительство, завоевания, реформы
- Отвечай ТОЛЬКО одним словом: "вопрос", "приказ", "проект" или "иное"

Тип сообщения:"""

        return prompt

    def _normalize_classification(self, classification: str) -> str:
        """Нормализовать классификацию к одному из четырех типов"""
        classification_lower = classification.lower().strip()

        # Проверяем точные совпадения
        if "вопрос" in classification_lower:
            return "вопрос"
        elif "приказ" in classification_lower:
            return "приказ"
        elif "проект" in classification_lower:
            return "проект"
        else:
            return "иное"

    async def _call_openrouter_api(self, prompt: str) -> str:
        """Вызвать OpenRouter API для классификации"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 10,  # Короткий ответ - только тип
            "temperature": 0.1,  # Очень низкая температура для стабильности
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
