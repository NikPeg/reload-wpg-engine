"""
Классификатор типов сообщений игроков с использованием LLM
"""

import logging

import httpx

from wpg_engine.config.settings import settings

logger = logging.getLogger(__name__)


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

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                logger.debug(
                    f"🔄 Отправка запроса классификации к OpenRouter API (model: {self.model})"
                )
                response = await client.post(url, json=data, headers=headers)

                logger.debug(
                    f"📡 OpenRouter API ответ классификации - статус: {response.status_code}"
                )

                # Логируем детали ошибки, если статус не 2xx
                if response.status_code >= 400:
                    logger.error(
                        f"❌ OpenRouter API ошибка классификации {response.status_code}"
                    )
                    logger.error(f"Response headers: {dict(response.headers)}")
                    try:
                        error_body = response.json()
                        logger.error(f"Response body: {error_body}")
                    except Exception:
                        logger.error(f"Response text: {response.text[:500]}")

                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                logger.debug(f"✅ Классификация получена: {content}")
                return content

        except httpx.TimeoutException as e:
            logger.error(f"⏱️ Timeout при классификации сообщения: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка при классификации: {e.response.status_code}")
            logger.error(f"URL: {e.request.url}")
            logger.error(f"Response: {e.response.text[:500]}")
            raise
        except httpx.RequestError as e:
            logger.error(f"❌ Ошибка сети при классификации: {type(e).__name__}: {e}")
            raise
        except KeyError as e:
            logger.error(
                f"❌ Неожиданный формат ответа классификации: отсутствует ключ {e}"
            )
            logger.error(f"Response: {result if 'result' in locals() else 'N/A'}")
            raise
        except Exception as e:
            logger.error(
                f"❌ Неожиданная ошибка при классификации: {type(e).__name__}: {e}"
            )
            logger.exception("Full traceback:")
            raise
