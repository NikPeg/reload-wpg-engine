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

        prompt = f"""Определи тип сообщения игрока из страны "{sender_country}":
"{message}"

ТИПЫ СООБЩЕНИЙ:

ВОПРОС - сообщение СОДЕРЖИТ вопрос (даже если есть и другой текст)
Признаки: вопросительный знак, вопросительные слова (что, как, где, когда, почему, сколько, какой, кто)
Примеры: "какой год?", "сколько у нас войск и где они?", "кто напал?"

ПРИКАЗ - игрок дает команду или указание (действие, которое можно выполнить)
Признаки: глаголы в повелительном наклонении, слова действия
Примеры: "атаковать", "построить завод", "отправить войска", "объявить войну", "заключить мир"

ПРОЕКТ - долгосрочный план или масштабное действие (займет год и более)
Признаки: слова о строительстве, развитии, долгих процессах
Примеры: "развить экономику", "построить космодром", "захватить континент", "создать империю"

ИНОЕ - короткие реакции, подтверждения, эмоции, неясные сообщения
Примеры: "ок", "понял", "хаха", "да", "нет", "спасибо"

ПРАВИЛА:
- Если есть вопросительный знак или вопросительное слово = ВОПРОС
- Если есть глагол-действие = ПРИКАЗ или ПРОЕКТ (зависит от масштаба)
- Если текст короткий и не содержит действий = ИНОЕ

Ответь ОДНИМ словом: вопрос, приказ, проект или иное

Тип:"""

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
