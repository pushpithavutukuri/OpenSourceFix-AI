"""
file_ranker.py
Scores repository files against a set of issue keywords.
Returns a ranked list of (relative_path, score) tuples.
"""

import re
import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

RankedFiles = List[Tuple[str, int]]


class FileRanker:
    """
    Keyword-frequency ranker.

    Scoring strategy:
        +3  per keyword match in function/class name
        +2  per keyword match in import name
        +1  per keyword match in the file path itself

    Later this will be replaced with embedding cosine similarity.
    """

    def rank(
        self,
        index: Dict[str, Dict[str, Any]],
        keywords: List[str],
    ) -> RankedFiles:
        """
        Rank indexed files by relevance to the given keywords.

        Args:
            index:    RepoIndex from RepositoryIndexer.
            keywords: List of keywords extracted from the issue.

        Returns:
            Sorted list of (relative_path, score), highest first.
        """
        keywords_lower = [kw.lower() for kw in keywords]
        scores: Dict[str, int] = {}

        for rel_path, meta in index.items():
            score = 0

            for kw in keywords_lower:
                # File path match
                if kw in rel_path.lower():
                    score += 1

                # Function name match
                for fn in meta.get("functions", []):
                    if kw in fn.lower():
                        score += 3

                # Class name match
                for cls in meta.get("classes", []):
                    if kw in cls.lower():
                        score += 3

                # Import name match
                for imp in meta.get("imports", []):
                    if kw in imp.lower():
                        score += 2

            if score > 0:
                scores[rel_path] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        logger.info("Ranked %d files for keywords %s", len(ranked), keywords)
        return ranked
