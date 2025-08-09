# Добавление секрета YC_REGISTRY_ID в GitHub

## Проблема
GitHub Actions не может собрать Docker образ из-за отсутствующего секрета `YC_REGISTRY_ID`.

## Решение

### 1. Перейдите в настройки GitHub Secrets
https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/settings/secrets/actions

### 2. Добавьте новый секрет
1. Нажмите кнопку "New repository secret"
2. В поле "Name" введите: `YC_REGISTRY_ID`
3. В поле "Secret" введите: `YOUR_REGISTRY_ID`
4. Нажмите "Add secret"

### 3. Проверьте другие необходимые секреты
Убедитесь, что у вас есть все необходимые секреты:

- ✅ `YC_SA_JSON_CREDENTIALS` (уже обновлен)
- ❓ `YC_REGISTRY_ID` (нужно добавить: `YOUR_REGISTRY_ID`)
- ❓ `YC_CLOUD_ID` (должен быть: `YOUR_CLOUD_ID`)
- ❓ `YC_FOLDER_ID` (должен быть: `YOUR_FOLDER_ID`)
- ❓ `YC_INSTANCE_IP` (IP адрес вашего сервера)
- ❓ `YC_INSTANCE_USER` (пользователь на сервере, обычно `ubuntu`)
- ❓ `YC_INSTANCE_NAME` (имя инстанса в Yandex Cloud)
- ❓ `TG_TOKEN` (токен Telegram бота)
- ❓ `TG_ADMIN_ID` (ваш Telegram ID)
- ❓ `AI_OPENROUTER_API_KEY` (API ключ для AI, если используется)

### 4. После добавления секрета
Сообщите мне, и мы перезапустим деплой.