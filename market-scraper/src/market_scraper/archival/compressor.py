"""Zstandard-based compression for data archival.

Provides fast, efficient compression for JSON data with configurable
compression levels for balancing speed vs compression ratio.
"""

import json
import pathlib
from typing import Any

import structlog
import zstandard as zstd

logger = structlog.get_logger(__name__)


class Compressor:
    """Zstandard-based compressor for data archival.

    Uses zstd level 3 by default for good balance of speed (300 MB/s)
    and compression ratio (3-4x for JSON data).

    Example:
        compressor = Compressor()
        compressed = compressor.compress({"data": [1, 2, 3]})
        data = compressor.decompress(compressed)
    """

    def __init__(self, level: int = 3) -> None:
        """Initialize the compressor.

        Args:
            level: Compression level (1-22). Default 3 for balance.
                   1 = fastest, lowest ratio
                   22 = slowest, highest ratio
                   3 = good balance (~300 MB/s, ~3.5x ratio for JSON)
        """
        self._level = level
        self._compressor = zstd.ZstdCompressor(level=level)
        self._decompressor = zstd.ZstdDecompressor()

    def compress(self, data: dict[str, Any] | list[Any]) -> bytes:
        """Compress JSON-serializable data.

        Args:
            data: Dictionary or list to compress

        Returns:
            Compressed bytes
        """
        json_bytes = json.dumps(data, default=self._json_serializer).encode("utf-8")
        compressed = self._compressor.compress(json_bytes)

        ratio = len(json_bytes) / len(compressed) if len(compressed) > 0 else 0
        logger.debug(
            "compression_complete",
            original_size=len(json_bytes),
            compressed_size=len(compressed),
            ratio=round(ratio, 2),
        )

        return compressed

    def decompress(self, compressed: bytes) -> dict[str, Any] | list[Any]:
        """Decompress data back to Python object.

        Args:
            compressed: Compressed bytes from compress()

        Returns:
            Original dictionary or list
        """
        json_bytes = self._decompressor.decompress(compressed)
        return json.loads(json_bytes.decode("utf-8"))

    def compress_to_file(
        self,
        data: dict[str, Any] | list[Any],
        path: pathlib.Path,
    ) -> int:
        """Compress data and write to file.

        Args:
            data: Dictionary or list to compress
            path: Output file path (should end with .zst)

        Returns:
            Compressed file size in bytes
        """
        compressed = self.compress(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)

        logger.info(
            "compression_file_written",
            path=str(path),
            size=len(compressed),
        )

        return len(compressed)

    def decompress_from_file(
        self,
        path: pathlib.Path,
    ) -> dict[str, Any] | list[Any]:
        """Read and decompress data from file.

        Args:
            path: Path to compressed file

        Returns:
            Decompressed dictionary or list
        """
        compressed = path.read_bytes()
        return self.decompress(compressed)

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types.

        Handles datetime and other MongoDB types.
        """
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
