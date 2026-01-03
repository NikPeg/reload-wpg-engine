# 🚀 Руководство по деплою WPG Engine

Руководство по развертыванию телеграм-бота WPG Engine на Yandex Cloud.

## 📋 Содержание

- [Быстрый старт](#быстрый-старт)
- [Локальная разработка](#локальная-разработка)
- [Автоматический деплой через GitHub Actions](#автоматический-деплой-через-github-actions)
- [Ручной деплой](#ручной-деплой)
- [Мониторинг](#мониторинг)
- [Устранение неполадок](#устранение-неполадок)

## 🚀 Быстрый старт

### 1. Локальная разработка

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd reload-wpg-engine

# Настройте окружение
make setup

# Отредактируйте .env файл
nano .env

# Запустите в режиме разработки
make run-dev

# Просмотр логов
make logs
```

### 2. Деплой в продакшн

```bash
# Настройте GitHub Secrets (см. раздел ниже)
# Затем просто сделайте push в main ветку
git push origin main

# Или используйте быстрый деплой скрипт
./scripts/quick-deploy.sh
```

## 💻 Локальная разработка

### Доступные команды (Makefile)

```bash
# Разработка
make build          # Собрать Docker образ
make run            # Запустить в продакшн режиме
make run-dev        # Запустить в режиме разработки
make test           # Запустить тесты
make lint           # Проверить код линтером
make format         # Форматировать код (Ruff)
make clean          # Очистить контейнеры

# Мониторинг
make status         # Статус контейнера
make logs           # Показать логи
make monitor        # Следить за логами
make backup         # Создать бэкап БД
make restart        # Перезапустить контейнер

# База данных
make migrate        # Запустить миграции
make recreate-db    # Пересоздать базу данных
```

### Использование Docker Compose

```bash
# Запуск в режиме разработки
make run-dev
# или
docker-compose -f deploy/docker-compose.dev.yml up -d

# Запуск в продакшн режиме
make run
# или
docker-compose -f deploy/docker-compose.yml up -d

# Просмотр логов
make logs
# или
docker-compose -f deploy/docker-compose.yml logs -f

# Остановка
make down
# или
docker-compose -f deploy/docker-compose.yml down
```

### Без Docker

```bash
# Установка зависимостей
make install

# Запуск
make local-run
# или
python main.py

# Тесты
make local-test
# или
python -m pytest tests/ -v
```

## 🤖 Автоматический деплой через GitHub Actions

### Настройка GitHub Secrets

Добавьте следующие секреты в настройках репозитория (Settings → Secrets and variables → Actions):

#### Обязательные секреты для Telegram

| Секрет | Описание | Пример |
|--------|----------|--------|
| `TG_TOKEN` | Токен Telegram бота | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `TG_ADMIN_ID` | ID администратора (положительное для пользователя, отрицательное для чата) | `123456789` или `-1001234567890` |

#### Обязательные секреты для Yandex Cloud

| Секрет | Описание | Получение |
|--------|----------|-----------|
| `YC_SA_JSON_CREDENTIALS` | JSON ключ сервисного аккаунта | `yc iam key create --service-account-id <ID> --output key.json` |
| `YC_REGISTRY_ID` | ID Container Registry | `yc container registry list` |
| `YC_CLOUD_ID` | ID облака | `yc config get cloud-id` |
| `YC_FOLDER_ID` | ID папки | `yc config get folder-id` |
| `YC_INSTANCE_IP` | IP адрес сервера | `yc compute instance get <name>` |
| `YC_INSTANCE_USER` | Пользователь на сервере | Обычно `ubuntu` |
| `YC_INSTANCE_NAME` | Имя инстанса | Имя вашей VM в Yandex Cloud |

#### Секреты для SSH

| Секрет | Описание | Получение |
|--------|----------|-----------|
| `SSH_PRIVATE_KEY` | Приватный SSH ключ для доступа к серверу | Содержимое `~/.ssh/id_rsa` |

#### Опциональные секреты для AI

| Секрет | Описание | По умолчанию |
|--------|----------|--------------|
| `AI_OPENROUTER_API_KEY` | API ключ OpenRouter для RAG системы | - |
| `AI_DEFAULT_MODEL` | Модель для RAG анализа | `deepseek/deepseek-chat-v3-0324` |

### Процесс автоматического деплоя

При push в ветку `main` запускается workflow:

1. **Тестирование** (`test` job)
   - Запуск pytest со всеми тестами
   - Блокирует деплой при ошибках

2. **Проверка качества кода** (`lint` job)
   - Линтинг с Ruff
   - Проверка форматирования

3. **Сборка и публикация** (`build-and-push` job)
   - Сборка Docker образа для `linux/amd64`
   - Загрузка в Yandex Container Registry
   - Использование кэша для ускорения

4. **Деплой** (`deploy` job)
   - Остановка старого контейнера
   - Загрузка нового образа на сервер
   - Запуск нового контейнера с переменными окружения
   - Проверка работоспособности (health check)

### Мониторинг деплоя

```bash
# Просмотр статуса в GitHub Actions
# https://github.com/your-username/your-repo/actions

# Проверка на сервере
ssh user@your-server-ip
docker ps | grep wpg-engine
docker logs wpg-engine-bot
```

## 🛠️ Ручной деплой

### Быстрый деплой через скрипт

Используйте готовый скрипт быстрого деплоя:

```bash
./scripts/quick-deploy.sh
```

Скрипт автоматически:
- Проверяет наличие `.env` файла
- Получает или создает Container Registry
- Собирает Docker образ
- Загружает образ в registry
- Деплоит на сервер через `yc compute ssh`
- Настраивает DNS серверы (8.8.8.8, 8.8.4.4, 1.1.1.1)
- Показывает логи после запуска

### Пошаговый ручной деплой

#### 1. Сборка образа

```bash
docker build -t wpg-engine -f deploy/Dockerfile .
```

#### 2. Получение Registry ID

```bash
# Список существующих registry
yc container registry list

# Или создать новый
yc container registry create --name wpg-engine-registry
```

#### 3. Загрузка в Registry

```bash
REGISTRY_ID="your_registry_id"
docker tag wpg-engine cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
docker push cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
```

#### 4. Деплой на сервер

```bash
SERVER_ID="your_server_id"

yc compute ssh --id $SERVER_ID << 'EOF'
# Остановка старого контейнера
docker stop wpg-engine-bot 2>/dev/null || true
docker rm wpg-engine-bot 2>/dev/null || true

# Загрузка нового образа
docker pull cr.yandex/REGISTRY_ID/wpg-engine-bot:latest

# Запуск нового контейнера
docker run -d \
  --name wpg-engine-bot \
  --restart unless-stopped \
  --dns 8.8.8.8 \
  --dns 8.8.4.4 \
  --dns 1.1.1.1 \
  -e TG_TOKEN="your_token" \
  -e TG_ADMIN_ID="your_admin_id" \
  -e AI_OPENROUTER_API_KEY="your_ai_key" \
  -e DB_URL="sqlite:///./data/wpg_engine.db" \
  -e LOG_LEVEL="INFO" \
  -v /opt/wpg-engine/data:/app/data \
  -v /opt/wpg-engine/logs:/app/logs \
  cr.yandex/REGISTRY_ID/wpg-engine-bot:latest

# Проверка запуска
docker logs wpg-engine-bot
EOF
```

## 📊 Мониторинг

### Проверка статуса

```bash
# Локально через Makefile
make status

# На сервере напрямую
yc compute ssh --id SERVER_ID --command "docker ps | grep wpg-engine"
```

### Логи

```bash
# Локально
make logs           # Последние логи
make monitor        # Следить в реальном времени

# На сервере
yc compute ssh --id SERVER_ID --command "docker logs wpg-engine-bot"
yc compute ssh --id SERVER_ID --command "docker logs --tail 50 wpg-engine-bot"
yc compute ssh --id SERVER_ID --command "docker logs -f wpg-engine-bot"
```

### Бэкапы базы данных

```bash
# Локально
make backup

# На сервере
yc compute ssh --id SERVER_ID << 'EOF'
docker cp wpg-engine-bot:/app/data/wpg_engine.db \
  /opt/wpg-engine/backups/backup_$(date +%Y%m%d_%H%M%S).db
EOF
```

### Перезапуск

```bash
# Локально
make restart

# На сервере
yc compute ssh --id SERVER_ID --command "docker restart wpg-engine-bot"
```

### Использование ресурсов

```bash
yc compute ssh --id SERVER_ID << 'EOF'
echo "=== Docker containers ==="
docker ps

echo ""
echo "=== Resource usage ==="
docker stats --no-stream

echo ""
echo "=== Disk usage ==="
df -h /opt/wpg-engine
EOF
```

## 🔧 Устранение неполадок

### Контейнер не запускается

```bash
# Проверить логи
docker logs wpg-engine-bot

# Проверить образ
docker images | grep wpg-engine

# Проверить переменные окружения
docker inspect wpg-engine-bot | grep -A 20 "Env"
```

### Ошибка DNS (Cannot connect to host api.telegram.org)

**Решение:** DNS серверы уже настроены в Docker Compose файлах и скриптах деплоя.

Если проблема сохраняется, проверьте:

```bash
# Проверить DNS в контейнере
docker exec wpg-engine-bot cat /etc/resolv.conf

# Должно быть:
# nameserver 8.8.8.8
# nameserver 8.8.4.4
# nameserver 1.1.1.1

# Проверить разрешение домена
docker exec wpg-engine-bot nslookup api.telegram.org
```

### Проблемы с базой данных

```bash
# Проверить подключение к БД
docker exec wpg-engine-bot python -c "
import asyncio
from wpg_engine.models import get_db
asyncio.run(get_db().__anext__())
"

# Пересоздать базу данных (ОСТОРОЖНО! Удалит все данные)
docker exec wpg-engine-bot python scripts/recreate_database.py

# Запустить миграции
docker exec wpg-engine-bot python scripts/run_migrations.py
```

### Проблемы с аутентификацией Yandex Cloud

```bash
# Создать новый ключ сервисного аккаунта
yc iam service-account list
yc iam key create --service-account-id <SERVICE_ACCOUNT_ID> --output key.json

# Настроить Docker для работы с Registry
yc container registry configure-docker
```

### Откат версии

```bash
# Посмотреть доступные образы
yc container image list --registry-id your-registry-id

# Запустить предыдущую версию
docker run -d --name wpg-engine-bot \
  cr.yandex/your-registry-id/wpg-engine-bot:main-abc123def
```

## 📚 Дополнительные команды

### Docker

```bash
# Очистка системы
docker system prune -a

# Просмотр использования ресурсов
docker stats

# Экспорт образа
docker save wpg-engine > wpg-engine.tar

# Импорт образа
docker load < wpg-engine.tar
```

### Yandex Cloud

```bash
# Список инстансов
yc compute instance list

# Подключение к инстансу
yc compute ssh --id SERVER_ID

# Информация об инстансе
yc compute instance get SERVER_ID
```

## 🔐 Безопасность

### Рекомендации

1. **Используйте отдельные токены** для разных окружений
2. **Регулярно ротируйте секреты** в GitHub
3. **Ограничьте доступ** к серверу по SSH ключам
4. **Не храните секреты в коде** - только в `.env` и GitHub Secrets
5. **Регулярно обновляйте** базовые образы Docker

### Проверка безопасности

```bash
# Проверка уязвимостей в образе (если установлен docker scan)
docker scan wpg-engine

# Проверка открытых портов на сервере
nmap your-server-ip

# Мониторинг логов безопасности на сервере
ssh user@server "sudo tail -f /var/log/auth.log"
```

## 🏗️ Архитектура Docker

### Структура образа

```dockerfile
FROM python:3.11-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential sqlite3 procps

# Создание непривилегированного пользователя
RUN groupadd -r wpgbot && useradd -r -g wpgbot wpgbot

# Python зависимости
COPY requirements.txt .
RUN pip install -r requirements.txt

# Код приложения
COPY --chown=wpgbot:wpgbot . .

# Запуск от имени непривилегированного пользователя
USER wpgbot

CMD ["python", "main.py"]
```

### DNS настройки

Все конфигурации Docker содержат DNS серверы для надежной работы:

```yaml
services:
  wpg-bot:
    dns:
      - 8.8.8.8      # Google DNS Primary
      - 8.8.4.4      # Google DNS Secondary  
      - 1.1.1.1      # Cloudflare DNS
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте раздел [Устранение неполадок](#устранение-неполадок)
2. Посмотрите логи: `make logs`
3. Проверьте статус: `make status`
4. Создайте issue в репозитории с подробным описанием

---

**Удачного деплоя! 🚀**
