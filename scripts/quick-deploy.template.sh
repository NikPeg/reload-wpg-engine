#!/bin/bash

# Quick Deploy Script Template for WPG Engine
# Copy this to quick-deploy.sh and configure your settings

set -e

SERVER_ID="epducvokks3etcr82gsu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
echo_success() { echo -e "${GREEN}✅ $1${NC}"; }
echo_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
echo_error() { echo -e "${RED}❌ $1${NC}"; }

# Check if .env exists
if [[ ! -f .env ]]; then
    echo_error ".env файл не найден!"
    echo_info "Создайте .env файл с вашими настройками:"
    echo "cp .env.example .env"
    echo "nano .env"
    exit 1
fi

# Load environment variables
source .env

# Check required variables
if [[ -z "$TG_TOKEN" ]]; then
    echo_error "TG_TOKEN не установлен в .env файле"
    exit 1
fi

if [[ -z "$TG_ADMIN_ID" ]]; then
    echo_error "TG_ADMIN_ID не установлен в .env файле"
    exit 1
fi

echo_info "🚀 Быстрый деплой на сервер $SERVER_ID"

# Get or create registry
echo_info "📦 Проверка Container Registry..."
REGISTRY_ID=$(yc container registry list --format json | jq -r '.[0].id' 2>/dev/null || echo "")

if [[ -z "$REGISTRY_ID" ]] || [[ "$REGISTRY_ID" == "null" ]]; then
    echo_info "Создание Container Registry..."
    yc container registry create --name wpg-engine-registry
    REGISTRY_ID=$(yc container registry list --format json | jq -r '.[0].id')
fi

echo_success "Registry ID: $REGISTRY_ID"

# Build image
echo_info "🔨 Сборка Docker образа..."
docker build -t cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest .

# Push image
echo_info "📤 Загрузка образа в registry..."
docker push cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest

# Deploy to server
echo_info "🚀 Деплой на сервер..."

# Create deployment script with environment variables
cat > /tmp/quick_deploy.sh << EOF
#!/bin/bash
set -e

# Variables
IMAGE_URL="cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest"
CONTAINER_NAME="wpg-engine-bot"

echo "🔄 Остановка старого контейнера..."
docker stop \$CONTAINER_NAME 2>/dev/null || true
docker rm \$CONTAINER_NAME 2>/dev/null || true

echo "📥 Загрузка нового образа..."
docker pull \$IMAGE_URL

echo "🚀 Запуск нового контейнера..."
docker run -d \\
  --name \$CONTAINER_NAME \\
  --restart unless-stopped \\
  -e TG_TOKEN="$TG_TOKEN" \\
  -e TG_ADMIN_ID="$TG_ADMIN_ID" \\
  -e AI_OPENROUTER_API_KEY="${AI_OPENROUTER_API_KEY:-}" \\
  -e DB_URL="sqlite:///./data/wpg_engine.db" \\
  -e LOG_LEVEL="INFO" \\
  -e DEBUG="false" \\
  -v /opt/wpg-engine/data:/app/data \\
  -v /opt/wpg-engine/logs:/app/logs \\
  \$IMAGE_URL

echo "🧹 Очистка старых образов..."
docker image prune -f

echo "✅ Деплой завершен!"
echo ""
echo "📊 Статус контейнера:"
docker ps | grep \$CONTAINER_NAME

echo ""
echo "📝 Последние логи:"
sleep 5
docker logs --tail 20 \$CONTAINER_NAME
EOF

# Copy and execute deployment script
yc compute ssh --id $SERVER_ID --command "mkdir -p /opt/wpg-engine/{data,logs,backups}"

echo_info "📋 Копирование скрипта деплоя..."
yc compute scp /tmp/quick_deploy.sh $SERVER_ID:/tmp/quick_deploy.sh

echo_info "🎯 Выполнение деплоя на сервере..."
yc compute ssh --id $SERVER_ID --command "chmod +x /tmp/quick_deploy.sh && /tmp/quick_deploy.sh && rm /tmp/quick_deploy.sh"

# Clean up
rm /tmp/quick_deploy.sh

echo_success "🎉 Деплой успешно завершен!"
echo ""
echo_info "Полезные команды для мониторинга:"
echo "yc compute ssh --id $SERVER_ID --command 'docker ps'"
echo "yc compute ssh --id $SERVER_ID --command 'docker logs wpg-engine-bot'"
echo "yc compute ssh --id $SERVER_ID --command 'docker restart wpg-engine-bot'"