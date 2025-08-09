#!/bin/bash

# Server Setup Script Template for WPG Engine
# Copy this to setup-server.sh and configure your SERVER_ID

set -e

# Configuration - CHANGE THIS TO YOUR SERVER ID
SERVER_ID="your_server_id_here"
PROJECT_NAME="wpg-engine"

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

# Check if SERVER_ID is configured
if [[ "$SERVER_ID" == "your_server_id_here" ]]; then
    echo_error "Пожалуйста, настройте SERVER_ID в скрипте!"
    echo_info "Откройте scripts/setup-server.sh и замените 'your_server_id_here' на ваш ID сервера"
    echo_info "Ваш SERVER_ID: epducvokks3etcr82gsu"
    exit 1
fi

# Setup server
setup_server() {
    echo_info "Настройка сервера $SERVER_ID..."
    
    # Connect to server and run setup commands
    yc compute ssh --id $SERVER_ID << 'EOF'
        set -e
        
        echo "🔧 Updating system..."
        sudo apt update && sudo apt upgrade -y
        
        echo "🐳 Installing Docker..."
        if ! command -v docker &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
            echo "✅ Docker installed"
        else
            echo "✅ Docker already installed"
        fi
        
        echo "📁 Creating project directories..."
        sudo mkdir -p /opt/wpg-engine/{data,logs,backups}
        sudo chown -R $USER:$USER /opt/wpg-engine
        
        echo "🔐 Setting up Yandex Container Registry..."
        if ! yc --version &> /dev/null; then
            curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
            echo 'export PATH="$HOME/yandex-cloud/bin:$PATH"' >> ~/.bashrc
            source ~/.bashrc
        fi
        
        # Configure Docker for Yandex Registry
        yc container registry configure-docker || echo "Registry configuration skipped"
        
        echo "🎉 Server setup completed!"
        echo "📊 System info:"
        echo "Docker version: $(docker --version)"
        echo "Available space: $(df -h / | tail -1 | awk '{print $4}')"
        echo "Memory: $(free -h | grep Mem | awk '{print $7}')"
EOF
    
    echo_success "Сервер настроен успешно!"
}

# Check status
check_status() {
    echo_info "Проверка статуса на сервере..."
    
    yc compute ssh --id $SERVER_ID << 'EOF'
        echo "🐳 Docker containers:"
        docker ps
        
        echo ""
        echo "📊 Container logs (last 10 lines):"
        docker logs --tail 10 wpg-engine-bot 2>/dev/null || echo "Container not running"
        
        echo ""
        echo "💾 Disk usage:"
        df -h /opt/wpg-engine
        
        echo ""
        echo "🧠 Memory usage:"
        free -h
EOF
}

# Show help
help() {
    echo "WPG Engine Server Setup Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup   - Setup server (install Docker, create directories)"
    echo "  status  - Check server and application status"
    echo "  help    - Show this help"
    echo ""
    echo "Server ID: $SERVER_ID"
    echo ""
    echo "ВАЖНО: Перед использованием замените SERVER_ID на ваш реальный ID сервера!"
}

# Main function
main() {
    case "${1:-help}" in
        "setup")
            setup_server
            ;;
        "status")
            check_status
            ;;
        "help"|*)
            help
            ;;
    esac
}

main "$@"