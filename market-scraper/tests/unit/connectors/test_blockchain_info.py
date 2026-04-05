# tests/unit/connectors/test_blockchain_info.py

"""Unit tests for Blockchain.info connector behavior."""

from market_scraper.connectors.blockchain_info.parsers import parse_current_metrics


def test_parse_current_metrics_includes_market_fields() -> None:
    """Current network metrics should expose price and market cap."""
    event = parse_current_metrics(
        {
            "hash_rate": 800_000_000_000,
            "difficulty": 123.45,
            "block_count": 1_234_567,
            "total_btc": 1_990_000_000_000_000,
            "price_24h": 67_295.0,
            "market_cap": 1_340_000_000_000.0,
            "tx_count_24h": 300_000,
        }
    )

    assert event.payload["price_usd"] == 67_295.0
    assert event.payload["market_cap_usd"] == 1_340_000_000_000.0
    assert event.payload["total_btc"] == 19_900_000.0
