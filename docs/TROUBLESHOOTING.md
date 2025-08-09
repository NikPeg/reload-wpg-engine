# Устранение проблем деплоя

## Ошибка "jq: parse error: Invalid numeric literal"

### Описание проблемы
Ошибка возникает при выполнении команды `quick-deploy` и связана с некорректным парсингом JSON ответа от метаданных сервиса Yandex Cloud.

```
🔐 Настройка аутентификации Docker...
jq: parse error: Invalid numeric literal at line 1, column 4
ERROR: exit status 5
```

### Причины
1. Метаданные сервиса возвращают некорректный JSON
2. Отсутствует доступ к метаданным (VM не настроена правильно)
3. Проблемы с утилитой `jq`

### Решение

#### 1. Обновленный скрипт
Мы исправили скрипт [`quick-deploy.sh`](scripts/quick-deploy.sh), добавив:
- Проверку корректности JSON перед парсингом
- Альтернативный способ получения токена через `yc CLI`
- Более надежную обработку ошибок

#### 2. Диагностика проблемы
Запустите скрипт диагностики:
```bash
./scripts/debug-auth.sh
```

Этот скрипт проверит:
- Доступность метаданных сервиса
- Корректность JSON ответа
- Наличие и настройку `yc CLI`
- Статус Docker
- Наличие утилиты `jq`

#### 3. Ручное устранение

##### На сервере Yandex Cloud:

1. **Проверьте метаданные:**
```bash
curl -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token
```

2. **Установите/обновите jq:**
```bash
sudo apt-get update
sudo apt-get install jq
```

3. **Настройте yc CLI (если не настроен):**
```bash
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
source ~/.bashrc
yc init
```

4. **Проверьте права сервисного аккаунта:**
   - VM должна иметь привязанный сервисный аккаунт
   - Сервисный аккаунт должен иметь роли:
     - `container-registry.images.puller`
     - `container-registry.images.pusher`

##### На локальной машине:

1. **Проверьте настройку yc CLI:**
```bash
yc config list
yc iam create-token
```

2. **Убедитесь, что Docker настроен для работы с Yandex Container Registry:**
```bash
yc container registry configure-docker
```

### Альтернативные способы деплоя

#### 1. Использование GitHub Actions
Настройте автоматический деплой через GitHub Actions (файл уже создан: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml))

#### 2. Ручной деплой
```bash
# 1. Соберите образ локально
docker build -t your-app .

# 2. Загрузите в registry
docker tag your-app cr.yandex/your-registry-id/your-app:latest
docker push cr.yandex/your-registry-id/your-app:latest

# 3. Запустите на сервере
yc compute ssh --id YOUR_SERVER_ID --command "docker pull cr.yandex/your-registry-id/your-app:latest && docker run -d --name your-app your-app:latest"
```

### Проверка успешного деплоя

После исправления проблемы проверьте:

1. **Статус контейнера:**
```bash
yc compute ssh --id YOUR_SERVER_ID --command "docker ps"
```

2. **Логи приложения:**
```bash
yc compute ssh --id YOUR_SERVER_ID --command "docker logs wpg-engine-bot"
```

3. **Работоспособность бота:**
   - Отправьте команду `/start` в Telegram
   - Проверьте ответ бота

### Дополнительные ресурсы

- [Документация Yandex Container Registry](https://cloud.yandex.ru/docs/container-registry/)
- [Настройка сервисных аккаунтов](https://cloud.yandex.ru/docs/iam/operations/sa/create)
- [Работа с метаданными VM](https://cloud.yandex.ru/docs/compute/operations/vm-info/get-info#metadata)

### Получение помощи

Если проблема не решается:

1. Запустите [`./scripts/debug-auth.sh`](scripts/debug-auth.sh) и приложите вывод
2. Проверьте логи: `/Users/nspeganov/.config/yandex-cloud/logs/`
3. Используйте client-trace-id из ошибки для обращения в поддержку Yandex Cloud