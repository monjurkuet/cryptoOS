.PHONY: help install dev test lint typecheck format clean docs run

help:
	@echo "cryptoOS - Cryptocurrency Data Aggregation Platform"
	@echo ""
	@echo "Available commands:"
	@echo "  install       - Install dependencies"
	@echo "  dev          - Install development dependencies"
	@echo "  test         - Run test suite"
	@echo "  lint         - Run code linter (ruff)"
	@echo "  format       - Format code (black + isort)"
	@echo "  typecheck    - Run type checker (mypy)"
	@echo "  clean        - Clean build artifacts"
	@echo "  docs         - Build documentation"
	@echo "  run          - Run the main application"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=cryptoOS

lint:
	ruff check cryptoOS/ tests/

format:
	black cryptoOS/ tests/
	isort cryptoOS/ tests/

typecheck:
	mypy cryptoOS/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/

docs:
	mkdocs build

run:
	python -m cryptoOS

ci: lint typecheck test
