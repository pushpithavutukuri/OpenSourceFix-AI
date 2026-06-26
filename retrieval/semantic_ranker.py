"""
semantic_ranker.py

Replaces the keyword-based FileRanker with BGE + FAISS semantic search.

Pipeline:
    Issue text
        ↓  embed_query()
    Query vector
        ↓  FAISSIndex.search()
    Top-K chunks (function/class level)
        ↓  aggregate by file
    Ranked file list  ←  same interface as old FileRanker

This module is the "drop-in upgrade" to the existing pipeline.
Everything downstream (BugLocalizer, FixGenerator) stays the same.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

from issue_analysis.issue_fetcher import GitHubIssue
from retrieval.embedder import Embedder
from retrieval.faiss_index import FAISSIndex, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class SemanticRankResult:
    """Ranked file with aggregated evidence from chunk-level search."""
    file_path: str
    score: float                        # aggregated similarity score
    top_chunks: List[SearchResult] = field(default_factory=list)   # chunk-level evidence
    rank: int = 0


class SemanticRanker:
    """
    Semantic file ranker using BGE embeddings + FAISS.

    Aggregation strategy:
        For each file, collect all chunks that appeared in top-K results.
        File score = sum of chunk similarity scores.
        This rewards files with MULTIPLE relevant functions over files
        that just happen to have one matching name.

    Args:
        embedder:       Embedder instance (BGE model).
        faiss_index:    Built/loaded FAISSIndex.
        chunk_top_k:    How many chunks to retrieve from FAISS per query.
        max_files:      Max number of files to return.
    """

    def __init__(
        self,
        embedder: Embedder,
        faiss_index: FAISSIndex,
        chunk_top_k: int = 30,
        max_files: int = 10,
    ):
        self.embedder = embedder
        self.index = faiss_index
        self.chunk_top_k = chunk_top_k
        self.max_files = max_files

    def rank(self, issue: GitHubIssue) -> List[SemanticRankResult]:
        """
        Rank repository files by semantic similarity to the issue.

        Args:
            issue: GitHubIssue object.

        Returns:
            List of SemanticRankResult, sorted by score descending.
        """
        query_text = self._build_query(issue)
        query_vector = self.embedder.embed_query(query_text)

        # Retrieve top-K chunks from FAISS
        chunk_results: List[SearchResult] = self.index.search(
            query_vector, top_k=self.chunk_top_k
        )

        # Aggregate chunk scores by file
        file_scores: Dict[str, float] = defaultdict(float)
        file_chunks: Dict[str, List[SearchResult]] = defaultdict(list)

        for result in chunk_results:
            fp = result.chunk.file_path
            file_scores[fp] += result.score
            file_chunks[fp].append(result)

        # Build ranked list
        ranked = []
        for fp, score in sorted(file_scores.items(), key=lambda x: x[1], reverse=True):
            ranked.append(SemanticRankResult(
                file_path=fp,
                score=round(score, 4),
                top_chunks=sorted(file_chunks[fp], key=lambda r: r.score, reverse=True),
            ))

        # Assign ranks and cap
        for i, r in enumerate(ranked):
            r.rank = i + 1
        ranked = ranked[: self.max_files]

        logger.info(
            "SemanticRanker: query='%s...' → %d files ranked",
            query_text[:60], len(ranked)
        )
        return ranked

    def rank_to_tuples(self, issue: GitHubIssue) -> List[Tuple[str, float]]:
        """
        Convenience method returning (file_path, score) tuples.
        Drop-in replacement for FileRanker.rank() output shape.
        """
        return [(r.file_path, r.score) for r in self.rank(issue)]

    # ── Private ────────────────────────────────────────────────────────────

    def _build_query(self, issue: GitHubIssue) -> str:
        """
        Combine issue title + body + labels into one query string.

        The title carries the most signal, so it's repeated.
        Labels (like "bug", "regression") add useful context.
        """
        parts = [issue.title, issue.title]   # title twice = higher weight
        if issue.body:
            # First 512 chars of body; rest is usually stack traces / logs
            parts.append(issue.body[:512])
        if issue.labels:
            parts.append(" ".join(issue.labels))
        return " ".join(parts)
