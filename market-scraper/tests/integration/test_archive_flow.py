"""Integration tests for data archival flow."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_scraper.archival.compressor import Compressor
from market_scraper.archival.archiver import Archiver


class TestCompressorIntegration:
    """Integration tests for Compressor."""

    def test_compress_decompress_roundtrip(self) -> None:
        """Test that compress -> decompress returns original data."""
        compressor = Compressor(level=3)

        original_data = {
            "metadata": {
                "collection": "test_collection",
                "archived_at": datetime.now(timezone.utc).isoformat(),
            },
            "documents": [
                {"id": 1, "name": "test", "value": 123.45},
                {"id": 2, "name": "test2", "value": 678.90},
            ],
        }

        compressed = compressor.compress(original_data)
        decompressed = compressor.decompress(compressed)

        assert decompressed == original_data

    def test_compress_to_file_roundtrip(self) -> None:
        """Test compress to file -> decompress from file."""
        compressor = Compressor(level=3)

        original_data = {
            "documents": [{"test": "data"}],
        }

        with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as f:
            temp_path = Path(f.name)

        try:
            compressor.compress_to_file(original_data, temp_path)
            assert temp_path.exists()
            assert temp_path.stat().st_size > 0

            decompressed = compressor.decompress_from_file(temp_path)
            assert decompressed == original_data
        finally:
            temp_path.unlink(missing_ok=True)

    def test_compression_ratio(self) -> None:
        """Test that compression achieves expected ratio for JSON data."""
        compressor = Compressor(level=3)

        # Create repetitive JSON data (typical for database exports)
        original_data = {
            "documents": [
                {
                    "address": f"0x{'a' * 40}",
                    "positions": [
                        {"coin": "BTC", "szi": 1.5, "entryPx": 97000.0}
                        for _ in range(10)
                    ],
                    "timestamp": "2024-01-15T12:30:00+00:00",
                }
                for _ in range(100)
            ]
        }

        json_size = len(json.dumps(original_data).encode("utf-8"))
        compressed = compressor.compress(original_data)
        compressed_size = len(compressed)

        ratio = json_size / compressed_size if compressed_size > 0 else 0

        # Expect at least 2x compression for repetitive JSON
        assert ratio >= 2.0, f"Expected ratio >= 2.0, got {ratio}"

    def test_compress_with_datetime(self) -> None:
        """Test that datetime objects are serialized correctly."""
        compressor = Compressor()

        data = {
            "timestamp": datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc),
        }

        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)

        # datetime should be converted to ISO string
        assert "timestamp" in decompressed
        assert isinstance(decompressed["timestamp"], str)


class TestArchiverIntegration:
    """Integration tests for Archiver."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Create a mock database."""
        db = MagicMock()

        # Create a mock collection with async iterator
        docs = [
            {
                "_id": "doc1",
                "address": "0xtest1",
                "positions": [{"coin": "BTC", "szi": 1.0}],
                "created_at": datetime.now(timezone.utc),
            },
            {
                "_id": "doc2",
                "address": "0xtest2",
                "positions": [{"coin": "BTC", "szi": -0.5}],
                "created_at": datetime.now(timezone.utc),
            },
        ]

        # Create async cursor mock
        cursor = AsyncIteratorMock(docs)
        collection = MagicMock()
        collection.find = MagicMock(return_value=cursor)
        db.__getitem__ = lambda self, name: collection

        return db

    @pytest.mark.asyncio
    async def test_archive_collection_creates_file(self, mock_db: MagicMock) -> None:
        """Test that archive_collection creates a compressed file."""
        archiver = Archiver(db=mock_db)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_archive.zst"

            result = await archiver.archive_collection(
                collection_name="trader_positions",
                output_path=output_path,
            )

            assert output_path.exists()
            assert result["documents"] == 2
            assert result["size_bytes"] > 0

            # Verify we can decompress and read the data
            compressor = Compressor()
            data = compressor.decompress_from_file(output_path)

            assert "metadata" in data
            assert "documents" in data
            assert len(data["documents"]) == 2

    @pytest.mark.asyncio
    async def test_archive_with_exclude_fields(self, mock_db: MagicMock) -> None:
        """Test that excluded fields are removed from archive."""
        archiver = Archiver(db=mock_db)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_archive.zst"

            await archiver.archive_collection(
                collection_name="trader_positions",
                output_path=output_path,
                exclude_fields=["_id"],
            )

            compressor = Compressor()
            data = compressor.decompress_from_file(output_path)

            # _id should be excluded
            for doc in data["documents"]:
                assert "_id" not in doc


class AsyncIteratorMock:
    """Mock async iterator for MongoDB cursor."""

    def __init__(self, items: list) -> None:
        self._items = items
        self._index = 0

    def __aiter__(self) -> "AsyncIteratorMock":
        return self

    async def __anext__(self) -> dict:
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


class TestArchiveRestoreFlow:
    """Test full archive and restore flow."""

    def test_full_roundtrip(self) -> None:
        """Test complete archive -> restore flow."""
        compressor = Compressor(level=3)

        # Original data from MongoDB
        original_data = {
            "metadata": {
                "collection": "trader_positions",
                "archived_at": "2024-01-15T12:00:00+00:00",
                "document_count": 3,
            },
            "documents": [
                {
                    "address": "0xabc123",
                    "positions": [{"coin": "BTC", "szi": 1.5}],
                    "account_value": 15000000,
                },
                {
                    "address": "0xdef456",
                    "positions": [{"coin": "BTC", "szi": -2.0}],
                    "account_value": 25000000,
                },
                {
                    "address": "0xghi789",
                    "positions": [],
                    "account_value": 5000000,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "positions_202401.zst"

            # Archive
            compressor.compress_to_file(original_data, archive_path)
            assert archive_path.exists()

            # Restore
            restored_data = compressor.decompress_from_file(archive_path)

            # Verify data integrity
            assert restored_data == original_data
            assert len(restored_data["documents"]) == 3
            assert restored_data["documents"][0]["address"] == "0xabc123"

            # Verify compression achieved
            json_size = len(json.dumps(original_data).encode("utf-8"))
            compressed_size = archive_path.stat().st_size
            ratio = json_size / compressed_size

            print(f"Compression ratio: {ratio:.2f}x")
            print(f"Original: {json_size} bytes, Compressed: {compressed_size} bytes")
