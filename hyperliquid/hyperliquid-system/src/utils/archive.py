"""
Archive Utilities.

This module provides functions for archiving data to parquet files.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger


def get_archive_path(
    base_path: str,
    collection: str,
    date: Optional[datetime] = None,
) -> str:
    """
    Get the archive file path for a collection and date.

    Args:
        base_path: Base archive directory
        collection: Collection name
        date: Date for the archive (default: current month)

    Returns:
        Full path to the parquet file
    """
    date = date or datetime.utcnow()
    month_dir = f"{date.year}-{date.month:02d}"

    archive_dir = Path(base_path) / collection
    archive_dir.mkdir(parents=True, exist_ok=True)

    return str(archive_dir / f"{month_dir}.parquet")


def save_to_parquet(
    data: List[Dict[str, Any]],
    path: str,
    append: bool = True,
) -> int:
    """
    Save data to a parquet file.

    Args:
        data: List of dictionaries to save
        path: Path to the parquet file
        append: Whether to append to existing file

    Returns:
        Number of records saved
    """
    if not data:
        return 0

    df = pd.DataFrame(data)

    # Handle ObjectId conversion
    if "_id" in df.columns:
        df["_id"] = df["_id"].astype(str)

    if append and os.path.exists(path):
        existing_df = pd.read_parquet(path)
        df = pd.concat([existing_df, df], ignore_index=True)
        # Remove duplicates
        df = df.drop_duplicates(subset=["_id"], keep="last")

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    df.to_parquet(path, index=False)
    logger.info(f"Saved {len(df)} records to {path}")

    return len(df)


def load_from_parquet(path: str) -> pd.DataFrame:
    """
    Load data from a parquet file.

    Args:
        path: Path to the parquet file

    Returns:
        DataFrame with the loaded data
    """
    if not os.path.exists(path):
        return pd.DataFrame()

    return pd.read_parquet(path)


def cleanup_old_archives(
    base_path: str,
    max_days: int = 365,
) -> int:
    """
    Remove archive files older than max_days.

    Args:
        base_path: Base archive directory
        max_days: Maximum age in days

    Returns:
        Number of files removed
    """
    removed = 0
    threshold = datetime.utcnow() - timedelta(days=max_days)
    base = Path(base_path)

    for parquet_file in base.glob("**/*.parquet"):
        # Try to extract date from filename
        try:
            filename = parquet_file.stem  # e.g., "2024-01"
            year, month = map(int, filename.split("-"))
            file_date = datetime(year, month, 1)

            if file_date < threshold:
                parquet_file.unlink()
                removed += 1
                logger.info(f"Removed old archive: {parquet_file}")
        except (ValueError, IndexError):
            # If can't parse date, check file modification time
            mtime = datetime.fromtimestamp(parquet_file.stat().st_mtime)
            if mtime < threshold:
                parquet_file.unlink()
                removed += 1
                logger.info(f"Removed old archive (by mtime): {parquet_file}")

    return removed


def get_archive_metadata(base_path: str) -> Dict[str, Any]:
    """
    Get metadata about all archives.

    Args:
        base_path: Base archive directory

    Returns:
        Dictionary with archive metadata
    """
    base = Path(base_path)
    metadata = {
        "collections": {},
        "totalSize": 0,
        "totalFiles": 0,
    }

    for collection_dir in base.iterdir():
        if not collection_dir.is_dir():
            continue

        collection_name = collection_dir.name
        files = list(collection_dir.glob("*.parquet"))

        collection_size = sum(f.stat().st_size for f in files)
        metadata["collections"][collection_name] = {
            "files": len(files),
            "sizeBytes": collection_size,
            "sizeMB": round(collection_size / (1024 * 1024), 2),
        }
        metadata["totalSize"] += collection_size
        metadata["totalFiles"] += len(files)

    metadata["totalSizeMB"] = round(metadata["totalSize"] / (1024 * 1024), 2)
    return metadata


def estimate_archive_size(data: List[Dict[str, Any]]) -> int:
    """
    Estimate the size of data when saved to parquet.

    Args:
        data: List of dictionaries

    Returns:
        Estimated size in bytes
    """
    if not data:
        return 0

    # Parquet typically achieves 3-5x compression
    raw_size = len(str(data))
    estimated_compressed = raw_size / 4  # Assume 4x compression

    return int(estimated_compressed)
