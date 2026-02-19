"""Storage module for the Market Scraper Framework.

This module provides data persistence capabilities through the DataRepository
abstract base class and its implementations.
"""

from market_scraper.storage.base import DataRepository, QueryFilter
from market_scraper.storage.memory_repository import MemoryRepository
from market_scraper.storage.mongo_repository import MongoRepository

__all__ = [
    "DataRepository",
    "MemoryRepository",
    "MongoRepository",
    "QueryFilter",
]
