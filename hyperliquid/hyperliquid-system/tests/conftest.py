"""
Test Configuration.

This module provides fixtures for testing.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Create a test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    database = client["hyperliquid_test"]

    yield database

    # Cleanup: drop test database
    await client.drop_database("hyperliquid_test")
    client.close()


@pytest.fixture
def sample_candle() -> dict:
    """Sample candle data for testing."""
    from datetime import datetime

    return {
        "t": datetime.utcnow(),
        "interval": "1h",
        "o": 75000.0,
        "h": 75100.0,
        "l": 74900.0,
        "c": 75050.0,
        "v": 150.5,
    }


@pytest.fixture
def sample_trader() -> dict:
    """Sample trader data for testing."""
    return {
        "ethAddress": "0x162cc7c861ebd0c06b3d72319201150482518185",
        "displayName": "TestTrader",
        "accountValue": 1000000.0,
        "score": 75.0,
        "windowPerformances": [
            ["day", {"pnl": "10000", "roi": "0.01", "vlm": "1000000"}],
            ["week", {"pnl": "50000", "roi": "0.05", "vlm": "5000000"}],
            ["month", {"pnl": "200000", "roi": "0.20", "vlm": "20000000"}],
            ["allTime", {"pnl": "1000000", "roi": "1.0", "vlm": "100000000"}],
        ],
    }


@pytest.fixture
def sample_position() -> dict:
    """Sample position data for testing."""
    return {
        "marginSummary": {
            "accountValue": "1000000",
            "totalNtlPos": "500000",
            "totalMarginUsed": "50000",
        },
        "assetPositions": [
            {
                "type": "oneWay",
                "position": {
                    "coin": "BTC",
                    "szi": "1.5",
                    "entryPx": "75000",
                    "positionValue": "112500",
                    "unrealizedPnl": "5000",
                    "leverage": {"type": "cross", "value": 10},
                    "marginUsed": "11250",
                },
            }
        ],
    }
