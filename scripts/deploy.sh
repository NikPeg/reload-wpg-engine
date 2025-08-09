#!/bin/bash

# WPG Engine Deployment Script for Yandex Cloud
# Usage: ./scripts/deploy.sh [environment]
# Environment: dev, staging, prod (default: prod)

set -e

# Configuration
ENVIRONMENT=${1:-prod}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment-specific configuration
case $ENVIRONMENT in
    "dev")
        IMAGE_TAG="dev"
        CONTAINER_NAME="wpg-engine-bot-dev"
        ;;
    "staging")
        IMAGE_TAG="staging"
        CONTAINER_NAME="wpg-engine-bot-staging"
        ;;
    "prod")
        IMAGE_TAG="latest"
        CONTAINER_NAME="wpg-engine-bot"
        ;;
    *)
        echo "❌ Unknown environment: $ENVIRONMENT"
        echo "Usage: $0 [dev|staging|prod]"
        exit 1
        ;;
esac

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check required environment variables
check_env_vars() {
    local required_vars=("YC_REGISTRY_ID" "YC_INSTANCE_IP" "YC_INSTANCE_USER")
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            echo_error "Environment variable $var is not set"
            exit 1
        fi
    done
}

# Build Docker image
build_image() {
    echo_info "Building Docker image for $ENVIRONMENT..."
    
    local image_name="cr.yandex/$YC_REGISTRY_ID/wpg-engine-bot:$IMAGE_TAG"
    
    cd "$PROJECT_DIR"
    docker build -t "$image_name" .
    
    echo_success "Image built: $image_name"
    return 0
}

# Push image to registry
push_image() {
    echo_info "Pushing image to Yandex Container Registry..."
    
    local image_name="cr.yandex/$YC_REGISTRY_ID/wpg-engine-bot:$IMAGE_TAG"
    
    # Login to registry
    docker push "$image_name"
    
    echo_success "Image pushed to registry"
}

# Deploy to server
deploy_to_server() {
    echo_info "Deploying to server ($ENVIRONMENT)..."
    
    local image_name="cr.yandex/$YC_REGISTRY_ID/wpg-engine-bot:$IMAGE_TAG"
    
    # Create deployment script for remote execution
    cat > /tmp/remote_deploy.sh << EOF
#!/bin/bash
set -e

# Variables
IMAGE_URL="$image_name"
CONTAINER_NAME="$CONTAINER_NAME"
DATA_DIR="/opt/wpg-engine/$ENVIRONMENT/data"
LOGS_DIR="/opt/wpg-engine/$ENVIRONMENT/logs"

echo "🔄 Stopping existing container..."
docker stop \$CONTAINER_NAME 2>/dev/null || true
docker rm \$CONTAINER_NAME 2>/dev/null || true

echo "📥 Pulling new image..."
docker pull \$IMAGE_URL

echo "📁 Creating directories..."
sudo mkdir -p \$DATA_DIR \$LOGS_DIR
sudo chown -R \$(whoami):\$(whoami) /opt/wpg-engine/$ENVIRONMENT

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

echo "✅ Deployment completed successfully!"
EOF

    # Copy and execute deployment script
    scp -o StrictHostKeyChecking=no /tmp/remote_deploy.sh "$YC_INSTANCE_USER@$YC_INSTANCE_IP:/tmp/"
    
    ssh -o StrictHostKeyChecking=no "$YC_INSTANCE_USER@$YC_INSTANCE_IP" \
        "chmod +x /tmp/remote_deploy.sh && /tmp/remote_deploy.sh && rm /tmp/remote_deploy.sh"
    
    # Clean up local temp file
    rm /tmp/remote_deploy.sh
    
    echo_success "Deployment completed"
}

# Verify deployment
verify_deployment() {
    echo_info "Verifying deployment..."
    
    sleep 10
    
    ssh -o StrictHostKeyChecking=no "$YC_INSTANCE_USER@$YC_INSTANCE_IP" \
        "docker ps | grep $CONTAINER_NAME && echo '📊 Container status: Running'"
    
    echo_info "Recent logs:"
    ssh -o StrictHostKeyChecking=no "$YC_INSTANCE_USER@$YC_INSTANCE_IP" \
        "docker logs --tail 20 $CONTAINER_NAME"
    
    echo_success "Verification completed"
}

# Main deployment process
main() {
    echo_info "Starting deployment process for environment: $ENVIRONMENT"
    
    # Load environment file if exists
    if [[ -f "$PROJECT_DIR/.env.$ENVIRONMENT" ]]; then
        echo_info "Loading environment variables from .env.$ENVIRONMENT"
        set -a
        source "$PROJECT_DIR/.env.$ENVIRONMENT"
        set +a
    elif [[ -f "$PROJECT_DIR/.env" ]]; then
        echo_warning "Using default .env file"
        set -a
        source "$PROJECT_DIR/.env"
        set +a
    fi
    
    check_env_vars
    build_image
    push_image
    deploy_to_server
    verify_deployment
    
    echo_success "🎉 Deployment completed successfully!"
    echo_info "Your bot is now running in $ENVIRONMENT environment"
}

# Run main function
main "$@"