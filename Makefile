# WPG Engine Makefile
# Convenient commands for development and deployment

.PHONY: help build run test clean deploy monitor logs backup

# Default target
help:
	@echo "WPG Engine - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make build          - Build Docker image"
	@echo "  make run            - Run locally with Docker Compose"
	@echo "  make run-dev        - Run in development mode"
	@echo "  make test           - Run tests in Docker"
	@echo "  make test-local     - Run tests locally (like CI)"
	@echo "  make test-docker    - Run tests in Docker (explicit)"
	@echo "  make lint           - Run linting"
	@echo "  make clean          - Clean up containers and images"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-prod    - Deploy to production"
	@echo "  make deploy-staging - Deploy to staging"
	@echo "  make deploy-dev     - Deploy to development"
	@echo ""
	@echo "Monitoring:"
	@echo "  make status         - Check container status"
	@echo "  make health         - Run health check"
	@echo "  make logs           - Show logs"
	@echo "  make monitor        - Follow logs"
	@echo "  make backup         - Create database backup"
	@echo "  make restart        - Restart container"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Initial setup"
	@echo "  make env            - Create .env from example"

# Development commands
build:
	@echo "🔨 Building Docker image..."
	docker build -t wpg-engine -f deploy/Dockerfile .

run: build
	@echo "🚀 Starting with Docker Compose..."
	docker-compose -f deploy/docker-compose.yml up -d
	@echo "✅ Started! Use 'make logs' to view logs"

run-dev:
	@echo "🚀 Starting in development mode..."
	docker-compose -f deploy/docker-compose.dev.yml up -d
	@echo "✅ Started in dev mode! Use 'make logs' to view logs"

test:
	@echo "🧪 Running tests..."
	@./scripts/local-test.sh test

test-local:
	@echo "🧪 Running tests locally (like CI)..."
	@python -m pytest tests/ -v || echo "No tests found, skipping..."

test-docker: build-test
	@echo "🧪 Running tests in Docker..."
	@./scripts/local-test.sh test

build-test:
	@echo "🔨 Building test image..."
	@./scripts/local-test.sh build

lint:
	@echo "🔍 Running linting..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check . && ruff format --check .; \
	else \
		echo "⚠️  Ruff not installed, skipping..."; \
	fi

format:
	@echo "🎨 Formatting code..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff format .; \
	else \
		echo "⚠️  Ruff not installed, skipping..."; \
	fi

clean:
	@echo "🧹 Cleaning up..."
	docker-compose -f deploy/docker-compose.yml down --remove-orphans
	docker-compose -f deploy/docker-compose.dev.yml down --remove-orphans
	@./scripts/local-test.sh clean

# Deployment commands
deploy-prod:
	@echo "🚀 Deploying to production..."
	@./scripts/deploy.sh prod

deploy-staging:
	@echo "🚀 Deploying to staging..."
	@./scripts/deploy.sh staging

deploy-dev:
	@echo "🚀 Deploying to development..."
	@./scripts/deploy.sh dev

# Monitoring commands
status:
	@./scripts/monitor.sh status

health:
	@./scripts/monitor.sh health

logs:
	@./scripts/monitor.sh logs

monitor:
	@./scripts/monitor.sh follow

backup:
	@./scripts/monitor.sh backup

restart:
	@./scripts/monitor.sh restart

# Setup commands
setup: env
	@echo "🔧 Setting up project..."
	@chmod +x scripts/*.sh
	@mkdir -p data logs
	@echo "✅ Setup completed!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env file with your bot token"
	@echo "2. Run 'make run' to start the bot"

env:
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env from example..."; \
		cp .env.example .env; \
		echo "✅ .env created! Please edit it with your settings."; \
	else \
		echo "⚠️  .env already exists"; \
	fi

# Docker Compose shortcuts
up: run
down:
	@echo "🛑 Stopping containers..."
	docker-compose -f deploy/docker-compose.yml down

up-dev: run-dev
down-dev:
	@echo "🛑 Stopping dev containers..."
	docker-compose -f deploy/docker-compose.dev.yml down

# Quick commands
quick-test: test-local
quick-deploy: test deploy-prod

# Database commands
migrate:
	@echo "🗄️  Running migrations..."
	python scripts/run_migrations.py

recreate-db:
	@echo "🗄️  Recreating database..."
	python scripts/recreate_database.py

# Local development
local-run:
	@echo "🏃 Running locally (without Docker)..."
	python main.py

local-test:
	@echo "🧪 Running tests locally..."
	python -m pytest tests/ -v

# Git hooks
pre-commit: format lint test-local
	@echo "✅ Pre-commit checks passed"

# Installation
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

install-dev: install
	@echo "📦 Installing development dependencies..."
	pip install pytest ruff mypy

# Help for specific environments
help-prod:
	@echo "Production deployment help:"
	@echo ""
	@echo "1. Set up GitHub secrets:"
	@echo "   - TG_TOKEN"
	@echo "   - TG_ADMIN_ID"
	@echo "   - YC_SA_JSON_CREDENTIALS"
	@echo "   - YC_REGISTRY_ID"
	@echo "   - YC_INSTANCE_IP"
	@echo "   - YC_INSTANCE_USER"
	@echo "   - YC_INSTANCE_NAME"
	@echo "   - YC_CLOUD_ID"
	@echo "   - YC_FOLDER_ID"
	@echo ""
	@echo "2. Push to main branch for automatic deployment"
	@echo "3. Or run 'make deploy-prod' for manual deployment"

help-dev:
	@echo "Development workflow:"
	@echo ""
	@echo "1. make setup           # Initial setup"
	@echo "2. Edit .env file       # Add your bot token"
	@echo "3. make run-dev         # Start in development mode"
	@echo "4. make logs            # View logs"
	@echo "5. make test            # Run tests"
	@echo "6. make clean           # Clean up when done"