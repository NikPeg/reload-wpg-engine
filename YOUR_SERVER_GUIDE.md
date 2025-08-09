# 🚀 Деплой на ваш сервер (epducvokks3etcr82gsu)

Пошаговая инструкция для деплоя WPG Engine на ваш сервер Yandex Cloud.

## 📋 Что нужно сделать один раз

### 1. Настройте .env файл

```bash
# Создайте .env файл из примера
cp .env.example .env

# Отредактируйте его
nano .env
```

**Обязательно укажите:**
```
TG_TOKEN=ваш_токен_бота_от_BotFather
TG_ADMIN_ID=ваш_telegram_id
AI_OPENROUTER_API_KEY=ваш_ключ_openrouter (опционально)
```

### 2. Первоначальная настройка сервера

```bash
# Настройка сервера (Docker, директории и т.д.)
./scripts/setup-server.sh setup
```

## 🚀 Деплой (каждый раз когда нужно обновить)

### Простой способ - одна команда:

```bash
./scripts/quick-deploy.sh
```

Этот скрипт:
- Соберет Docker образ
- Загрузит его в Yandex Container Registry
- Остановит старый контейнер на сервере
- Запустит новый контейнер с обновленным кодом
- Покажет логи

### Ручной способ (если нужен контроль):

```bash
# 1. Сборка образа
docker build -t wpg-engine .

# 2. Получить ID registry
yc container registry list

# 3. Тегировать и загрузить
REGISTRY_ID="ваш_registry_id"
docker tag wpg-engine cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
docker push cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest

# 4. Деплой на сервер
yc compute ssh --id epducvokks3etcr82gsu --command "
docker stop wpg-engine-bot || true
docker rm wpg-engine-bot || true
docker pull cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
docker run -d --name wpg-engine-bot --restart unless-stopped \
  -e TG_TOKEN='ваш_токен' \
  -e TG_ADMIN_ID='ваш_id' \
  -v /opt/wpg-engine/data:/app/data \
  -v /opt/wpg-engine/logs:/app/logs \
  cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
"
```

## 📊 Мониторинг и управление

### Проверить статус бота:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker ps"
```

### Посмотреть логи:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker logs wpg-engine-bot"

# Последние 50 строк
yc compute ssh --id epducvokks3etcr82gsu --command "docker logs --tail 50 wpg-engine-bot"

# Следить за логами в реальном времени
yc compute ssh --id epducvokks3etcr82gsu --command "docker logs -f wpg-engine-bot"
```

### Перезапустить бота:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker restart wpg-engine-bot"
```

### Остановить бота:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker stop wpg-engine-bot"
```

### Создать бэкап базы данных:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "
docker cp wpg-engine-bot:/app/data/wpg_engine.db /opt/wpg-engine/backups/backup_$(date +%Y%m%d_%H%M%S).db
"
```

## 🔧 Полезные команды

### Подключиться к серверу:

```bash
yc compute ssh --id epducvokks3etcr82gsu
```

### Зайти внутрь контейнера:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker exec -it wpg-engine-bot /bin/bash"
```

### Проверить использование ресурсов:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "
echo 'Docker containers:'
docker ps
echo ''
echo 'Resource usage:'
docker stats --no-stream
echo ''
echo 'Disk usage:'
df -h /opt/wpg-engine
"
```

### Очистить старые образы:

```bash
yc compute ssh --id epducvokks3etcr82gsu --command "docker image prune -f"
```

## 🚨 Если что-то пошло не так

### Бот не отвечает:

1. Проверьте логи: `yc compute ssh --id epducvokks3etcr82gsu --command "docker logs wpg-engine-bot"`
2. Проверьте статус: `yc compute ssh --id epducvokks3etcr82gsu --command "docker ps"`
3. Перезапустите: `yc compute ssh --id epducvokks3etcr82gsu --command "docker restart wpg-engine-bot"`

### Контейнер не запускается:

1. Проверьте образ: `yc compute ssh --id epducvokks3etcr82gsu --command "docker images"`
2. Попробуйте запустить интерактивно: 
   ```bash
   yc compute ssh --id epducvokks3etcr82gsu --command "
   docker run -it --rm cr.yandex/REGISTRY_ID/wpg-engine-bot:latest /bin/bash
   "
   ```

### Проблемы с базой данных:

```bash
# Пересоздать базу данных
yc compute ssh --id epducvokks3etcr82gsu --command "
docker exec wpg-engine-bot python recreate_database.py
"
```

## 📝 Типичный рабочий процесс

1. **Разработка локально:**
   ```bash
   # Тестируете изменения
   python main.py
   ```

2. **Деплой на сервер:**
   ```bash
   ./scripts/quick-deploy.sh
   ```

3. **Проверка работы:**
   ```bash
   yc compute ssh --id epducvokks3etcr82gsu --command "docker logs --tail 20 wpg-engine-bot"
   ```

4. **Если нужно откатиться:**
   ```bash
   # Запустить предыдущую версию образа
   yc compute ssh --id epducvokks3etcr82gsu --command "docker run -d --name wpg-engine-bot-old previous_image"
   ```

---

**Готово! Теперь у вас есть полностью автоматизированный деплой! 🎉**

💡 **Совет:** Добавьте в закладки команду `./scripts/quick-deploy.sh` - это все что нужно для обновления бота.