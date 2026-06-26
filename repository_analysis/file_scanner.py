"""
file_scanner.py
Scans a local repository and collects metadata about its structure.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    total_files: int = 0
    python_files: int = 0
    folders: int = 0
    python_file_paths: List[Path] = field(default_factory=list)


class FileScanner:
    """Walk a repository and gather file/folder statistics."""

    SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache"}

    def scan(self, repo_path: Path) -> ScanResult:
        """
        Recursively scan the repository.

        Args:
            repo_path: Root path of the cloned repository.

        Returns:
            ScanResult with counts and Python file paths.
        """
        result = ScanResult()

        for root, dirs, files in os.walk(repo_path):
            # Prune directories we never want to enter
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            result.folders += len(dirs)

            for fname in files:
                result.total_files += 1
                if fname.endswith(".py"):
                    result.python_files += 1
                    result.python_file_paths.append(Path(root) / fname)

        logger.info(
            "Scan complete — total_files=%d  python_files=%d  folders=%d",
            result.total_files,
            result.python_files,
            result.folders,
        )
        return result
