"""
keyword_extractor.py
Extracts programming-relevant keywords from a GitHub issue.
"""

import re
import logging
from typing import List

from issue_analysis.issue_fetcher import GitHubIssue

logger = logging.getLogger(__name__)

# Common English stop words that carry no code relevance
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "in", "on", "at", "to", "for", "of", "with", "this", "that", "it",
    "i", "we", "you", "he", "she", "they", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "when", "if", "not", "no", "so", "as", "by", "from", "about",
    "after", "before", "than", "then", "there", "here", "also",
}


class KeywordExtractor:
    """
    Rule-based keyword extractor.

    Priority:
    1. Backtick-quoted identifiers  →  highest signal
    2. CamelCase / snake_case tokens →  high signal (code identifiers)
    3. All remaining non-stop words  →  medium signal

    Later this will be replaced with an LLM-based extractor.
    """

    def extract(self, issue: GitHubIssue) -> List[str]:
        """
        Extract keywords from title + body + comments.

        Returns:
            Deduplicated, lowercased keyword list, highest-signal first.
        """
        full_text = "\n".join(
            [issue.title, issue.body] + issue.comments
        )

        backtick_terms = re.findall(r"`([^`]+)`", full_text)
        camel_snake = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+|[a-z]+(?:_[a-z]+)+)\b", full_text)
        all_words = re.findall(r"\b[a-zA-Z]{3,}\b", full_text.lower())
        regular_words = [w for w in all_words if w not in STOP_WORDS]

        # Merge in priority order, dedup while preserving order
        seen = set()
        keywords = []
        for term in backtick_terms + camel_snake + regular_words:
            normalized = term.lower().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                keywords.append(normalized)

        logger.info("Extracted %d keywords from issue #%d", len(keywords), issue.number)
        return keywords
