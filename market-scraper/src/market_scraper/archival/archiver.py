"""MongoDB to compressed archive converter.

Queries MongoDB collections for data approaching TTL expiry and
creates compressed archives for long-term storage.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from market_scraper.archival.compressor import Compressor

logger = structlog.get_logger(__name__)


class Archiver:
    """Creates compressed archives from MongoDB collections.

    Queries data that is approaching TTL expiry and archives it
    to compressed files for long-term storage.

    Example:
        archiver = Archiver(db, compressor, retention_days=7)
        result = await archiver.archive_collection(
            "trader_positions",
            output_path=Path("/data/archives/positions_2024_01.zst")
        )
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        compressor: Compressor | None = None,
        batch_size: int = 10000,
    ) -> None:
        """Initialize the archiver.

        Args:
            db: MongoDB database instance
            compressor: Compressor instance (default: zstd level 3)
            batch_size: Number of documents to process per batch
        """
        self._db = db
        self._compressor = compressor or Compressor()
        self._batch_size = batch_size

    async def archive_collection(
        self,
        collection_name: str,
        output_path: Path,
        query: dict[str, Any] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Archive a MongoDB collection to a compressed file.

        Args:
            collection_name: Name of the MongoDB collection
            output_path: Output file path (should end with .zst)
            query: Optional MongoDB query filter
            exclude_fields: Fields to exclude from archive

        Returns:
            Dict with archive statistics
        """
        collection = self._db[collection_name]
        query = query or {}

        logger.info(
            "archive_start",
            collection=collection_name,
            output=str(output_path),
        )

        # Stream documents to avoid memory issues
        documents: list[dict[str, Any]] = []
        total_docs = 0
        cursor = collection.find(query)

        projection = None
        if exclude_fields:
            projection = {f: 0 for f in exclude_fields}

        async for doc in cursor:
            # Convert ObjectId and datetime to serializable format
            doc = self._serialize_document(doc)
            if projection:
                doc = {k: v for k, v in doc.items() if k not in exclude_fields}
            documents.append(doc)
            total_docs += 1

            if len(documents) >= self._batch_size:
                logger.debug(
                    "archive_batch",
                    collection=collection_name,
                    count=total_docs,
                )

        if not documents:
            logger.info("archive_empty", collection=collection_name)
            return {
                "collection": collection_name,
                "documents": 0,
                "size_bytes": 0,
                "path": str(output_path),
            }

        # Add metadata
        archive_data = {
            "metadata": {
                "collection": collection_name,
                "archived_at": datetime.now(UTC).isoformat(),
                "document_count": len(documents),
                "query": query,
            },
            "documents": documents,
        }

        # Compress and write
        size = self._compressor.compress_to_file(archive_data, output_path)

        logger.info(
            "archive_complete",
            collection=collection_name,
            documents=len(documents),
            size_bytes=size,
            path=str(output_path),
        )

        return {
            "collection": collection_name,
            "documents": len(documents),
            "size_bytes": size,
            "path": str(output_path),
        }

    async def archive_with_date_range(
        self,
        collection_name: str,
        output_path: Path,
        date_field: str,
        start_date: datetime,
        end_date: datetime,
        exclude_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Archive documents within a date range.

        Args:
            collection_name: Name of the MongoDB collection
            output_path: Output file path
            date_field: Field name containing the date
            start_date: Start of date range
            end_date: End of date range
            exclude_fields: Fields to exclude from archive

        Returns:
            Dict with archive statistics
        """
        query = {
            date_field: {
                "$gte": start_date,
                "$lt": end_date,
            }
        }

        return await self.archive_collection(
            collection_name=collection_name,
            output_path=output_path,
            query=query,
            exclude_fields=exclude_fields,
        )

    async def archive_all_collections(
        self,
        output_dir: Path,
        collections: list[str],
        retention_days: int = 7,
    ) -> list[dict[str, Any]]:
        """Archive multiple collections.

        Archives data older than retention_days from now.

        Args:
            output_dir: Directory for archive files
            retention_days: Archive data older than this
            collections: List of collection names to archive

        Returns:
            List of archive results
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        date_str = cutoff_date.strftime("%Y%m%d")

        results = []
        for collection_name in collections:
            output_path = output_dir / f"{collection_name}_{date_str}.zst"

            try:
                result = await self.archive_collection(
                    collection_name=collection_name,
                    output_path=output_path,
                    query={"created_at": {"$lt": cutoff_date}},
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "archive_error",
                    collection=collection_name,
                    error=str(e),
                    exc_info=True,
                )
                results.append({
                    "collection": collection_name,
                    "error": str(e),
                })

        return results

    def _serialize_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Convert MongoDB document to JSON-serializable format.

        Args:
            doc: MongoDB document with ObjectId, datetime, etc.

        Returns:
            JSON-serializable dictionary
        """
        result = {}
        for key, value in doc.items():
            if hasattr(value, "isoformat"):
                result[key] = value.isoformat()
            elif hasattr(value, "binary"):
                result[key] = value.binary.hex()
            elif isinstance(value, bytes):
                result[key] = value.hex()
            elif isinstance(value, dict):
                result[key] = self._serialize_document(value)
            elif isinstance(value, list):
                result[key] = [
                    self._serialize_document(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result
