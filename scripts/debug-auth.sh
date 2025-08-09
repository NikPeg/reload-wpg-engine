#!/bin/bash

# Debug script for authentication issues
# This script helps diagnose Docker authentication problems on Yandex Cloud

set -e

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

echo_info "🔍 Диагностика аутентификации Docker на Yandex Cloud"
echo ""

# Check if running on Yandex Cloud
echo_info "1. Проверка метаданных сервиса..."
METADATA_RESPONSE=$(curl -s -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token 2>/dev/null || echo "ERROR")

if [ "$METADATA_RESPONSE" = "ERROR" ]; then
    echo_warning "Метаданные сервиса недоступны (возможно, не на Yandex Cloud VM)"
else
    echo_success "Метаданные сервиса доступны"
    echo "Ответ: $METADATA_RESPONSE"
    
    # Check if response is valid JSON
    if echo "$METADATA_RESPONSE" | jq -e . >/dev/null 2>&1; then
        echo_success "Ответ в формате JSON корректен"
        ACCESS_TOKEN=$(echo "$METADATA_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null)
        if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
            echo_success "Токен доступа найден (длина: ${#ACCESS_TOKEN} символов)"
        else
            echo_error "Токен доступа не найден в ответе"
        fi
    else
        echo_error "Ответ не является корректным JSON"
    fi
fi

echo ""

# Check yc CLI
echo_info "2. Проверка yc CLI..."
if command -v yc >/dev/null 2>&1; then
    echo_success "yc CLI установлен"
    
    # Check yc authentication
    if yc config list >/dev/null 2>&1; then
        echo_success "yc CLI настроен"
        
        # Try to create token
        YC_TOKEN=$(yc iam create-token 2>/dev/null || echo "ERROR")
        if [ "$YC_TOKEN" != "ERROR" ] && [ -n "$YC_TOKEN" ]; then
            echo_success "Токен через yc CLI получен (длина: ${#YC_TOKEN} символов)"
        else
            echo_error "Не удалось получить токен через yc CLI"
        fi
    else
        echo_warning "yc CLI не настроен"
    fi
else
    echo_error "yc CLI не установлен"
fi

echo ""

# Check Docker
echo_info "3. Проверка Docker..."
if command -v docker >/dev/null 2>&1; then
    echo_success "Docker установлен"
    
    # Check Docker daemon
    if docker info >/dev/null 2>&1; then
        echo_success "Docker daemon запущен"
    else
        echo_error "Docker daemon не запущен или недоступен"
    fi
else
    echo_error "Docker не установлен"
fi

echo ""

# Check jq
echo_info "4. Проверка jq..."
if command -v jq >/dev/null 2>&1; then
    echo_success "jq установлен (версия: $(jq --version))"
else
    echo_error "jq не установлен"
    echo_info "Установите jq: sudo apt-get install jq"
fi

echo ""
echo_info "🏁 Диагностика завершена"