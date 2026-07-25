"""
test_issue_classifier.py
Tests for IssueClassifier — all LLM calls are mocked.
"""

import pytest
from unittest.mock import MagicMock
from issue_analysis.issue_fetcher import GitHubIssue
from issue_analysis.issue_classifier import IssueClassifier


def make_issue(title="", body="", labels=None):
    return GitHubIssue(
        number=1, title=title, body=body, author="u",
        state="open", url="http://x", labels=labels or []
    )


class TestIssueClassifier:

    def test_classifies_by_label_bug(self):
        issue = make_issue(title="something wrong", labels=["bug"])
        result = IssueClassifier().classify(issue)
        assert result.category == "bug"
        assert result.method == "label"
        assert result.confidence == "high"

    def test_classifies_by_label_feature(self):
        issue = make_issue(title="add dark mode", labels=["enhancement"])
        result = IssueClassifier().classify(issue)
        assert result.category == "feature"

    def test_rule_based_bug_from_keywords(self):
        issue = make_issue(title="login crashes with traceback error")
        result = IssueClassifier().classify(issue)
        assert result.category == "bug"
        assert result.method == "rule_based"

    def test_rule_based_performance(self):
        issue = make_issue(title="API is very slow and causes timeout")
        result = IssueClassifier().classify(issue)
        assert result.category == "performance"

    def test_llm_called_for_ambiguous_issue(self):
        issue = make_issue(title="update the thing")  # no clear signal
        llm = MagicMock()
        llm.generate.return_value = '{"category": "feature", "confidence": "medium", "reason": "Sounds like an update request."}'
        result = IssueClassifier(model_client=llm).classify(issue)
        assert result.category == "feature"
        assert result.method == "llm"

    def test_no_crash_without_llm(self):
        issue = make_issue(title="update the thing")
        result = IssueClassifier().classify(issue)   # no model_client
        assert result.category in {"bug", "feature", "performance", "docs", "refactor", "unknown"}
