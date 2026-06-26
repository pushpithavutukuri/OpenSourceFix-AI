"""
test_issue_analysis.py
Unit tests for issue fetching and keyword extraction.
"""

import pytest
from unittest.mock import MagicMock

from issue_analysis.issue_fetcher import GitHubIssue
from issue_analysis.keyword_extractor import KeywordExtractor


def make_issue(**kwargs) -> GitHubIssue:
    defaults = dict(
        number=42,
        title="Login fails after session timeout",
        body="When the session expires the `refresh_token` endpoint returns 500.",
        author="user",
        state="open",
        url="https://github.com/example/repo/issues/42",
        labels=[],
        comments=[],
    )
    defaults.update(kwargs)
    return GitHubIssue(**defaults)


class TestKeywordExtractor:
    def test_backtick_terms_are_included(self):
        issue = make_issue(body="The `session_manager` module raises an error.")
        keywords = KeywordExtractor().extract(issue)
        assert "session_manager" in keywords

    def test_stop_words_are_excluded(self):
        issue = make_issue(title="the and or but")
        keywords = KeywordExtractor().extract(issue)
        for sw in ["the", "and", "or", "but"]:
            assert sw not in keywords

    def test_title_words_are_included(self):
        issue = make_issue(title="authentication timeout error")
        keywords = KeywordExtractor().extract(issue)
        assert "authentication" in keywords
        assert "timeout" in keywords

    def test_snake_case_detected(self):
        issue = make_issue(body="The refresh_token function is broken.")
        keywords = KeywordExtractor().extract(issue)
        assert "refresh_token" in keywords

    def test_deduplication(self):
        issue = make_issue(
            title="login error",
            body="login error happens on login",
        )
        keywords = KeywordExtractor().extract(issue)
        assert keywords.count("login") == 1
