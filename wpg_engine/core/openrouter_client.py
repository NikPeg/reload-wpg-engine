"""
Клиент для работы с OpenRouter API
Универсальный модуль для всех запросов к LLM через OpenRouter
"""

import asyncio
import logging

import httpx

from wpg_engine.config.settings import settings

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Клиент для выполнения запросов к OpenRouter API с retry логикой"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Инициализация клиента

        Args:
            api_key: API ключ OpenRouter (по умолчанию из settings)
            model: Модель для использования (по умолчанию из settings)
        """
        self.api_key = api_key or settings.ai.openrouter_api_key
        self.model = model or settings.ai.default_model

    async def call_api(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.3,
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
    ) -> str:
        """
        Выполнить запрос к OpenRouter API с автоматическими повторами при timeout

        Args:
            prompt: Текст промпта для LLM
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации (0.0-1.0)
            max_retries: Количество повторных попыток при timeout (всего попыток = 1 + max_retries)
            timeout_seconds: Timeout в секундах для read операции

        Returns:
            Текст ответа от LLM

        Raises:
            httpx.TimeoutException: Если все попытки завершились timeout
            httpx.HTTPStatusError: При HTTP ошибках от API
            httpx.RequestError: При ошибках сети
            KeyError: При неожиданном формате ответа
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key не настроен")

        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Детальная настройка timeout
        timeout = httpx.Timeout(
            connect=10.0,  # Время на установку соединения
            read=timeout_seconds,  # Время на чтение ответа
            write=10.0,  # Время на отправку запроса
            pool=5.0,  # Время на получение соединения из пула
        )

        max_attempts = max_retries + 1
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    logger.debug(
                        f"🔄 Отправка запроса к OpenRouter API (model: {self.model}, "
                        f"попытка {attempt}/{max_attempts}, max_tokens: {max_tokens})"
                    )
                    response = await client.post(url, json=data, headers=headers)

                    logger.debug(
                        f"📡 OpenRouter API ответ - статус: {response.status_code}"
                    )

                    # Логируем детали ошибки, если статус не 2xx
                    if response.status_code >= 400:
                        logger.error(f"❌ OpenRouter API ошибка {response.status_code}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        try:
                            error_body = response.json()
                            logger.error(f"Response body: {error_body}")
                        except Exception:
                            logger.error(f"Response text: {response.text[:500]}")

                    response.raise_for_status()

                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    logger.debug(
                        f"✅ OpenRouter API успешно вернул ответ (длина: {len(content)} символов)"
                    )
                    return content

            except (httpx.TimeoutException, httpx.ReadTimeout) as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(
                        f"⏱️ Timeout при запросе к OpenRouter API "
                        f"(попытка {attempt}/{max_attempts}), повторяю через 2 секунды..."
                    )
                    await asyncio.sleep(2)  # Задержка перед повтором
                else:
                    logger.error(
                        f"⏱️ Timeout после {max_attempts} попыток к OpenRouter API: {e}"
                    )
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"❌ HTTP ошибка от OpenRouter API: {e.response.status_code}"
                )
                logger.error(f"URL: {e.request.url}")
                logger.error(f"Response: {e.response.text[:500]}")
                raise  # HTTP ошибки не ретраим
            except httpx.RequestError as e:
                logger.error(
                    f"❌ Ошибка сети при запросе к OpenRouter API: {type(e).__name__}: {e}"
                )
                raise  # Ошибки сети не ретраим
            except KeyError as e:
                logger.error(
                    f"❌ Неожиданный формат ответа от OpenRouter API: отсутствует ключ {e}"
                )
                logger.error(f"Response: {result if 'result' in locals() else 'N/A'}")
                raise  # Ошибки формата не ретраим
            except Exception as e:
                logger.error(
                    f"❌ Неожиданная ошибка при вызове OpenRouter API: {type(e).__name__}: {e}"
                )
                logger.exception("Full traceback:")
                raise  # Неожиданные ошибки не ретраим

        # Если все попытки завершились timeout, пробрасываем последнее исключение
        if last_exception:
            raise last_exception

        # Не должно происходить, но на всякий случай
        raise RuntimeError("Неожиданное завершение цикла retry без результата")
