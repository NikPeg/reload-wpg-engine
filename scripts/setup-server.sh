#!/bin/bash

# Server Setup Script for WPG Engine
# Usage: ./scripts/setup-server.sh

set -e

# Configuration
SERVER_ID="epducvokks3etcr82gsu"
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

# Deploy application
deploy_app() {
    echo_info "Деплой приложения на сервер..."
    
    # Get registry ID
    REGISTRY_ID=$(yc container registry list --format json | jq -r '.[0].id' 2>/dev/null || echo "")
    
    if [[ -z "$REGISTRY_ID" ]]; then
        echo_warning "Container Registry не найден, создаем..."
        yc container registry create --name wpg-engine-registry
        REGISTRY_ID=$(yc container registry list --format json | jq -r '.[0].id')
    fi
    
    echo_info "Registry ID: $REGISTRY_ID"
    
    # Build and push image
    echo_info "Сборка Docker образа..."
    docker build -t cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest .
    
    echo_info "Загрузка образа в registry..."
    docker push cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest
    
    # Deploy to server
    echo_info "Деплой на сервер..."
    
    # Create deployment script
    cat > /tmp/deploy_script.sh << EOF
#!/bin/bash
set -e

# Variables
IMAGE_URL="cr.yandex/$REGISTRY_ID/wpg-engine-bot:latest"
CONTAINER_NAME="wpg-engine-bot"
DATA_DIR="/opt/wpg-engine/data"
LOGS_DIR="/opt/wpg-engine/logs"

echo "🔄 Stopping existing container..."
docker stop \$CONTAINER_NAME 2>/dev/null || true
docker rm \$CONTAINER_NAME 2>/dev/null || true

echo "📥 Pulling new image..."
docker pull \$IMAGE_URL

echo "🚀 Starting new container..."
docker run -d \\
  --name \$CONTAINER_NAME \\
  --restart unless-stopped \\
  -e TG_TOKEN="\${TG_TOKEN}" \\
  -e TG_ADMIN_ID="\${TG_ADMIN_ID}" \\
  -e AI_OPENROUTER_API_KEY="\${AI_OPENROUTER_API_KEY:-}" \\
  -e DB_URL="sqlite:///./data/wpg_engine.db" \\
  -e LOG_LEVEL="INFO" \\
  -v \$DATA_DIR:/app/data \\
  -v \$LOGS_DIR:/app/logs \\
  \$IMAGE_URL

echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Deployment completed!"
echo "📊 Container status:"
docker ps | grep \$CONTAINER_NAME || echo "Container not found"
EOF
    
    # Copy script to server and execute
    scp /tmp/deploy_script.sh $(yc compute instance get $SERVER_ID --format json | jq -r '.network_interfaces[0].primary_v4_address.one_to_one_nat.address'):/tmp/
    
    yc compute ssh --id $SERVER_ID << 'EOF'
        chmod +x /tmp/deploy_script.sh
        
        # Set environment variables (you need to set these)
        export TG_TOKEN="YOUR_BOT_TOKEN_HERE"
        export TG_ADMIN_ID="YOUR_ADMIN_ID_HERE"
        export AI_OPENROUTER_API_KEY="YOUR_API_KEY_HERE"
        
        # Run deployment
        /tmp/deploy_script.sh
        
        # Clean up
        rm /tmp/deploy_script.sh
EOF
    
    # Clean up local temp file
    rm /tmp/deploy_script.sh
    
    echo_success "Деплой завершен!"
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
    echo "  deploy  - Deploy application to server"
    echo "  status  - Check server and application status"
    echo "  help    - Show this help"
    echo ""
    echo "Server ID: $SERVER_ID"
}

# Main function
main() {
    case "${1:-help}" in
        "setup")
            setup_server
            ;;
        "deploy")
            deploy_app
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