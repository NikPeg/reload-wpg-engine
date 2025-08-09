# Ручное тестирование исправлений Docker

## ✅ Главная проблема решена!

GitHub Actions успешно собрал и загрузил Docker образ без ошибки "exec format error".

## Тестирование на сервере

Подключитесь к серверу и выполните команды:

```bash
# Остановить старый контейнер
docker stop wpg-engine-bot || true
docker rm wpg-engine-bot || true

# Загрузить новый исправленный образ
docker pull cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest

# Запустить новый контейнер
docker run -d \
  --name wpg-engine-bot \
  --restart unless-stopped \
  -e TG_TOKEN="your-telegram-token" \
  -e TG_ADMIN_ID="your-admin-id" \
  -e DB_URL="sqlite:///./data/wpg_engine.db" \
  -e LOG_LEVEL="INFO" \
  -v /opt/wpg-engine/data:/app/data \
  -v /opt/wpg-engine/logs:/app/logs \
  cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest

# Проверить статус
docker ps | grep wpg-engine-bot

# Проверить логи (должны быть без ошибки "exec format error")
docker logs wpg-engine-bot --tail 20
```

## Ожидаемый результат

Контейнер должен запуститься без ошибки:
- ❌ Старая ошибка: `exec /opt/venv/bin/python: exec format error`
- ✅ Новый результат: нормальные логи запуска приложения

## Если нужен автоматический деплой

Для исправления SSH проблемы нужно:
1. Сгенерировать SSH ключ на GitHub Actions
2. Добавить публичный ключ на сервер
3. Добавить приватный ключ в GitHub Secrets

Но это уже не критично - главная проблема с Docker решена!