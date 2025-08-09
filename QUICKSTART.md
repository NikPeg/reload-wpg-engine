# ⚡ Быстрый старт - WPG Engine Deployment

Пошаговое руководство для быстрого запуска автоматизированного деплоя.

## 🎯 За 5 минут до первого деплоя

### 1. Подготовка локального окружения

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd reload-wpg-engine

# Быстрая настройка
make setup

# Создайте .env файл
cp .env.example .env
```

### 2. Настройте .env файл

```bash
# Отредактируйте .env
nano .env

# Минимально необходимые настройки:
TG_TOKEN=your_telegram_bot_token_here
TG_ADMIN_ID=your_telegram_admin_id_here
```

### 3. Локальное тестирование

```bash
# Запуск в Docker
make run-dev

# Проверка логов
make logs

# Остановка
make down
```

## 🚀 Настройка автоматического деплоя

### 1. Yandex Cloud (5 минут)

```bash
# Создайте Container Registry
yc container registry create --name wpg-engine-registry

# Создайте виртуальную машину
yc compute instance create \
  --name wpg-engine-server \
  --zone ru-central1-a \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2004-lts,size=20 \
  --ssh-key ~/.ssh/id_rsa.pub

# Получите IP адрес
yc compute instance get wpg-engine-server --format json | jq -r '.network_interfaces[0].primary_v4_address.one_to_one_nat.address'
```

### 2. Настройка сервера (3 минуты)

```bash
# Подключитесь к серверу
yc compute ssh --name wpg-engine-server

# Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Настройте Docker для Yandex Registry
yc container registry configure-docker

# Создайте директории
sudo mkdir -p /opt/wpg-engine/{data,logs,backups}
sudo chown -R $USER:$USER /opt/wpg-engine
```

### 3. GitHub Secrets (2 минуты)

Добавьте в Settings → Secrets and variables → Actions:

```
TG_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TG_ADMIN_ID=123456789
YC_SA_JSON_CREDENTIALS={"id": "...", "service_account_id": "...", "private_key": "..."}
YC_REGISTRY_ID=crp1234567890abcdef
YC_CLOUD_ID=b1g1234567890abcdef
YC_FOLDER_ID=b1g1234567890abcdef
YC_INSTANCE_IP=51.250.1.1
YC_INSTANCE_USER=ubuntu
YC_INSTANCE_NAME=wpg-engine-server
```

## 🎉 Первый деплой

```bash
# Просто сделайте push в main ветку
git add .
git commit -m "Initial deployment setup"
git push origin main

# Или ручной деплой
make deploy-prod
```

## 📊 Проверка работы

```bash
# Проверка статуса
make status

# Просмотр логов
make logs

# Health check
make health
```

## 🔄 Ежедневное использование

```bash
# Разработка
make run-dev          # Запуск локально
make logs             # Просмотр логов
make test             # Тесты

# Деплой
git push origin main  # Автоматический деплой

# Мониторинг
make status           # Статус
make backup           # Бэкап БД
make restart          # Перезапуск
```

## 🆘 Если что-то пошло не так

```bash
# Проверьте логи GitHub Actions
# https://github.com/your-repo/actions

# Проверьте контейнер на сервере
ssh user@server-ip
docker ps
docker logs wpg-engine-bot

# Перезапустите
make restart

# Полная документация
cat DEPLOYMENT.md
```

## 📋 Чек-лист готовности

- [ ] Yandex Cloud настроен
- [ ] Сервер создан и настроен
- [ ] GitHub Secrets добавлены
- [ ] .env файл настроен
- [ ] Локальное тестирование прошло успешно
- [ ] Первый деплой выполнен
- [ ] Бот отвечает в Telegram

**Готово! Ваш бот теперь деплоится автоматически при каждом push в main ветку! 🎉**

---

💡 **Совет:** Добавьте в закладки команды `make status`, `make logs` и `make health` для быстрого мониторинга.