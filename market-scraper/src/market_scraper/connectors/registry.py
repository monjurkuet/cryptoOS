# src/market_scraper/connectors/registry.py

"""Connector registry for discovery and instantiation."""

from market_scraper.connectors.base import DataConnector


class ConnectorRegistry:
    """Registry for connector discovery and instantiation."""

    _connectors: dict[str, type[DataConnector]] = {}

    @classmethod
    def register(cls, name: str, connector_class: type[DataConnector]) -> None:
        """Register a connector class.

        Args:
            name: Unique name for the connector
            connector_class: The connector class to register

        Raises:
            ValueError: If name is already registered with a different class
        """
        if name in cls._connectors and cls._connectors[name] is not connector_class:
            raise ValueError(f"Connector '{name}' is already registered")
        cls._connectors[name] = connector_class

    @classmethod
    def get(cls, name: str) -> type[DataConnector]:
        """Get connector class by name.

        Args:
            name: Name of the connector

        Returns:
            The connector class

        Raises:
            KeyError: If connector is not registered
        """
        if name not in cls._connectors:
            raise KeyError(f"Unknown connector: {name}")
        return cls._connectors[name]

    @classmethod
    def list_connectors(cls) -> list[str]:
        """List all registered connector names.

        Returns:
            List of registered connector names
        """
        return list(cls._connectors.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered connectors (mainly for testing)."""
        cls._connectors.clear()
