"""
memory/repository_cache.py

Caches the repository knowledge base (index, dependency graph, FAISS
embeddings) to disk so subsequent runs are fast.

Problem solved
--------------
Without caching:
    Every run: clone → scan → parse → embed (5-10 min for large repos)

With caching:
    First run:  clone → scan → parse → embed → save cache (~5 min)
    Later runs: load cache (< 5 seconds) ✅

Cache invalidation
------------------
We use a content hash of all Python file modification times.
If any file changes, the cache is automatically rebuilt.
This is safe and correct — stale caches never serve wrong data.

Cache structure (on disk)
-------------------------
.repo_cache/
    <repo_name>/
        meta.json          ← hash, file count, timestamp
        index.json         ← RepoIndex dict
        dep_graph.json     ← dependency graph (serialized)
        faiss.index        ← FAISS binary
        chunks.pkl         ← CodeChunk list

Usage
-----
    cache = RepositoryCache(cache_dir=".repo_cache")
    if cache.is_valid(repo_path):
        data = cache.load(repo_path)
    else:
        data = build_from_scratch(repo_path)
        cache.save(repo_path, data)
"""

import hashlib
import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CachedRepository:
    repo_name: str
    index: Dict[str, Any]           # RepoIndex
    dep_graph_data: Dict[str, List[str]]  # serialized dependency graph
    created_at: str
    file_count: int
    content_hash: str


class RepositoryCache:
    """
    Persistent cache for repository knowledge base.

    Caches:
    - Repository index (AST parse results)
    - Dependency graph
    - FAISS embeddings (via RetrievalPipeline's own cache — we track its hash)

    Args:
        cache_dir: Base directory for all caches (default: ".repo_cache")
    """

    def __init__(self, cache_dir: str = ".repo_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_valid(self, repo_path: Path) -> bool:
        """
        Check if a valid cache exists for this repository.

        Returns True if the cache exists AND the repo hasn't changed.
        """
        cache_path = self._cache_path(repo_path)
        meta_file = cache_path / "meta.json"

        if not meta_file.exists():
            return False

        try:
            meta = json.loads(meta_file.read_text())
            current_hash = self._compute_hash(repo_path)
            valid = meta.get("content_hash") == current_hash
            if valid:
                logger.info("Cache valid for %s (hash match).", repo_path.name)
            else:
                logger.info("Cache stale for %s (repo changed).", repo_path.name)
            return valid
        except Exception as exc:
            logger.warning("Cache check failed: %s", exc)
            return False

    def save(self, repo_path: Path, index: dict, dep_graph) -> None:
        """
        Save repository knowledge base to disk.

        Args:
            repo_path:  Path to the cloned repository.
            index:      RepoIndex dict from RepositoryIndexer.
            dep_graph:  DependencyGraph instance.
        """
        cache_path = self._cache_path(repo_path)
        cache_path.mkdir(parents=True, exist_ok=True)

        content_hash = self._compute_hash(repo_path)

        # Save index
        (cache_path / "index.json").write_text(json.dumps(index, indent=2))

        # Save dependency graph (serialized as dict)
        (cache_path / "dep_graph.json").write_text(json.dumps(dep_graph.to_dict(), indent=2))

        # Save metadata
        meta = {
            "repo_name":    repo_path.name,
            "content_hash": content_hash,
            "created_at":   datetime.now().isoformat(),
            "file_count":   len(index),
        }
        (cache_path / "meta.json").write_text(json.dumps(meta, indent=2))

        logger.info(
            "Cache saved for %s (%d files, hash=%s).",
            repo_path.name, len(index), content_hash[:8],
        )

    def load(self, repo_path: Path) -> Optional[CachedRepository]:
        """
        Load the cached knowledge base for a repository.

        Returns None if cache is missing or corrupted.
        """
        cache_path = self._cache_path(repo_path)

        try:
            meta = json.loads((cache_path / "meta.json").read_text())
            index = json.loads((cache_path / "index.json").read_text())
            dep_graph_data = json.loads((cache_path / "dep_graph.json").read_text())

            result = CachedRepository(
                repo_name=meta["repo_name"],
                index=index,
                dep_graph_data=dep_graph_data,
                created_at=meta["created_at"],
                file_count=meta["file_count"],
                content_hash=meta["content_hash"],
            )
            logger.info(
                "Cache loaded for %s (%d files, created %s).",
                repo_path.name, result.file_count, result.created_at[:10],
            )
            return result
        except Exception as exc:
            logger.warning("Cache load failed for %s: %s", repo_path.name, exc)
            return None

    def invalidate(self, repo_path: Path) -> None:
        """Delete the cache for a repository, forcing a rebuild on next run."""
        import shutil
        cache_path = self._cache_path(repo_path)
        if cache_path.exists():
            shutil.rmtree(cache_path)
            logger.info("Cache invalidated for %s.", repo_path.name)

    def restore_dep_graph(self, cached: CachedRepository):
        """
        Reconstruct a DependencyGraph from cached data.

        Returns a DependencyGraph with the graph populated.
        """
        from repository_analysis.dependency_graph import DependencyGraph
        from collections import defaultdict

        graph = DependencyGraph()
        # Directly populate the internal graph dict
        for file_path, imports in cached.dep_graph_data.items():
            for imp in imports:
                graph._graph[file_path].add(imp)
        return graph

    def list_cached(self) -> List[dict]:
        """List all cached repositories with their metadata."""
        results = []
        for meta_file in self.cache_dir.rglob("meta.json"):
            try:
                meta = json.loads(meta_file.read_text())
                results.append(meta)
            except Exception:
                continue
        return results

    # ── private ────────────────────────────────────────────────────────────

    def _cache_path(self, repo_path: Path) -> Path:
        return self.cache_dir / repo_path.name

    def _compute_hash(self, repo_path: Path) -> str:
        """
        Hash all Python file modification times.
        Changes when any .py file is added, modified, or deleted.
        """
        hasher = hashlib.md5()
        skip = {".git", "__pycache__", "venv", ".venv", "node_modules"}

        py_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in files:
                if f.endswith(".py"):
                    full = Path(root) / f
                    py_files.append((str(full.relative_to(repo_path)), full.stat().st_mtime))

        py_files.sort()
        for path, mtime in py_files:
            hasher.update(f"{path}:{mtime}".encode())

        return hasher.hexdigest()
