# Development Guide

This guide covers setting up a development environment, running tests, code style guidelines, and contributing to the project.

## Development Setup

### 1. Clone and Install

```bash
git clone <repository-url>
cd market-scraper
uv sync
```

### 2. Install Pre-commit Hooks

The project uses pre-commit for code quality:

```bash
uv run pre-commit install
```

### 3. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your settings
```

## Running Tests

### Test Organization

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/      # Integration tests (requires services)
├── e2e/             # End-to-end tests (full system)
└── fixtures/        # Test fixtures and data
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/market_scraper --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m e2e

# Run specific test file
pytest tests/unit/core/test_events.py

# Run with verbose output
pytest -v

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

### Test Markers

The project uses pytest markers for test categorization:

```python
import pytest

@pytest.mark.unit
def test_something():
    """Unit tests - fast, no external dependencies"""
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_with_database():
    """Integration tests - requires services"""
    pass

@pytest.mark.e2e
def test_full_flow():
    """End-to-end tests - full system test"""
    pass

@pytest.mark.slow
def test_heavy_operation():
    """Slow tests - may take longer to run"""
    pass
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/core/test_events.py

import pytest
from datetime import datetime
from market_scraper.core.events import StandardEvent, EventType

@pytest.mark.unit
class TestStandardEvent:
    def test_create_event(self):
        """Test event creation."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "price": 50000},
        )
        
        assert event.event_type == EventType.TRADE
        assert event.source == "test"
        assert event.payload["symbol"] == "BTC-USD"
        assert event.event_id is not None

    def test_mark_processed(self):
        """Test processing time tracking."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={},
        )
        
        event.mark_processed()
        
        assert event.processed_at is not None
        assert event.processing_time_ms is not None
        assert event.processing_time_ms >= 0
```

#### Integration Test Example

```python
# tests/integration/test_event_bus.py

import pytest
from market_scraper.event_bus import MemoryEventBus
from market_scraper.core.events import StandardEvent, EventType

@pytest.mark.integration
class TestMemoryEventBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        """Test pub/sub functionality."""
        bus = MemoryEventBus()
        received = []
        
        async def handler(event):
            received.append(event)
        
        await bus.subscribe(EventType.TRADE, handler)
        
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={},
        )
        
        await bus.publish(event)
        
        assert len(received) == 1
        assert received[0].event_id == event.event_id
```

## Code Style

### Python Style

The project follows these style guidelines:

- **PEP 8**: Python style guide
- **Google Style**: Docstring conventions
- **Type Hints**: Required for all function signatures

### Linting

Run linting checks:

```bash
# Run ruff linter
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/
```

### Type Checking

Run mypy type checks:

```bash
uv run mypy src/
```

### Formatting

Format code with black:

```bash
uv run black src/
```

### Pre-commit Checks

Run all pre-commit hooks:

```bash
uv run pre-commit run --all-files
```

### Code Standards

```python
"""Module docstring - describe what this module does."""

import asyncio
from datetime import datetime
from typing import Any

from market_scraper.core.events import StandardEvent


class MyClass:
    """Class docstring - describe the class purpose.
    
    Attributes:
        attribute: Description of attribute.
    """

    def __init__(self, value: int) -> None:
        """Initialize the class.
        
        Args:
            value: The initial value.
        """
        self._value = value

    async def process(self, data: dict[str, Any]) -> StandardEvent | None:
        """Process data and return an event.
        
        Args:
            data: Input data dictionary.
            
        Returns:
            A StandardEvent if successful, None otherwise.
            
        Raises:
            ValueError: If data is invalid.
        """
        if not data:
            return None
        
        return StandardEvent.create(
            event_type="custom",
            source="my_class",
            payload=data,
        )
```

## Contributing Guidelines

### 1. Fork and Clone

```bash
git clone <your-fork-url>
cd market-scraper
```

### 2. Create a Branch

```bash
git checkout -b feature/my-new-feature
# or
git checkout -b fix/issue-description
```

### 3. Make Changes

1. Write code following the style guidelines
2. Add tests for new functionality
3. Update documentation if needed

### 4. Run Tests

```bash
# Run all checks
pytest
uv run ruff check src/
uv run mypy src/
```

### 5. Commit Changes

```bash
git add .
git commit -m "Add feature: description of changes"
```

### 6. Push and Create PR

```bash
git push origin feature/my-new-feature
# Then create PR via GitHub
```

## Common Development Tasks

### Adding a New Connector

1. Create `src/market_scraper/connectors/my_connector/`
2. Implement `DataConnector` interface
3. Register in `ConnectorRegistry`
4. Add tests

### Adding a New Processor

1. Create `src/market_scraper/processors/my_processor.py`
2. Extend `Processor` base class
3. Subscribe to event types
4. Add tests

### Adding a New API Endpoint

1. Add route in appropriate file under `src/market_scraper/api/routes/`
2. Add request/response models in `src/market_scraper/api/models.py`
3. Add tests
4. Update OpenAPI spec (automatic with FastAPI)

## Debugging

### Enable Debug Logging

```bash
# Set log level via environment
LOGGING__LEVEL=DEBUG uv run python -m market_scraper
```

### Using PDB

```python
import pdb

def some_function():
    result = do_something()
    pdb.set_trace()  # Debug here
    return result
```

### VS Code Configuration

```json
{
    "python.linting.ruffEnabled": true,
    "python.linting.mypyEnabled": true,
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false
}
```
