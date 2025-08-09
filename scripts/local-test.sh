#!/bin/bash

# Local Testing Script for WPG Engine
# Usage: ./scripts/local-test.sh [command]
# Commands: build, run, test, logs, stop, clean

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER_NAME="wpg-engine-test"

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

# Build Docker image
build() {
    echo_info "Building Docker image for local testing..."
    cd "$PROJECT_DIR"
    docker build -t wpg-engine-local .
    echo_success "Image built successfully"
}

# Run container
run() {
    echo_info "Starting container for local testing..."
    
    # Stop existing container if running
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    
    # Create local directories
    mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"
    
    # Check if .env exists
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        echo_warning ".env file not found, copying from .env.example"
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo_warning "Please edit .env file with your bot token before running"
        return 1
    fi
    
    # Run container
    docker run -d \
        --name $CONTAINER_NAME \
        --env-file "$PROJECT_DIR/.env" \
        -v "$PROJECT_DIR/data:/app/data" \
        -v "$PROJECT_DIR/logs:/app/logs" \
        wpg-engine-local
    
    echo_success "Container started: $CONTAINER_NAME"
    echo_info "Use './scripts/local-test.sh logs' to view logs"
}

# Run tests
test() {
    echo_info "Running tests..."
    cd "$PROJECT_DIR"
    
    # Run tests in container
    docker run --rm \
        --env-file "$PROJECT_DIR/.env" \
        -v "$PROJECT_DIR:/app" \
        wpg-engine-local \
        python -m pytest tests/ -v || echo_warning "No tests found or tests failed"
    
    echo_success "Tests completed"
}

# Show logs
logs() {
    echo_info "Showing container logs..."
    docker logs -f $CONTAINER_NAME
}

# Stop container
stop() {
    echo_info "Stopping container..."
    docker stop $CONTAINER_NAME 2>/dev/null || echo_warning "Container not running"
    docker rm $CONTAINER_NAME 2>/dev/null || echo_warning "Container not found"
    echo_success "Container stopped"
}

# Clean up
clean() {
    echo_info "Cleaning up..."
    stop
    docker rmi wpg-engine-local 2>/dev/null || echo_warning "Image not found"
    echo_success "Cleanup completed"
}

# Show status
status() {
    echo_info "Container status:"
    docker ps -a | grep $CONTAINER_NAME || echo_warning "Container not found"
    
    if docker ps | grep -q $CONTAINER_NAME; then
        echo_success "Container is running"
        echo_info "Recent logs:"
        docker logs --tail 10 $CONTAINER_NAME
    else
        echo_warning "Container is not running"
    fi
}

# Interactive shell
shell() {
    echo_info "Opening shell in container..."
    docker exec -it $CONTAINER_NAME /bin/bash || echo_error "Container not running"
}

# Show help
help() {
    echo "WPG Engine Local Testing Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build   - Build Docker image"
    echo "  run     - Run container"
    echo "  test    - Run tests"
    echo "  logs    - Show container logs"
    echo "  stop    - Stop container"
    echo "  clean   - Stop container and remove image"
    echo "  status  - Show container status"
    echo "  shell   - Open shell in container"
    echo "  help    - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 build && $0 run    # Build and run"
    echo "  $0 logs               # View logs"
    echo "  $0 stop               # Stop container"
}

# Main function
main() {
    case "${1:-help}" in
        "build")
            build
            ;;
        "run")
            run
            ;;
        "test")
            test
            ;;
        "logs")
            logs
            ;;
        "stop")
            stop
            ;;
        "clean")
            clean
            ;;
        "status")
            status
            ;;
        "shell")
            shell
            ;;
        "help"|*)
            help
            ;;
    esac
}

main "$@"