"""
test_agent.py
Tests for RepairAgent, RetryManager, FailureAnalyzer.
All external calls (LLM, pytest, file system) are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestFailureAnalyzer:
    def test_classifies_assertion_error(self):
        from validation.failure_analyzer import FailureAnalyzer
        output = """
FAILED tests/test_auth.py::test_refresh - AssertionError: assert None == 'token'
E   AssertionError: assert None == 'token'
"""
        result = FailureAnalyzer().analyze(output)
        assert result.failure_type == "assertion_error"
        assert "None" in result.root_cause
        assert "tests/test_auth.py::test_refresh" in result.failed_tests

    def test_classifies_syntax_error(self):
        from validation.failure_analyzer import FailureAnalyzer
        output = "SyntaxError: invalid syntax (auth.py, line 42)"
        result = FailureAnalyzer().analyze(output)
        assert result.failure_type == "syntax_error"

    def test_classifies_import_error(self):
        from validation.failure_analyzer import FailureAnalyzer
        output = "ImportError: cannot import name 'refresh' from 'auth'"
        result = FailureAnalyzer().analyze(output)
        assert result.failure_type == "import_error"

    def test_empty_output(self):
        from validation.failure_analyzer import FailureAnalyzer
        result = FailureAnalyzer().analyze("")
        assert result.failure_type == "unknown"


class TestRetryManager:
    def test_records_attempts(self):
        from agent.retry_manager import RetryManager
        rm = RetryManager(max_attempts=3)
        rm.record_attempt(1, "diff1", False, "syntax_error", "bad", None)
        rm.record_attempt(2, "diff2", True, None, "", None)
        assert len(rm.history()) == 2
        assert rm.history()[1].passed is True

    def test_detects_repeated_failure(self):
        from agent.retry_manager import RetryManager
        rm = RetryManager(max_attempts=5)
        for i in range(3):
            rm.record_attempt(i+1, "", False, "assertion_error", "same", None)
        assert rm.should_change_strategy() is True
        assert rm.repeated_failure_type() == "assertion_error"

    def test_no_strategy_change_with_varied_failures(self):
        from agent.retry_manager import RetryManager
        rm = RetryManager(max_attempts=5)
        rm.record_attempt(1, "", False, "syntax_error", "", None)
        rm.record_attempt(2, "", False, "import_error", "", None)
        rm.record_attempt(3, "", False, "assertion_error", "", None)
        assert rm.should_change_strategy() is False


class TestRepositoryCache:
    def test_save_and_load(self, tmp_path):
        from memory.repository_cache import RepositoryCache
        from repository_analysis.dependency_graph import DependencyGraph

        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "auth.py").write_text("def login(): pass\n")

        index = {"auth.py": {"functions": ["login"], "abs_path": str(repo / "auth.py")}}
        dep_graph = DependencyGraph()

        cache = RepositoryCache(cache_dir=str(tmp_path / "cache"))
        cache.save(repo, index, dep_graph)

        assert cache.is_valid(repo)

        loaded = cache.load(repo)
        assert loaded is not None
        assert loaded.repo_name == "myrepo"
        assert "auth.py" in loaded.index

    def test_invalidated_after_file_change(self, tmp_path):
        from memory.repository_cache import RepositoryCache
        from repository_analysis.dependency_graph import DependencyGraph
        import time

        repo = tmp_path / "myrepo"
        repo.mkdir()
        f = repo / "auth.py"
        f.write_text("def login(): pass\n")

        index = {"auth.py": {"abs_path": str(f)}}
        dep_graph = DependencyGraph()
        cache = RepositoryCache(cache_dir=str(tmp_path / "cache"))
        cache.save(repo, index, dep_graph)

        # Simulate file change
        time.sleep(0.01)
        f.write_text("def login(): return True\n")
        # Touch the file to update mtime
        f.touch()

        assert not cache.is_valid(repo)


class TestRepositoryRanker:
    def test_ranks_multiple_files(self):
        from retrieval.repository_ranker import RepositoryRanker
        from issue_analysis.issue_fetcher import GitHubIssue
        from repository_analysis.dependency_graph import DependencyGraph
        from unittest.mock import MagicMock

        issue = GitHubIssue(1, "login bug", "session fails", "u", "open", "http://x")
        index = {
            "auth.py": {"abs_path": "/repo/auth.py", "functions": ["login"]},
            "models.py": {"abs_path": "/repo/models.py", "functions": ["User"]},
        }
        dep_graph = DependencyGraph()

        mock_ranker = MagicMock()
        mock_ranker.rank.return_value = [
            MagicMock(file_path="auth.py", score=0.9, reason="semantic"),
            MagicMock(file_path="models.py", score=0.6, reason="semantic"),
        ]

        ranker = RepositoryRanker(mock_ranker, dep_graph, index, max_files=5)
        results = ranker.rank(issue)
        assert len(results) >= 1
        assert results[0].path == "auth.py"
