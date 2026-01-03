#!/bin/bash

# DNS Troubleshooting Script for WPG Engine
# Проверяет настройки DNS и помогает диагностировать проблемы с подключением к Telegram API

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
echo_success() { echo -e "${GREEN}✅ $1${NC}"; }
echo_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
echo_error() { echo -e "${RED}❌ $1${NC}"; }

echo_info "=== DNS Troubleshooting для WPG Engine ==="
echo ""

# Check if docker is running
echo_info "1. Проверка Docker..."
if ! docker info > /dev/null 2>&1; then
    echo_error "Docker не запущен или недоступен"
    exit 1
fi
echo_success "Docker работает"
echo ""

# Check if container exists
echo_info "2. Проверка контейнера..."
CONTAINER_NAME="wpg-engine-bot"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo_success "Контейнер найден: $CONTAINER_NAME"
    
    # Check if running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo_success "Контейнер запущен"
    else
        echo_warning "Контейнер существует, но не запущен"
    fi
else
    echo_warning "Контейнер $CONTAINER_NAME не найден"
    echo_info "Проверяю альтернативные имена..."
    docker ps -a --format '{{.Names}}' | grep -i wpg || echo_warning "Контейнеры WPG не найдены"
fi
echo ""

# Check DNS settings in container
echo_info "3. Проверка DNS настроек в контейнере..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo_info "Текущие DNS серверы в контейнере:"
    docker exec $CONTAINER_NAME cat /etc/resolv.conf 2>/dev/null || echo_warning "Не удалось прочитать /etc/resolv.conf"
    
    # Check if our DNS servers are configured
    if docker exec $CONTAINER_NAME cat /etc/resolv.conf 2>/dev/null | grep -q "8.8.8.8\|1.1.1.1"; then
        echo_success "Настроены публичные DNS серверы"
    else
        echo_error "Публичные DNS серверы не настроены!"
        echo_info "Добавьте в docker-compose.yml или docker run --dns 8.8.8.8"
    fi
else
    echo_warning "Контейнер не запущен, пропускаю проверку DNS"
fi
echo ""

# Test DNS resolution from container
echo_info "4. Тест разрешения доменных имен..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo_info "Проверка api.telegram.org..."
    
    if docker exec $CONTAINER_NAME sh -c 'command -v nslookup' > /dev/null 2>&1; then
        if docker exec $CONTAINER_NAME nslookup api.telegram.org 2>/dev/null; then
            echo_success "DNS работает: api.telegram.org разрешается"
        else
            echo_error "DNS не работает: не удалось разрешить api.telegram.org"
        fi
    else
        echo_warning "nslookup не установлен в контейнере"
        echo_info "Пробую альтернативный метод с ping..."
        if docker exec $CONTAINER_NAME ping -c 1 api.telegram.org > /dev/null 2>&1; then
            echo_success "DNS работает (проверено через ping)"
        else
            echo_error "DNS не работает или пинг заблокирован"
        fi
    fi
else
    echo_warning "Контейнер не запущен, пропускаю тест DNS"
fi
echo ""

# Check container logs for DNS errors
echo_info "5. Проверка логов на наличие DNS ошибок..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo_info "Последние ошибки DNS в логах:"
    if docker logs $CONTAINER_NAME 2>&1 | grep -i "dns\|name or service not known\|Cannot connect to host" | tail -5; then
        echo_error "Найдены ошибки DNS в логах!"
    else
        echo_success "DNS ошибок не найдено в последних логах"
    fi
else
    echo_warning "Контейнер не найден, пропускаю проверку логов"
fi
echo ""

# Check docker-compose DNS configuration
echo_info "6. Проверка docker-compose конфигурации..."
if [ -f "deploy/docker-compose.yml" ]; then
    echo_info "Проверяю deploy/docker-compose.yml..."
    if grep -q "dns:" deploy/docker-compose.yml; then
        echo_success "DNS серверы настроены в docker-compose.yml"
        echo_info "Настроенные DNS:"
        grep -A 3 "dns:" deploy/docker-compose.yml | grep "-"
    else
        echo_error "DNS серверы НЕ настроены в docker-compose.yml!"
        echo_info "Добавьте в секцию wpg-bot:"
        echo "    dns:"
        echo "      - 8.8.8.8"
        echo "      - 8.8.4.4"
        echo "      - 1.1.1.1"
    fi
else
    echo_warning "deploy/docker-compose.yml не найден"
fi
echo ""

# Check host DNS resolution
echo_info "7. Проверка DNS на хост-системе..."
if command -v nslookup > /dev/null 2>&1; then
    if nslookup api.telegram.org > /dev/null 2>&1; then
        echo_success "Хост может разрешить api.telegram.org"
    else
        echo_error "Хост НЕ может разрешить api.telegram.org"
        echo_warning "Проблема может быть на уровне хост-системы"
    fi
else
    echo_warning "nslookup не установлен на хосте"
fi
echo ""

# Recommendations
echo_info "=== Рекомендации ==="
echo ""

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    if docker exec $CONTAINER_NAME cat /etc/resolv.conf 2>/dev/null | grep -q "8.8.8.8\|1.1.1.1"; then
        echo_success "DNS настроен правильно"
        echo_info "Если всё ещё есть проблемы:"
        echo "  1. Проверьте фаервол/VPN"
        echo "  2. Попробуйте использовать другие DNS (77.88.8.8 для России)"
        echo "  3. Проверьте логи: docker logs $CONTAINER_NAME"
    else
        echo_error "ДЕЙСТВИЕ ТРЕБУЕТСЯ: Настройте DNS"
        echo ""
        echo "Вариант 1: Используйте docker-compose (рекомендуется)"
        echo "  cd deploy"
        echo "  docker-compose down"
        echo "  docker-compose up -d"
        echo ""
        echo "Вариант 2: Пересоздайте контейнер с DNS"
        echo "  docker stop $CONTAINER_NAME"
        echo "  docker rm $CONTAINER_NAME"
        echo "  docker run -d --name $CONTAINER_NAME \\"
        echo "    --dns 8.8.8.8 --dns 8.8.4.4 --dns 1.1.1.1 \\"
        echo "    --restart unless-stopped \\"
        echo "    ... другие параметры ..."
        echo ""
        echo "Вариант 3: Настройте Docker глобально"
        echo "  Отредактируйте /etc/docker/daemon.json:"
        echo '  {"dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"]}'
        echo "  sudo systemctl restart docker"
    fi
else
    echo_warning "Контейнер не запущен"
    echo_info "Запустите контейнер с правильными DNS настройками:"
    echo "  cd deploy"
    echo "  docker-compose up -d"
fi

echo ""
echo_info "=== Конец диагностики ==="

