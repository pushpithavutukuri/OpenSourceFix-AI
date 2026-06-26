"""
faiss_index.py

Builds a FAISS flat index over code chunk embeddings.
Supports save/load so you don't re-embed on every run.

Index type: IndexFlatIP (inner product on normalized vectors = cosine similarity)
This is the right choice for:
    - Exact nearest-neighbor search (no approximation error)
    - Normalized BGE vectors (inner product == cosine)
    - Repos up to ~500k chunks (flat is fast enough)

For repos > 500k chunks, swap to IndexIVFFlat with nlist=1024.
"""

import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import faiss

from retrieval.chunk_splitter import CodeChunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    chunk: CodeChunk
    score: float          # cosine similarity in [0, 1]
    rank: int


class FAISSIndex:
    """
    Wraps a FAISS IndexFlatIP with chunk metadata.

    Build flow:
        index = FAISSIndex()
        index.build(chunks, embeddings)
        index.save(path)

    Query flow:
        index = FAISSIndex.load(path)
        results = index.search(query_vector, top_k=10)
    """

    def __init__(self):
        self._index: Optional[faiss.Index] = None
        self._chunks: List[CodeChunk] = []

    # ── Build ──────────────────────────────────────────────────────────────

    def build(self, chunks: List[CodeChunk], embeddings: np.ndarray) -> None:
        """
        Build the FAISS index from chunk embeddings.

        Args:
            chunks:     Parallel list of CodeChunk objects.
            embeddings: np.ndarray of shape (len(chunks), dim), float32,
                        L2-normalized (as produced by Embedder).
        """
        assert len(chunks) == embeddings.shape[0], (
            f"Mismatch: {len(chunks)} chunks vs {embeddings.shape[0]} embeddings"
        )

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)   # inner product on normalized = cosine
        self._index.add(embeddings)
        self._chunks = chunks

        logger.info(
            "FAISS index built: %d vectors, dim=%d", self._index.ntotal, dim
        )

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[SearchResult]:
        """
        Find the top-k most similar chunks to the query vector.

        Args:
            query_vector: Shape (1, dim), float32, L2-normalized.
            top_k:        Number of results to return.

        Returns:
            List of SearchResult, sorted by score descending.
        """
        if self._index is None:
            raise RuntimeError("Index not built. Call build() or load() first.")

        top_k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_vector, top_k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:    # FAISS returns -1 for empty slots
                continue
            results.append(SearchResult(
                chunk=self._chunks[idx],
                score=float(score),
                rank=rank + 1,
            ))

        return results

    # ── Persist ────────────────────────────────────────────────────────────

    def save(self, directory: Path) -> None:
        """
        Save the FAISS index and chunk metadata to disk.

        Saves two files:
            directory/faiss.index   ← FAISS binary
            directory/chunks.pkl    ← serialized CodeChunk list
        """
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / "faiss.index"))
        with open(directory / "chunks.pkl", "wb") as f:
            pickle.dump(self._chunks, f)
        logger.info("FAISS index saved to %s", directory)

    @classmethod
    def load(cls, directory: Path) -> "FAISSIndex":
        """
        Load a previously saved index from disk.

        Args:
            directory: Same directory passed to save().

        Returns:
            Populated FAISSIndex ready for search().
        """
        instance = cls()
        instance._index = faiss.read_index(str(directory / "faiss.index"))
        with open(directory / "chunks.pkl", "rb") as f:
            instance._chunks = pickle.load(f)
        logger.info(
            "FAISS index loaded: %d vectors from %s",
            instance._index.ntotal, directory
        )
        return instance

    # ── Stats ──────────────────────────────────────────────────────────────

    @property
    def total_chunks(self) -> int:
        return self._index.ntotal if self._index else 0

    def stats(self) -> dict:
        file_count = len({c.file_path for c in self._chunks})
        return {
            "total_chunks": self.total_chunks,
            "unique_files": file_count,
            "chunk_types": {
                t: sum(1 for c in self._chunks if c.type == t)
                for t in ("function", "class", "module")
            },
        }
