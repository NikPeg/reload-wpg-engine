"""
Классификатор типов сообщений игроков с использованием LLM
"""

import logging

from wpg_engine.core.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


class MessageClassifier:
    """Классификатор для определения типа сообщения игрока"""

    def __init__(self):
        self.client = OpenRouterClient()

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
        if not self.client.api_key:
            return "иное"

        prompt = self._create_classification_prompt(
            message_content, sender_country_name
        )

        try:
            # Используем короткий max_tokens и низкую температуру для классификации
            classification = await self.client.call_api(
                prompt=prompt,
                max_tokens=10,
                temperature=0.1,
                max_retries=2,
                timeout_seconds=60.0,
            )
            # Нормализуем ответ к одному из четырех типов
            return self._normalize_classification(classification)
        except Exception as e:
            logger.error(
                f"❌ Ошибка при классификации сообщения: {type(e).__name__}: {e}"
            )
            logger.exception("Full traceback:")
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
