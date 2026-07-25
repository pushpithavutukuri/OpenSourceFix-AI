"""
issue_classifier.py

Classifies a GitHub issue into a category so downstream stages can
adjust their strategy accordingly.

Categories
----------
bug         → something is broken; highest priority for fix generation
feature     → new capability requested; out of scope for patch generation
performance → correct but slow; fix generation targets profiling hotspots
docs        → documentation only; no code change needed
refactor    → code quality; fix generation targets structure not logic
unknown     → could not determine

Classification uses two layers:
1. Fast rule-based pass  (keyword matching, label inspection)
2. LLM confirmation pass (only when rule-based is uncertain)

This two-layer design is important:
- For obvious bugs (label="bug", title has "crash"/"error"/"fails") we skip the LLM entirely
- For ambiguous issues we spend one LLM call to get a confident classification
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords strongly associated with each category
_BUG_SIGNALS      = {"error", "crash", "fail", "broken", "exception", "traceback",
                     "bug", "regression", "incorrect", "wrong", "unexpected", "fix"}
_FEATURE_SIGNALS  = {"feature", "request", "add", "new", "support", "implement",
                     "enhance", "improvement", "wish", "proposal"}
_PERF_SIGNALS     = {"slow", "performance", "latency", "memory", "cpu", "speed",
                     "timeout", "hang", "freeze", "bottleneck", "optimize"}
_DOCS_SIGNALS     = {"docs", "documentation", "readme", "typo", "spelling",
                     "example", "tutorial", "guide"}
_REFACTOR_SIGNALS = {"refactor", "cleanup", "clean", "restructure", "rename",
                     "move", "reorganize", "technical debt"}


@dataclass
class ClassificationResult:
    category: str           # "bug" | "feature" | "performance" | "docs" | "refactor" | "unknown"
    confidence: str         # "high" | "medium" | "low"
    method: str             # "rule_based" | "llm" | "label"
    reason: str


class IssueClassifier:
    """
    Classifies GitHub issues by category.

    Args:
        model_client: Optional LLM client. If None, only rule-based classification runs.
    """

    def __init__(self, model_client=None):
        self.model = model_client

    def classify(self, issue) -> ClassificationResult:
        """
        Classify an issue. Tries rule-based first, falls back to LLM if uncertain.

        Args:
            issue: GitHubIssue dataclass.

        Returns:
            ClassificationResult.
        """
        # 1. Label-based (highest confidence — maintainers set these deliberately)
        label_result = self._classify_by_labels(issue)
        if label_result:
            return label_result

        # 2. Rule-based keyword scoring
        rule_result = self._classify_by_keywords(issue)
        if rule_result.confidence == "high":
            return rule_result

        # 3. LLM confirmation for uncertain cases
        if self.model:
            llm_result = self._classify_by_llm(issue)
            if llm_result:
                return llm_result

        # Return the medium-confidence rule result if LLM unavailable
        return rule_result

    # ── private ────────────────────────────────────────────────────────────

    def _classify_by_labels(self, issue) -> Optional[ClassificationResult]:
        """Check GitHub labels for explicit category signals."""
        label_map = {
            "bug": "bug", "bug report": "bug", "regression": "bug",
            "enhancement": "feature", "feature request": "feature", "feature": "feature",
            "performance": "performance", "perf": "performance",
            "documentation": "docs", "docs": "docs",
            "refactor": "refactor", "cleanup": "refactor",
        }
        for label in issue.labels:
            category = label_map.get(label.lower())
            if category:
                logger.info("Classified issue #%d as '%s' via label '%s'.", issue.number, category, label)
                return ClassificationResult(
                    category=category,
                    confidence="high",
                    method="label",
                    reason=f"GitHub label '{label}' explicitly marks this as {category}.",
                )
        return None

    def _classify_by_keywords(self, issue) -> ClassificationResult:
        """Score each category by keyword frequency in title + body."""
        text = f"{issue.title} {issue.body}".lower()
        words = set(re.findall(r"\b[a-z]+\b", text))

        scores = {
            "bug":         len(words & _BUG_SIGNALS),
            "feature":     len(words & _FEATURE_SIGNALS),
            "performance": len(words & _PERF_SIGNALS),
            "docs":        len(words & _DOCS_SIGNALS),
            "refactor":    len(words & _REFACTOR_SIGNALS),
        }

        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        if best_score == 0:
            return ClassificationResult("unknown", "low", "rule_based", "No category signals found.")

        # Determine confidence based on score margin
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]
        confidence = "high" if margin >= 2 else "medium" if best_score >= 1 else "low"

        logger.info("Rule-based: issue #%d → %s (score=%d, confidence=%s)", issue.number, best_category, best_score, confidence)
        return ClassificationResult(
            category=best_category,
            confidence=confidence,
            method="rule_based",
            reason=f"Keywords matched: score={best_score}, margin over next category={margin}.",
        )

    def _classify_by_llm(self, issue) -> Optional[ClassificationResult]:
        """Ask the LLM to classify when rule-based is uncertain."""
        import json
        prompt = f"""Classify this GitHub issue into exactly one category.

Issue title: {issue.title}
Issue body (first 400 chars): {issue.body[:400]}

Categories:
- bug         : Something is broken or incorrect
- feature     : Request for new functionality
- performance : Correct but slow or resource-heavy
- docs        : Documentation only, no code change
- refactor    : Code quality improvement, no behavior change
- unknown     : Cannot determine

Respond with ONLY a JSON object, no markdown:
{{"category": "<category>", "confidence": "<high|medium|low>", "reason": "<one sentence>"}}
"""
        try:
            raw = self.model.generate(prompt)
            clean = re.sub(r"```[a-z]*", "", raw).strip()
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            return ClassificationResult(
                category=data.get("category", "unknown"),
                confidence=data.get("confidence", "medium"),
                method="llm",
                reason=data.get("reason", ""),
            )
        except Exception as exc:
            logger.warning("LLM classification failed: %s", exc)
            return None
