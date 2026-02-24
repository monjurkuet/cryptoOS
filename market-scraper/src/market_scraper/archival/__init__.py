"""Data archival module for long-term storage.

This module provides functionality to archive MongoDB data before TTL deletion.
Archives are compressed with zstd and can be pushed to Git LFS for version control.

Components:
- Compressor: zstd-based compression with configurable levels
- Archiver: Queries MongoDB and creates compressed archives
- GitLFSPusher: Pushes archives to a Git LFS repository
"""

from market_scraper.archival.compressor import Compressor
from market_scraper.archival.archiver import Archiver

__all__ = ["Compressor", "Archiver"]
