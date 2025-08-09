# Команды для проверки деплоя

После завершения GitHub Actions выполните на сервере:

## 1. Проверить статус контейнера
```bash
docker ps | grep wpg-engine-bot
```

## 2. Проверить логи контейнера
```bash
docker logs wpg-engine-bot --tail 20
```

## 3. Если контейнер все еще показывает ошибку, принудительно обновить:
```bash
# Остановить и удалить старый контейнер
docker stop wpg-engine-bot
docker rm wpg-engine-bot

# Принудительно загрузить новый образ
docker pull cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest --platform linux/amd64

# Запустить новый контейнер
docker run -d \
  --name wpg-engine-bot \
  --restart unless-stopped \
  -e TG_TOKEN="$TG_TOKEN" \
  -e TG_ADMIN_ID="$TG_ADMIN_ID" \
  -e AI_OPENROUTER_API_KEY="$AI_OPENROUTER_API_KEY" \
  -e DB_URL="sqlite:///./data/wpg_engine.db" \
  -e LOG_LEVEL="INFO" \
  -v /opt/wpg-engine/data:/app/data \
  -v /opt/wpg-engine/logs:/app/logs \
  cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest
```

## 4. Проверить архитектуру образа
```bash
docker inspect cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest | grep Architecture
```

## 5. Проверить архитектуру сервера
```bash
uname -m
```

## 6. Если проблема все еще есть, проверить содержимое контейнера
```bash
docker run --rm -it cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest /bin/bash
# Внутри контейнера:
which python
python --version
ls -la /opt/venv/bin/python || echo "venv not found - good!"