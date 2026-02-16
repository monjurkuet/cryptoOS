"""
Archive Job.

This module handles archiving old data to parquet files.
"""

import gzip
import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.utils.archive import get_archive_path, save_to_parquet


async def archive_all_collections(
    db: AsyncIOMotorDatabase,
) -> Dict[str, int]:
    """
    Archive all collections based on retention policy.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with archived count per collection
    """
    if not settings.archive_enabled:
        logger.info("Archiving disabled")
        return {}

    results = {}

    # Get retention config
    retention = settings.retention_config

    for collection_name, days in retention.items():
        try:
            # Special handling for orderbook - compress old data
            if collection_name == CollectionName.BTC_ORDERBOOK:
                # First compress data >7 days old
                compressed = await archive_orderbook_with_compression(db, compress_after_days=7)
                # Then do normal archiving for data exceeding retention
                archived = await archive_collection(db, collection_name, days)
                results[collection_name] = archived + compressed
            else:
                count = await archive_collection(db, collection_name, days)
                results[collection_name] = count
        except Exception as e:
            logger.error(f"Error archiving {collection_name}: {e}")
            results[collection_name] = 0

    total = sum(results.values())
    logger.info(f"Archived {total} documents from {len(results)} collections")

    return results


async def archive_collection(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    days_old: int,
) -> int:
    """
    Archive documents older than threshold from a collection.

    Args:
        db: MongoDB database
        collection_name: Name of the collection
        days_old: Archive documents older than this many days

    Returns:
        Count of archived documents
    """
    collection = db[collection_name]
    threshold = datetime.utcnow() - timedelta(days=days_old)

    # Find documents to archive
    cursor = collection.find(
        {"createdAt": {"$lt": threshold}},
        limit=10000,  # Batch size limit
    )

    documents = await cursor.to_list(length=10000)

    if not documents:
        return 0

    # Save to parquet
    archive_path = get_archive_path(
        base_path=settings.archive_base_path,
        collection=collection_name,
    )

    saved = save_to_parquet(documents, archive_path, append=True)

    # Delete archived documents
    if saved > 0:
        ids = [doc["_id"] for doc in documents]
        await collection.delete_many({"_id": {"$in": ids}})

    logger.info(f"Archived {saved} documents from {collection_name}")

    return saved


async def archive_orderbook_with_compression(
    db: AsyncIOMotorDatabase,
    compress_after_days: int = 7,
) -> int:
    """
    Archive orderbook data with gzip compression for old data.

    Only compresses data older than compress_after_days.
    Keeps recent data uncompressed for fast queries.

    Args:
        db: MongoDB database
        compress_after_days: Compress data older than this many days

    Returns:
        Count of compressed/archived documents
    """
    collection = db[CollectionName.BTC_ORDERBOOK]

    # Calculate threshold - data older than this gets compressed
    threshold = datetime.utcnow() - timedelta(days=compress_after_days)

    # Find old orderbook data to compress
    cursor = collection.find(
        {"t": {"$lt": threshold}},
        limit=5000,  # Process in batches
    ).sort("t", 1)  # Oldest first

    documents = await cursor.to_list(length=5000)

    if not documents:
        return 0

    # Group documents by date for efficient storage
    from collections import defaultdict

    docs_by_date = defaultdict(list)

    for doc in documents:
        # Group by date (YYYY-MM-DD)
        doc_date = doc.get("t", datetime.utcnow()).strftime("%Y-%m-%d")
        # Remove _id for compression (will be regenerated on read if needed)
        doc_copy = {k: v for k, v in doc.items() if k != "_id"}
        docs_by_date[doc_date].append(doc_copy)

    compressed_count = 0

    for date_str, docs in docs_by_date.items():
        try:
            # Compress the documents
            json_data = json.dumps(docs, default=str)
            compressed = gzip.compress(json_data.encode("utf-8"), compresslevel=9)

            # Save to compressed archive file
            archive_dir = f"{settings.archive_base_path}/btc_orderbook_compressed"
            import os

            os.makedirs(archive_dir, exist_ok=True)

            archive_file = f"{archive_dir}/{date_str}.json.gz"

            # Append or create new file
            mode = "ab" if os.path.exists(archive_file) else "wb"
            with open(archive_file, mode) as f:
                # Write length prefix + compressed data for easy reading
                f.write(len(compressed).to_bytes(4, byteorder="big"))
                f.write(compressed)

            compressed_count += len(docs)

        except Exception as e:
            logger.error(f"Error compressing orderbook for {date_str}: {e}")
            continue

    # Delete compressed documents from database
    if compressed_count > 0:
        ids = [doc["_id"] for doc in documents]
        await collection.delete_many({"_id": {"$in": ids}})
        logger.info(
            f"Compressed and archived {compressed_count} orderbook documents (> {compress_after_days} days old)"
        )

    return compressed_count


def decompress_orderbook_file(file_path: str) -> List[Dict]:
    """
    Decompress a gzipped orderbook archive file.

    Args:
        file_path: Path to .json.gz file

    Returns:
        List of decompressed documents
    """
    documents = []

    try:
        with open(file_path, "rb") as f:
            while True:
                # Read length prefix (4 bytes)
                length_bytes = f.read(4)
                if not length_bytes or len(length_bytes) < 4:
                    break

                length = int.from_bytes(length_bytes, byteorder="big")

                # Read compressed data
                compressed = f.read(length)
                if not compressed or len(compressed) < length:
                    break

                # Decompress
                json_data = gzip.decompress(compressed).decode("utf-8")
                docs = json.loads(json_data)
                documents.extend(docs)

    except Exception as e:
        logger.error(f"Error decompressing {file_path}: {e}")

    return documents


async def get_archive_status(
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Get archiving status and statistics.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with archive status
    """
    from src.utils.archive import get_archive_metadata

    # Get archive metadata
    archive_meta = get_archive_metadata(settings.archive_base_path)

    # Get collection counts
    collections = [
        CollectionName.BTC_CANDLES,
        CollectionName.BTC_ORDERBOOK,
        CollectionName.BTC_TRADES,
        CollectionName.TRADER_POSITIONS,
        CollectionName.TRADER_ORDERS,
        CollectionName.BTC_SIGNALS,
    ]

    db_counts = {}
    for coll in collections:
        try:
            count = await db[coll].count_documents({})
            db_counts[coll] = count
        except Exception:
            db_counts[coll] = 0

    return {
        "archiveEnabled": settings.archive_enabled,
        "archiveBasePath": settings.archive_base_path,
        "archiveStats": archive_meta,
        "dbCounts": db_counts,
        "retentionPolicy": settings.retention_config,
    }


async def cleanup_archives(
    max_days: int = 365,
) -> int:
    """
    Clean up old archive files.

    Args:
        max_days: Maximum age of archives in days

    Returns:
        Count of removed files
    """
    from src.utils.archive import cleanup_old_archives

    removed = cleanup_old_archives(settings.archive_base_path, max_days)
    logger.info(f"Cleaned up {removed} old archive files")

    return removed
