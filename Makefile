# CalorieMate Makefile
# Development automation for Flask application with raw SQL implementation

.PHONY: help install dev run test clean docker-build docker-up docker-down docker-logs docker-clean validate setup-env

# Default target
help:
	@echo "CalorieMate Development Commands"
	@echo "================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       Install dependencies and setup virtual environment"
	@echo "  make setup-env     Setup environment files and configuration"
	@echo ""
	@echo "Development:"
	@echo "  make dev          Start development server with auto-reload"
	@echo "  make run          Run the Flask application"
	@echo "  make test         Run application tests"
	@echo "  make validate     Validate configuration and dependencies"
	@echo ""
	@echo "Docker Operations:"
	@echo "  make docker-build Build Docker containers"
	@echo "  make docker-up    Start Docker services (detached mode)"
	@echo "  make docker-down  Stop Docker services"
	@echo "  make docker-logs  View Docker application logs"
	@echo "  make docker-clean Clean Docker containers and volumes"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        Clean temporary files and cache"
	@echo "  make lint         Run code linting (if configured)"
	@echo ""
	@echo "Quick Start:"
	@echo "  make install && make dev"

# Variables
PYTHON = python
VENV_DIR = .venv
REQUIREMENTS = requirements.txt
DOCKER_COMPOSE = docker-compose -f docker/docker-compose.yml

# Setup and Installation
install:
	@echo "Setting up CalorieMate development environment..."
	@if not exist "$(VENV_DIR)" ( \
		echo "Creating virtual environment..." && \
		$(PYTHON) -m venv $(VENV_DIR) \
	)
	@echo "Activating virtual environment and installing dependencies..."
	@$(VENV_DIR)\Scripts\python.exe -m pip install --upgrade pip
	@$(VENV_DIR)\Scripts\activate && pip install -r $(REQUIREMENTS)
	@echo "Installation complete!"

setup-env:
	@echo "Setting up environment configuration..."
	@if not exist ".env" ( \
		echo "Creating .env file..." && \
		echo FLASK_APP=app.py > .env && \
		echo FLASK_ENV=development >> .env && \
		echo FLASK_DEBUG=True >> .env && \
		echo DB_HOST=localhost >> .env && \
		echo DB_PORT=3306 >> .env && \
		echo DB_USER=root >> .env && \
		echo DB_PASSWORD= >> .env && \
		echo DB_NAME=caloriemate >> .env && \
		echo SECRET_KEY=dev-secret-key-change-in-production >> .env \
	)
	@echo "Environment setup complete!"

# Development
dev: setup-env
	@echo "Starting CalorieMate development server..."
	@$(VENV_DIR)\Scripts\python.exe app.py

run: setup-env
	@echo "Running CalorieMate application..."
	@$(VENV_DIR)\Scripts\activate && flask run --host=0.0.0.0 --port=5000

# Testing and Validation
test:
	@echo "Running CalorieMate tests..."
	@$(VENV_DIR)\Scripts\python.exe -m pytest -v || echo "No pytest found, running basic tests..."
	@$(VENV_DIR)\Scripts\python.exe test_setup.py
	@if exist "test_docker_config.py" ( \
		$(VENV_DIR)\Scripts\python.exe test_docker_config.py \
	)

validate:
	@echo "Validating CalorieMate configuration..."
	@$(VENV_DIR)\Scripts\python.exe -c "import app; print('App imports successfully')"
	@if exist "test_docker_config.py" ( \
		$(VENV_DIR)\Scripts\python.exe test_docker_config.py \
	)
	@echo "Validation complete!"

# Docker Operations
docker-build:
	@echo "Building CalorieMate Docker containers..."
	@$(DOCKER_COMPOSE) build

docker-up:
	@echo "Starting CalorieMate Docker services..."
	@$(DOCKER_COMPOSE) up -d
	@echo "Services started!"
	@echo "CalorieMate: http://localhost:5000"
	@echo "phpMyAdmin: http://localhost:8080"

docker-down:
	@echo "Stopping CalorieMate Docker services..."
	@$(DOCKER_COMPOSE) down

docker-logs:
	@echo "CalorieMate application logs:"
	@$(DOCKER_COMPOSE) logs -f app

docker-clean:
	@echo "Cleaning Docker containers and volumes..."
	@$(DOCKER_COMPOSE) down -v
	@docker system prune -f

# Maintenance
clean:
	@echo "Cleaning temporary files..."
	@if exist "__pycache__" rmdir /s /q __pycache__
	@if exist "*.pyc" del /q *.pyc
	@if exist ".pytest_cache" rmdir /s /q .pytest_cache
	@if exist "*.egg-info" rmdir /s /q *.egg-info
	@echo "Cleanup complete!"

lint:
	@echo "Running code linting..."
	@$(VENV_DIR)\Scripts\python.exe -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || echo "flake8 not installed"
	@$(VENV_DIR)\Scripts\python.exe -m black --check . || echo "black not installed"

# Database Operations
db-init:
	@echo "Initializing database..."
	@$(VENV_DIR)\Scripts\python.exe -c "from app import initialize_database; initialize_database()"

db-reset:
	@echo "WARNING: Resetting database (this will delete all data)..."
	@pause
	@$(VENV_DIR)\Scripts\python.exe -c "from app import reset_database; reset_database()"

# Quick development workflow
quick-start: install dev

# Production preparation
prod-check:
	@echo "Production readiness check..."
	@echo "WARNING: Remember to:"
	@echo "  - Update SECRET_KEY in production"
	@echo "  - Set proper database credentials"
	@echo "  - Configure SSL/TLS"
	@echo "  - Review security settings"
	@echo "  - Set FLASK_ENV=production"

# Git operations
git-status:
	@git status --porcelain
	@echo ""
	@echo "Current branch: $(shell git branch --show-current)"

commit:
	@git add .
	@git status
	@echo "Enter commit message:"
	@set /p msg="" && git commit -m "%msg%"

# All-in-one commands
full-setup: install setup-env validate
	@echo "CalorieMate is ready for development!"
	@echo "Run 'make dev' to start the development server"

docker-fresh: docker-clean docker-build docker-up
	@echo "Fresh Docker environment is ready!"

# Windows-specific helper
activate:
	@echo "To activate the virtual environment, run:"
	@echo "$(VENV_DIR)\Scripts\activate"