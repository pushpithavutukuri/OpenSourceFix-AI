"""
repo_loader.py
Clones or updates a GitHub repository to local disk.
"""

import os
import logging
from pathlib import Path

import git

logger = logging.getLogger(__name__)


class RepoLoader:
    """Clone or pull a GitHub repository to a local directory."""

    def __init__(self, base_dir: str = "cloned_repos"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, repo_url: str) -> Path:
        """
        Clone repo if not present, pull if it already exists.

        Args:
            repo_url: Full GitHub URL, e.g. https://github.com/tiangolo/fastapi

        Returns:
            Path to the local repository root.
        """
        repo_name = repo_url.rstrip("/").split("/")[-1]
        local_path = self.base_dir / repo_name

        if local_path.exists():
            logger.info("Repository already exists at %s — pulling latest.", local_path)
            repo = git.Repo(local_path)
            repo.remotes.origin.pull()
        else:
            logger.info("Cloning %s into %s", repo_url, local_path)
            git.Repo.clone_from(repo_url, local_path)

        logger.info("Repository ready at %s", local_path)
        return local_path
