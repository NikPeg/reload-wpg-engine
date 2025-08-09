#!/bin/bash

# Setup Deployment Scripts
# This script creates working deployment scripts from templates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

# Default server ID
DEFAULT_SERVER_ID="epducvokks3etcr82gsu"

echo_info "🔧 Настройка скриптов деплоя"

# Check if .env exists
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    echo_warning ".env файл не найден"
    echo_info "Создание .env из примера..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo_success ".env файл создан"
    echo_warning "Пожалуйста, отредактируйте .env файл с вашими настройками:"
    echo "  - TG_TOKEN=ваш_токен_бота"
    echo "  - TG_ADMIN_ID=ваш_telegram_id"
    echo ""
fi

# Create quick-deploy.sh from template
echo_info "Создание scripts/quick-deploy.sh..."
if [[ -f "$SCRIPT_DIR/quick-deploy.template.sh" ]]; then
    cp "$SCRIPT_DIR/quick-deploy.template.sh" "$SCRIPT_DIR/quick-deploy.sh"
    chmod +x "$SCRIPT_DIR/quick-deploy.sh"
    echo_success "scripts/quick-deploy.sh создан"
else
    echo_error "Шаблон quick-deploy.template.sh не найден"
fi

# Create setup-server.sh from template
echo_info "Создание scripts/setup-server.sh..."
if [[ -f "$SCRIPT_DIR/setup-server.template.sh" ]]; then
    # Replace the server ID in the template
    sed "s/your_server_id_here/$DEFAULT_SERVER_ID/g" "$SCRIPT_DIR/setup-server.template.sh" > "$SCRIPT_DIR/setup-server.sh"
    chmod +x "$SCRIPT_DIR/setup-server.sh"
    echo_success "scripts/setup-server.sh создан с SERVER_ID: $DEFAULT_SERVER_ID"
else
    echo_error "Шаблон setup-server.template.sh не найден"
fi

# Make all scripts executable
echo_info "Установка прав на выполнение..."
chmod +x "$SCRIPT_DIR"/*.sh

echo_success "🎉 Настройка завершена!"
echo ""
echo_info "Следующие шаги:"
echo "1. Отредактируйте .env файл с вашими настройками"
echo "2. Запустите: ./scripts/setup-server.sh setup"
echo "3. Запустите: ./scripts/quick-deploy.sh"
echo ""
echo_warning "ВАЖНО: Файлы scripts/quick-deploy.sh и scripts/setup-server.sh"
echo_warning "добавлены в .gitignore и не будут загружены в репозиторий"
echo_warning "для защиты ваших данных."