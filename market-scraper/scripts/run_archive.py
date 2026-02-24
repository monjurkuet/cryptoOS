#!/usr/bin/env python
"""CLI tool for running data archival.

Usage:
    uv run python scripts/run_archive.py --help
    uv run python scripts/run_archive.py --collections trader_positions signals
    uv run python scripts/run_archive.py --all --push
"""

import argparse
import asyncio
from datetime import datetime, UTC
from pathlib import Path
import os

import structlog
from motor.motor_asyncio import AsyncIOMotorClient

from market_scraper.archival import Archiver, Compressor
from market_scraper.archival.git_lfs_pusher import GitLFSPusher
from market_scraper.config.market_config import load_market_config

logger = structlog.get_logger(__name__)


async def run_archive(
    collections: list[str],
    output_dir: Path,
    mongo_url: str,
    database: str,
    retention_days: int = 7,
    push_to_git: bool = False,
    git_repo_url: str | None = None,
    git_local_path: Path | None = None,
    compression_level: int = 3,
) -> list[dict]:
    """Run the archival process.

    Args:
        collections: List of collection names to archive
        output_dir: Directory for archive files
        mongo_url: MongoDB connection string
        database: Database name
        retention_days: Archive data older than this
        push_to_git: Whether to push to Git LFS
        git_repo_url: Git repository URL
        git_local_path: Local path for Git repo
        compression_level: zstd compression level

    Returns:
        List of archive results
    """
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_url)
    db = client[database]

    # Initialize components
    compressor = Compressor(level=compression_level)
    archiver = Archiver(db=db, compressor=compressor)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create archive files
    results = await archiver.archive_all_collections(
        output_dir=output_dir,
        collections=collections,
        retention_days=retention_days,
    )

    # Close MongoDB connection
    client.close()

    # Push to Git LFS if configured
    if push_to_git and git_repo_url:
        pusher = GitLFSPusher(
            repo_url=git_repo_url,
            local_path=git_local_path or Path("/tmp/archive-repo"),
        )
        await pusher.setup()

        archive_paths = [
            Path(r["path"]) for r in results if "path" in r
        ]
        await pusher.push_multiple(
            archive_paths=archive_paths,
            commit_message=f"Archive: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        )

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Archive MongoDB data to compressed files"
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        default=["trader_positions", "signals", "candles"],
        help="Collections to archive",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Archive all configured collections",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/data/archives"),
        help="Output directory for archives",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Archive data older than this many days",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push archives to Git LFS",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=3,
        help="zstd compression level (1-22)",
    )

    args = parser.parse_args()

    # Get configuration from environment
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    database = os.environ.get("MONGO_DATABASE", "market_scraper")
    git_repo_url = os.environ.get("ARCHIVE_REPO_URL")
    git_local_path = os.environ.get("ARCHIVE_REPO_LOCAL_PATH")

    # Determine collections to archive
    if args.all:
        market_config = load_market_config()
        collections = list(market_config.storage.retention.keys())
    else:
        collections = args.collections

    logger.info(
        "archive_cli_start",
        collections=collections,
        output_dir=str(args.output_dir),
        retention_days=args.retention_days,
    )

    results = asyncio.run(
        run_archive(
            collections=collections,
            output_dir=args.output_dir,
            mongo_url=mongo_url,
            database=database,
            retention_days=args.retention_days,
            push_to_git=args.push,
            git_repo_url=git_repo_url,
            git_local_path=Path(git_local_path) if git_local_path else None,
            compression_level=args.compression_level,
        )
    )

    # Print results
    print("\nArchive Results:")
    print("-" * 50)
    for result in results:
        if "error" in result:
            print(f"  {result['collection']}: ERROR - {result['error']}")
        else:
            size_kb = result.get("size_bytes", 0) / 1024
            print(f"  {result['collection']}: {result['documents']} docs, {size_kb:.1f} KB")
    print("-" * 50)


if __name__ == "__main__":
    main()
