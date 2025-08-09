#!/bin/bash

# WPG Engine Monitoring Script
# Usage: ./scripts/monitor.sh [command]
# Commands: status, health, logs, restart, backup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER_NAME="wpg-engine-bot"

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

# Check container status
status() {
    echo_info "Checking container status..."
    
    if docker ps | grep -q $CONTAINER_NAME; then
        echo_success "Container is running"
        
        # Show container info
        echo_info "Container details:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep $CONTAINER_NAME
        
        # Show resource usage
        echo_info "Resource usage:"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" $CONTAINER_NAME
        
    elif docker ps -a | grep -q $CONTAINER_NAME; then
        echo_warning "Container exists but is not running"
        docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep $CONTAINER_NAME
    else
        echo_error "Container not found"
        return 1
    fi
}

# Health check
health() {
    echo_info "Performing health check..."
    
    if ! docker ps | grep -q $CONTAINER_NAME; then
        echo_error "Container is not running"
        return 1
    fi
    
    # Check if container is healthy
    health_status=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER_NAME 2>/dev/null || echo "no-healthcheck")
    
    case $health_status in
        "healthy")
            echo_success "Container is healthy"
            ;;
        "unhealthy")
            echo_error "Container is unhealthy"
            echo_info "Health check logs:"
            docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' $CONTAINER_NAME
            return 1
            ;;
        "starting")
            echo_warning "Container is starting up..."
            ;;
        "no-healthcheck")
            echo_warning "No health check configured"
            ;;
    esac
    
    # Check database connectivity
    echo_info "Testing database connectivity..."
    if docker exec $CONTAINER_NAME python -c "
import asyncio
from wpg_engine.models import get_db
async def test():
    async for db in get_db():
        print('Database connection: OK')
        break
asyncio.run(test())
" 2>/dev/null; then
        echo_success "Database connection: OK"
    else
        echo_error "Database connection: FAILED"
        return 1
    fi
    
    echo_success "Health check completed"
}

# Show logs
logs() {
    local lines=${1:-50}
    echo_info "Showing last $lines log lines..."
    
    if docker ps | grep -q $CONTAINER_NAME; then
        docker logs --tail $lines -t $CONTAINER_NAME
    else
        echo_error "Container is not running"
        return 1
    fi
}

# Follow logs
follow_logs() {
    echo_info "Following logs (Ctrl+C to stop)..."
    
    if docker ps | grep -q $CONTAINER_NAME; then
        docker logs -f -t $CONTAINER_NAME
    else
        echo_error "Container is not running"
        return 1
    fi
}

# Restart container
restart() {
    echo_info "Restarting container..."
    
    if docker ps | grep -q $CONTAINER_NAME; then
        docker restart $CONTAINER_NAME
        echo_success "Container restarted"
        
        # Wait for container to be ready
        echo_info "Waiting for container to be ready..."
        sleep 10
        health
    else
        echo_error "Container is not running"
        return 1
    fi
}

# Backup database
backup() {
    echo_info "Creating database backup..."
    
    local backup_dir="/opt/wpg-engine/backups"
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="wpg_engine_backup_$timestamp.db"
    
    # Create backup directory
    mkdir -p "$backup_dir"
    
    if docker ps | grep -q $CONTAINER_NAME; then
        # Copy database from container
        docker cp "$CONTAINER_NAME:/app/data/wpg_engine.db" "$backup_dir/$backup_file"
        echo_success "Database backed up to: $backup_dir/$backup_file"
        
        # Keep only last 7 backups
        echo_info "Cleaning old backups (keeping last 7)..."
        ls -t "$backup_dir"/wpg_engine_backup_*.db | tail -n +8 | xargs -r rm
        
        echo_info "Available backups:"
        ls -la "$backup_dir"/wpg_engine_backup_*.db 2>/dev/null || echo "No backups found"
    else
        echo_error "Container is not running"
        return 1
    fi
}

# System info
sysinfo() {
    echo_info "System information:"
    
    echo "📊 Docker version:"
    docker --version
    
    echo ""
    echo "💾 Disk usage:"
    df -h | grep -E "(Filesystem|/dev/)"
    
    echo ""
    echo "🧠 Memory usage:"
    free -h
    
    echo ""
    echo "🔥 CPU usage:"
    top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
    
    echo ""
    echo "🐳 Docker containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
    
    echo ""
    echo "📦 Docker images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
}

# Show help
help() {
    echo "WPG Engine Monitoring Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  status      - Show container status and resource usage"
    echo "  health      - Perform health check"
    echo "  logs [n]    - Show last n log lines (default: 50)"
    echo "  follow      - Follow logs in real-time"
    echo "  restart     - Restart container"
    echo "  backup      - Create database backup"
    echo "  sysinfo     - Show system information"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 status           # Check status"
    echo "  $0 logs 100         # Show last 100 log lines"
    echo "  $0 health           # Health check"
    echo "  $0 backup           # Create backup"
}

# Main function
main() {
    case "${1:-help}" in
        "status")
            status
            ;;
        "health")
            health
            ;;
        "logs")
            logs "${2:-50}"
            ;;
        "follow")
            follow_logs
            ;;
        "restart")
            restart
            ;;
        "backup")
            backup
            ;;
        "sysinfo")
            sysinfo
            ;;
        "help"|*)
            help
            ;;
    esac
}

main "$@"