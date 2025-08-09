# Исправление аутентификации Yandex Cloud

## Проблема
GitHub Actions не может войти в Yandex Container Registry из-за ошибки "Password required".

## Решение

### 1. Создать новый ключ сервисного аккаунта

```bash
# Получить ID сервисного аккаунта
yc iam service-account list

# Создать новый ключ (замените SERVICE_ACCOUNT_ID на ваш ID)
yc iam key create --service-account-id <SERVICE_ACCOUNT_ID> --output key.json

# Показать содержимое ключа
cat key.json
```

### 2. Обновить GitHub Secret

1. Перейдите в настройки репозитория: https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/settings/secrets/actions
2. Найдите секрет `YC_SA_JSON_CREDENTIALS`
3. Нажмите "Update" 
4. Вставьте содержимое файла `key.json`
5. Сохраните

### 3. Проверить права сервисного аккаунта

```bash
# Проверить роли сервисного аккаунта
yc iam service-account list-access-bindings <SERVICE_ACCOUNT_ID>
```

Сервисный аккаунт должен иметь роли:
- `container-registry.images.pusher` - для загрузки образов
- `compute.admin` или `compute.instanceAdmin` - для управления инстансами

### 4. После обновления секрета

Сделайте новый коммит или перезапустите последний workflow:

```bash
# Перезапустить последний workflow
gh run rerun 16847672817

# Или сделать пустой коммит
git commit --allow-empty -m "Trigger deployment after fixing YC auth"
git push origin main
```

### 5. Альтернативное решение - ручной деплой

Если проблемы с GitHub Actions продолжаются, можно собрать и загрузить образ вручную:

```bash
# Локально собрать образ
docker build -t wpg-engine-bot .

# Тегировать для Yandex Registry
docker tag wpg-engine-bot cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest

# Войти в registry
yc container registry configure-docker

# Загрузить образ
docker push cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest
```

Затем на сервере:

```bash
# Остановить старый контейнер
docker stop wpg-engine-bot
docker rm wpg-engine-bot

# Загрузить новый образ
docker pull cr.yandex/YOUR_REGISTRY_ID/wpg-engine-bot:latest

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