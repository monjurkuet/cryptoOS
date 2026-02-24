"""Git LFS integration for pushing archives to remote storage.

Provides functionality to push compressed archives to a Git LFS
repository for version-controlled long-term storage.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GitLFSPusher:
    """Pushes archives to a Git LFS repository.

    This class manages a local clone of a Git repository with LFS
    configured for storing large archive files.

    Example:
        pusher = GitLFSPusher(
            repo_url="https://github.com/user/archive-repo.git",
            local_path=Path("/data/archive-repo"),
        )
        await pusher.setup()
        await pusher.push_archive(
            archive_path=Path("/data/archives/positions.zst"),
            commit_message="Archive trader positions for 2024-01",
        )
    """

    def __init__(
        self,
        repo_url: str,
        local_path: Path,
        branch: str = "main",
        lfs_patterns: list[str] | None = None,
    ) -> None:
        """Initialize the Git LFS pusher.

        Args:
            repo_url: Git repository URL (SSH or HTTPS)
            local_path: Local path for repository clone
            branch: Git branch to use
            lfs_patterns: File patterns for LFS tracking (default: *.zst)
        """
        self._repo_url = repo_url
        self._local_path = local_path
        self._branch = branch
        self._lfs_patterns = lfs_patterns or ["*.zst"]
        self._initialized = False

    async def setup(self) -> None:
        """Initialize the repository clone.

        Clones the repository if it doesn't exist, or fetches latest
        if it does. Configures Git LFS for archive files.
        """
        if self._local_path.exists():
            await self._fetch_and_reset()
        else:
            await self._clone_repo()

        await self._configure_lfs()
        self._initialized = True
        logger.info("git_lfs_setup_complete", path=str(self._local_path))

    async def _clone_repo(self) -> None:
        """Clone the repository."""
        self._local_path.parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--branch", self._branch,
            self._repo_url,
            str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {self._repo_url}")

        logger.info("git_clone_complete", path=str(self._local_path))

    async def _fetch_and_reset(self) -> None:
        """Fetch latest and reset local branch."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            "fetch",
            "origin",
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        proc = await asyncio.create_subprocess_exec(
            "git",
            "reset",
            "--hard",
            f"origin/{self._branch}",
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        logger.info("git_fetch_reset_complete", branch=self._branch)

    async def _configure_lfs(self) -> None:
        """Configure Git LFS for archive patterns."""
        for pattern in self._lfs_patterns:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "lfs",
                "track",
                pattern,
                cwd=str(self._local_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        # Ensure .gitattributes is tracked
        gitattributes = self._local_path / ".gitattributes"
        if gitattributes.exists():
            proc = await asyncio.create_subprocess_exec(
                "git",
                "add",
                ".gitattributes",
                cwd=str(self._local_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        logger.info("git_lfs_configured", patterns=self._lfs_patterns)

    async def push_archive(
        self,
        archive_path: Path,
        dest_dir: str = "",
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """Push an archive file to the repository.

        Args:
            archive_path: Path to the archive file
            dest_dir: Subdirectory in repo to store archive
            commit_message: Custom commit message

        Returns:
            Dict with push result information
        """
        if not self._initialized:
            await self.setup()

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Determine destination path in repo
        if dest_dir:
            dest_path = self._local_path / dest_dir / archive_path.name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            dest_path = self._local_path / archive_path.name

        # Copy archive to repo
        shutil.copy2(archive_path, dest_path)

        # Stage, commit, and push
        relative_path = str(dest_path.relative_to(self._local_path))

        # git add
        proc = await asyncio.create_subprocess_exec(
            "git",
            "add",
            relative_path,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git add failed: {stderr.decode()}")

        # git commit
        message = commit_message or f"Archive: {archive_path.name}"
        proc = await asyncio.create_subprocess_exec(
            "git",
            "commit",
            "-m",
            message,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            # May fail if nothing to commit
            logger.warning("git_commit_no_changes", stderr=stderr.decode())

        # git push
        proc = await asyncio.create_subprocess_exec(
            "git",
            "push",
            "origin",
            self._branch,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git push failed: {stderr.decode()}")

        logger.info(
            "archive_pushed",
            archive=archive_path.name,
            dest=str(dest_path),
            message=message,
        )

        return {
            "archive": archive_path.name,
            "dest_path": str(dest_path),
            "commit_message": message,
            "pushed": True,
        }

    async def push_multiple(
        self,
        archive_paths: list[Path],
        dest_dir: str = "",
        commit_message: str | None = None,
    ) -> list[dict[str, Any]]:
        """Push multiple archives in a single commit.

        Args:
            archive_paths: List of archive file paths
            dest_dir: Subdirectory in repo to store archives
            commit_message: Custom commit message

        Returns:
            List of push results
        """
        if not self._initialized:
            await self.setup()

        results = []
        for archive_path in archive_paths:
            if dest_dir:
                dest_path = self._local_path / dest_dir / archive_path.name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                dest_path = self._local_path / archive_path.name

            shutil.copy2(archive_path, dest_path)
            results.append({
                "archive": archive_path.name,
                "dest_path": str(dest_path),
            })

        # Single commit for all archives
        relative_paths = [r["dest_path"] for r in results]

        proc = await asyncio.create_subprocess_exec(
            "git",
            "add",
            *relative_paths,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        message = commit_message or f"Archive batch: {len(archive_paths)} files"
        proc = await asyncio.create_subprocess_exec(
            "git",
            "commit",
            "-m",
            message,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        proc = await asyncio.create_subprocess_exec(
            "git",
            "push",
            "origin",
            self._branch,
            cwd=str(self._local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        logger.info("batch_archive_pushed", count=len(archive_paths))
        return results
