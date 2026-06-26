"""
bug_localizer.py
Combines ranked files + dependency graph to output the most likely bug locations.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Set

from repository_analysis.file_ranker import RankedFiles
from repository_analysis.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class BugLocalization:
    primary_files: List[str] = field(default_factory=list)   # highest-score files
    related_files: List[str] = field(default_factory=list)   # pulled in via dependency graph
    scores: Dict[str, int] = field(default_factory=dict)


class BugLocalizer:
    """
    Stage 1 bug localization (keyword + dependency heuristic).

    Strategy:
        1. Take top-N ranked files as primary suspects.
        2. For each primary file, look up its imports in the dependency graph.
        3. Any imported module that also appears in the index is a related file.

    Later this becomes:
        - LLM-based function-level localization
        - Embedding similarity re-ranking
        - Stack trace parsing
    """

    def __init__(self, top_n: int = 5):
        self.top_n = top_n

    def localize(
        self,
        ranked: RankedFiles,
        dep_graph: DependencyGraph,
        index: Dict[str, Any],
    ) -> BugLocalization:
        """
        Produce a BugLocalization result.

        Args:
            ranked:    Output of FileRanker.rank().
            dep_graph: Built DependencyGraph.
            index:     RepoIndex from RepositoryIndexer.

        Returns:
            BugLocalization with primary and related files.
        """
        top_files = [path for path, _ in ranked[: self.top_n]]
        score_map = {path: score for path, score in ranked[: self.top_n]}

        # Collect related files via dependency graph
        related: Set[str] = set()
        index_keys = set(index.keys())

        for rel_path in top_files:
            abs_path = index.get(rel_path, {}).get("abs_path", "")
            imports = dep_graph.get_dependencies(Path(abs_path))
            for imp in imports:
                # Map module name back to a file key if possible
                for key in index_keys:
                    if imp.replace(".", "/") in key or key.endswith(f"{imp.replace('.', '/')}.py"):
                        if key not in top_files:
                            related.add(key)

        result = BugLocalization(
            primary_files=top_files,
            related_files=sorted(related),
            scores=score_map,
        )

        logger.info(
            "Bug localization: %d primary, %d related files.",
            len(result.primary_files),
            len(result.related_files),
        )
        return result
