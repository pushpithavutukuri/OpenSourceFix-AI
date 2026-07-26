"""
retrieval/repository_ranker.py

Multi-file retrieval: ranks ALL relevant files for a bug, not just one.

Many real bugs span multiple files:
    auth/session.py     ← where the bug is
    models/token.py     ← Token model that session.py imports
    middleware/auth.py  ← middleware that calls session.py
    tests/test_auth.py  ← tests that expose the bug

This module returns a ranked list of ALL files that are likely
relevant to understanding and fixing the bug.

Strategy
--------
1. Semantic search (BGE + FAISS) for direct relevance
2. Dependency expansion: if file A is relevant, files A imports get a
   relevance boost (they provide context the LLM needs)
3. Test file inclusion: tests that cover the top files are included
   automatically (the LLM needs to understand what "correct" looks like)
4. Re-rank with Reciprocal Rank Fusion across all signals
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RankedFile:
    path: str
    score: float
    reason: str           # "semantic" | "dependency" | "test_coverage" | "stack_trace"
    rank: int = 0


class RepositoryRanker:
    """
    Ranks multiple repository files relevant to a bug.

    Args:
        semantic_ranker:  SemanticRanker from retrieval/semantic_ranker.py
        dep_graph:        DependencyGraph from the repository indexer
        index:            RepoIndex dict
        max_files:        Maximum files to return (default 10)
        dep_boost:        Score multiplier for dependency-expanded files (default 0.5)
    """

    def __init__(
        self,
        semantic_ranker,
        dep_graph,
        index: dict,
        max_files: int = 10,
        dep_boost: float = 0.5,
    ):
        self.semantic_ranker = semantic_ranker
        self.dep_graph = dep_graph
        self.index = index
        self.max_files = max_files
        self.dep_boost = dep_boost

    def rank(self, issue, stack_hints: List[str] = None) -> List[RankedFile]:
        """
        Produce a multi-file ranked list.

        Args:
            issue:       GitHubIssue dataclass.
            stack_hints: Optional list of file paths from stack trace parser.

        Returns:
            List of RankedFile, sorted by combined score descending.
        """
        scores: Dict[str, float] = defaultdict(float)
        reasons: Dict[str, str] = {}

        # 1. Semantic search
        semantic_results = self.semantic_ranker.rank(issue)
        for result in semantic_results:
            scores[result.file_path] += result.score
            reasons[result.file_path] = "semantic"

        # 2. Stack trace hints (highest priority signal)
        if stack_hints:
            for i, hint_file in enumerate(stack_hints):
                boost = 2.0 / (i + 1)   # 2.0 for first, 1.0 for second, etc.
                # Find closest match in index
                for idx_path in self.index:
                    if hint_file in idx_path or idx_path.endswith(hint_file):
                        scores[idx_path] += boost
                        reasons[idx_path] = "stack_trace"
                        break

        # 3. Dependency expansion
        top_files = sorted(scores, key=scores.get, reverse=True)[:5]
        for rel_path in top_files:
            abs_path = self.index.get(rel_path, {}).get("abs_path", "")
            if not abs_path:
                continue
            from pathlib import Path
            deps = self.dep_graph.get_dependencies(Path(abs_path))
            for dep_module in deps:
                for idx_path in self.index:
                    dep_clean = dep_module.replace(".", "/")
                    if dep_clean in idx_path and idx_path not in scores:
                        scores[idx_path] += scores[rel_path] * self.dep_boost
                        reasons[idx_path] = "dependency"

        # 4. Test file inclusion
        for path in list(scores.keys()):
            test_candidates = self._find_test_files(path)
            for tc in test_candidates:
                if tc in self.index and tc not in scores:
                    scores[tc] += 0.3
                    reasons[tc] = "test_coverage"

        # 5. Build final ranked list
        ranked = []
        for i, (path, score) in enumerate(
            sorted(scores.items(), key=lambda x: x[1], reverse=True)[: self.max_files]
        ):
            ranked.append(RankedFile(
                path=path,
                score=round(score, 4),
                reason=reasons.get(path, "semantic"),
                rank=i + 1,
            ))

        logger.info(
            "RepositoryRanker: %d files ranked for issue #%d",
            len(ranked), issue.number,
        )
        return ranked

    def _find_test_files(self, source_path: str) -> List[str]:
        """Find test files that likely cover a given source file."""
        module_name = source_path.replace("/", "_").replace(".py", "")
        candidates = []
        for idx_path in self.index:
            if "test" in idx_path.lower() and (
                module_name in idx_path or
                source_path.split("/")[-1].replace(".py", "") in idx_path
            ):
                candidates.append(idx_path)
        return candidates
