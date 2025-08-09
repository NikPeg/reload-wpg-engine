# 🔐 Безопасный деплой WPG Engine

Руководство по безопасному деплою с защитой чувствительных данных.

## 🚨 Важно о безопасности

Все чувствительные данные (токены, ключи, ID серверов) теперь защищены:
- ✅ Файлы с токенами добавлены в `.gitignore`
- ✅ Используются шаблоны вместо файлов с реальными данными
- ✅ Скрипты создаются локально и не попадают в репозиторий

## 🚀 Быстрый старт

### 1. Первоначальная настройка (один раз)

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd reload-wpg-engine

# Создайте рабочие скрипты из шаблонов
./scripts/setup-deployment.sh
```

### 2. Настройте .env файл

```bash
# Отредактируйте .env файл
nano .env
```

**Обязательно укажите:**
```env
TG_TOKEN=ваш_токен_бота_от_BotFather
TG_ADMIN_ID=ваш_telegram_id
AI_OPENROUTER_API_KEY=ваш_ключ_openrouter
```

### 3. Настройте сервер (один раз)

```bash
# Настройка Docker и директорий на сервере
./scripts/setup-server.sh setup
```

### 4. Деплой бота

```bash
# Деплой одной командой
./scripts/quick-deploy.sh
```

## 📁 Структура файлов

```
scripts/
├── setup-deployment.sh      # Создание рабочих скриптов (в репозитории)
├── *.template.sh            # Шаблоны скриптов (в репозитории)
├── quick-deploy.sh          # Рабочий скрипт (НЕ в репозитории)
├── setup-server.sh          # Рабочий скрипт (НЕ в репозитории)
└── monitor.sh               # Мониторинг (в репозитории)
```

## 🔄 Рабочий процесс

### Ежедневное использование:

```bash
# 1. Разработка и тестирование локально
python main.py

# 2. Деплой на сервер
./scripts/quick-deploy.sh

# 3. Проверка работы
./scripts/monitor.sh status
```

### Мониторинг:

```bash
# Статус контейнера
./scripts/monitor.sh status

# Логи
./scripts/monitor.sh logs

# Health check
./scripts/monitor.sh health

# Бэкап базы данных
./scripts/monitor.sh backup
```

## 🛠️ Управление

### Если нужно пересоздать скрипты:

```bash
# Удалите старые скрипты (если есть)
rm scripts/quick-deploy.sh scripts/setup-server.sh

# Создайте новые
./scripts/setup-deployment.sh
```

### Если изменился ID сервера:

```bash
# Отредактируйте шаблон
nano scripts/setup-server.template.sh

# Пересоздайте скрипты
./scripts/setup-deployment.sh
```

## 🔧 Команды для вашего сервера

### Прямое подключение:
```bash
yc compute ssh --id epducvokks3etcr82gsu
```

### Быстрые команды:
```bash
# Статус контейнера
yc compute ssh --id epducvokks3etcr82gsu --command "docker ps"

# Логи бота
yc compute ssh --id epducvokks3etcr82gsu --command "docker logs wpg-engine-bot"

# Перезапуск бота
yc compute ssh --id epducvokks3etcr82gsu --command "docker restart wpg-engine-bot"
```

## 🚨 Устранение неполадок

### Если скрипты не работают:

1. **Проверьте .env файл:**
   ```bash
   cat .env | grep TG_TOKEN
   ```

2. **Пересоздайте скрипты:**
   ```bash
   ./scripts/setup-deployment.sh
   ```

3. **Проверьте права на выполнение:**
   ```bash
   ls -la scripts/*.sh
   ```

### Если Container Registry не найден:

```bash
# Создайте registry
yc container registry create --name wpg-engine-registry

# Проверьте
yc container registry list
```

### Если контейнер не запускается:

```bash
# Подключитесь к серверу
yc compute ssh --id epducvokks3etcr82gsu

# Проверьте логи
docker logs wpg-engine-bot

# Проверьте образы
docker images | grep wpg-engine
```

## 🔐 Безопасность

### Что защищено:
- ✅ Токены ботов
- ✅ API ключи
- ✅ ID серверов в рабочих скриптах
- ✅ Переменные окружения

### Что в репозитории:
- ✅ Шаблоны скриптов (без реальных данных)
- ✅ Скрипт настройки
- ✅ Документация
- ✅ Dockerfile и docker-compose файлы

### Что НЕ в репозитории:
- ❌ .env файлы с реальными токенами
- ❌ Рабочие скрипты деплоя
- ❌ Файлы с ключами и сертификатами

## 📝 Заметки

1. **При работе в команде:** каждый разработчик должен запустить `./scripts/setup-deployment.sh` после клонирования репозитория.

2. **При смене сервера:** обновите `SERVER_ID` в шаблоне и пересоздайте скрипты.

3. **Бэкапы:** регулярно создавайте бэкапы базы данных с помощью `./scripts/monitor.sh backup`.

4. **Обновления:** при обновлении кода просто запустите `./scripts/quick-deploy.sh`.

---

**Теперь ваши данные в безопасности! 🔐**