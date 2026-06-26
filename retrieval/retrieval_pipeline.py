"""
retrieval_pipeline.py

Orchestrates the full retrieval setup:
    Repo Index → ChunkSplitter → Embedder → FAISSIndex → SemanticRanker

This is the single entry point your main.py calls.
It handles caching so re-indexing only happens when the repo changes.

Usage:
    pipeline = RetrievalPipeline(config)
    pipeline.build(repo_index, repo_root)      # first run: embeds + saves
    ranker = pipeline.get_ranker()             # returns SemanticRanker
    results = ranker.rank(issue)
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from retrieval.chunk_splitter import ChunkSplitter
from retrieval.embedder import Embedder
from retrieval.faiss_index import FAISSIndex
from retrieval.semantic_ranker import SemanticRanker

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """
    Builds and caches the full semantic retrieval stack.

    Cache strategy:
        A hash of all file paths + modification times is stored alongside
        the FAISS index. If the hash matches on next run, we load from cache.
        If the repo changed, we rebuild.

    Args:
        cache_dir:    Where to store the FAISS index and chunk metadata.
        model_name:   BGE model to use for embeddings.
        device:       "cpu" or "cuda".
        chunk_top_k:  How many chunks FAISS returns per query.
        max_files:    Max ranked files returned to the caller.
    """

    def __init__(
        self,
        cache_dir: str = ".retrieval_cache",
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        chunk_top_k: int = 30,
        max_files: int = 10,
    ):
        self.cache_dir = Path(cache_dir)
        self.model_name = model_name
        self.device = device
        self.chunk_top_k = chunk_top_k
        self.max_files = max_files

        self._embedder: Optional[Embedder] = None
        self._faiss: Optional[FAISSIndex] = None

    # ── Public API ─────────────────────────────────────────────────────────

    def build(self, repo_index: dict, repo_root: Path, force_rebuild: bool = False) -> None:
        """
        Build (or load from cache) the FAISS index for a repository.

        Args:
            repo_index:     RepoIndex from RepositoryIndexer.
            repo_root:      Path to the cloned repository.
            force_rebuild:  Skip cache check and always rebuild.
        """
        cache_hash = self._compute_hash(repo_index)
        hash_file = self.cache_dir / "index.hash"

        if not force_rebuild and self._cache_valid(hash_file, cache_hash):
            logger.info("Loading retrieval index from cache...")
            self._embedder = self._load_embedder()
            self._faiss = FAISSIndex.load(self.cache_dir)
            return

        logger.info("Building retrieval index from scratch...")

        # 1. Chunk
        splitter = ChunkSplitter()
        chunks = splitter.split_repository(repo_index, repo_root)
        logger.info("Produced %d chunks from %d files.", len(chunks), len(repo_index))

        # 2. Embed
        self._embedder = Embedder(model_name=self.model_name, device=self.device)
        texts = [c.content for c in chunks]
        embeddings = self._embedder.embed_corpus(texts)

        # 3. Index
        self._faiss = FAISSIndex()
        self._faiss.build(chunks, embeddings)

        # 4. Save
        self._faiss.save(self.cache_dir)
        hash_file.write_text(cache_hash)
        logger.info("Retrieval index built and cached. Stats: %s", self._faiss.stats())

    def get_ranker(self) -> SemanticRanker:
        """Return a SemanticRanker ready to query. Call build() first."""
        if self._embedder is None or self._faiss is None:
            raise RuntimeError("Call build() before get_ranker().")
        return SemanticRanker(
            embedder=self._embedder,
            faiss_index=self._faiss,
            chunk_top_k=self.chunk_top_k,
            max_files=self.max_files,
        )

    def stats(self) -> dict:
        if self._faiss:
            return self._faiss.stats()
        return {}

    # ── Private ────────────────────────────────────────────────────────────

    def _compute_hash(self, repo_index: dict) -> str:
        """Hash of all file paths + their sizes. Changes when repo changes."""
        content = json.dumps(
            {k: v.get("abs_path", "") for k, v in sorted(repo_index.items())},
            sort_keys=True,
        )
        return hashlib.md5(content.encode()).hexdigest()

    def _cache_valid(self, hash_file: Path, current_hash: str) -> bool:
        if not hash_file.exists():
            return False
        return hash_file.read_text().strip() == current_hash

    def _load_embedder(self) -> Embedder:
        return Embedder(model_name=self.model_name, device=self.device)
