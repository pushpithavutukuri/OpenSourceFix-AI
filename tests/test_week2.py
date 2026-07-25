"""
test_week2.py
Unit tests for Week 2: function localizer, diff validator, patch generator.
All LLM calls are mocked — tests run instantly without API keys.

Run: pytest tests/test_week2.py -v
"""

import numpy as np
import pytest
from unittest.mock import MagicMock
from pathlib import Path


# ── DiffValidator ─────────────────────────────────────────────────────────

class TestDiffValidator:
    VALID_DIFF = """--- a/auth/session.py
+++ b/auth/session.py
@@ -38,7 +38,10 @@
 def refresh_token(token):
-    return token.value
+    if token.is_expired():
+        raise TokenExpiredError("Token has expired")
+    return token.value
"""

    def test_valid_diff_passes(self):
        from fix_generation.diff_validator import DiffValidator
        result = DiffValidator().validate(self.VALID_DIFF)
        assert result.valid
        assert result.hunk_count == 1
        assert "auth/session.py" in result.files_changed

    def test_empty_diff_fails(self):
        from fix_generation.diff_validator import DiffValidator
        result = DiffValidator().validate("")
        assert not result.valid
        assert any("empty" in e.lower() for e in result.errors)

    def test_missing_hunk_header_fails(self):
        from fix_generation.diff_validator import DiffValidator
        result = DiffValidator().validate("--- a/foo.py\n+++ b/foo.py\n+added\n")
        assert not result.valid

    def test_unknown_file_warns(self):
        from fix_generation.diff_validator import DiffValidator
        result = DiffValidator().validate(self.VALID_DIFF, repo_index={"other.py": {}})
        assert result.valid
        assert any("not found" in w for w in result.warnings)


# ── FunctionLocalizer ─────────────────────────────────────────────────────

class TestFunctionLocalizer:
    def _make_issue(self):
        from issue_analysis.issue_fetcher import GitHubIssue
        return GitHubIssue(1, "Login fails", "session expires silently", "u", "open", "http://x")

    def _make_localization(self, files):
        from bug_localization.bug_localizer import BugLocalization
        return BugLocalization(primary_files=files, related_files=[], scores={})

    def test_returns_function_location(self, tmp_path):
        from bug_localization.function_localizer import FunctionLocalizer
        src = tmp_path / "auth.py"
        src.write_text("def refresh_token(tok):\n    return tok.value\n")
        index = {"auth.py": {"abs_path": str(src), "functions": ["refresh_token"]}}

        llm = MagicMock()
        llm.generate.return_value = '{"function": "refresh_token", "start_line": 1, "end_line": 2, "confidence": "high", "reason": "No expiry check."}'

        result = FunctionLocalizer(llm).localize(
            self._make_issue(), self._make_localization(["auth.py"]), index
        )
        assert len(result) == 1
        assert result[0].function == "refresh_token"
        assert result[0].confidence == "high"

    def test_handles_bad_json_gracefully(self, tmp_path):
        from bug_localization.function_localizer import FunctionLocalizer
        src = tmp_path / "foo.py"
        src.write_text("def bar(): pass\n")
        index = {"foo.py": {"abs_path": str(src), "functions": ["bar"]}}

        llm = MagicMock()
        llm.generate.return_value = "Sorry, I cannot help."

        result = FunctionLocalizer(llm).localize(
            self._make_issue(), self._make_localization(["foo.py"]), index
        )
        assert result == []

    def test_sorted_high_to_low(self):
        from bug_localization.function_localizer import FunctionLocation
        items = [
            FunctionLocation("f.py", "b", 1, 5, "low", "r"),
            FunctionLocation("f.py", "a", 6, 10, "high", "r"),
            FunctionLocation("f.py", "c", 11, 15, "medium", "r"),
        ]
        order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda r: order.get(r.confidence, 3))
        assert items[0].confidence == "high"
        assert items[-1].confidence == "low"


# ── PatchGenerator ────────────────────────────────────────────────────────

class TestPatchGenerator:
    VALID_DIFF = """--- a/auth.py
+++ b/auth.py
@@ -1,2 +1,4 @@
 def refresh_token(tok):
-    return tok.value
+    if tok.is_expired():
+        raise ValueError("expired")
+    return tok.value
"""

    def _make_issue(self):
        from issue_analysis.issue_fetcher import GitHubIssue
        return GitHubIssue(1, "Bug", "desc", "u", "open", "http://x")

    def _make_location(self, tmp_path):
        from bug_localization.function_localizer import FunctionLocation
        return FunctionLocation("auth.py", "refresh_token", 1, 5, "high", "no expiry check",
                                "def refresh_token(tok):\n    return tok.value")

    def test_returns_valid_patch(self, tmp_path):
        from fix_generation.patch_generator import PatchGenerator
        src = tmp_path / "auth.py"
        src.write_text("def refresh_token(tok):\n    return tok.value\n")
        index = {"auth.py": {"abs_path": str(src)}}

        llm = MagicMock()
        llm.generate.return_value = f"<DIFF>\n{self.VALID_DIFF}\n</DIFF>\n<EXPLANATION>Added expiry check.</EXPLANATION>"

        result = PatchGenerator(llm).generate(self._make_issue(), self._make_location(tmp_path), index)
        assert result.validation_passed
        assert result.attempts == 1
        assert "refresh_token" in result.diff

    def test_retries_on_invalid_diff(self, tmp_path):
        from fix_generation.patch_generator import PatchGenerator
        src = tmp_path / "auth.py"
        src.write_text("def refresh_token(tok):\n    return tok.value\n")
        index = {"auth.py": {"abs_path": str(src)}}

        llm = MagicMock()
        llm.generate.side_effect = [
            "<DIFF>not a real diff</DIFF><EXPLANATION>x</EXPLANATION>",
            f"<DIFF>\n{self.VALID_DIFF}\n</DIFF>\n<EXPLANATION>Fixed.</EXPLANATION>",
        ]
        result = PatchGenerator(llm, max_retries=1).generate(
            self._make_issue(), self._make_location(tmp_path), index
        )
        assert result.validation_passed
        assert result.attempts == 2


# ── PatchApplier ──────────────────────────────────────────────────────────

class TestPatchApplier:
    def test_dry_run_returns_result(self, tmp_path):
        from fix_generation.patch_applier import PatchApplier
        (tmp_path / "auth.py").write_text("def refresh_token(tok):\n    return tok.value\n")
        diff = """--- a/auth.py
+++ b/auth.py
@@ -1,2 +1,4 @@
 def refresh_token(tok):
-    return tok.value
+    if tok.is_expired():
+        raise ValueError("expired")
+    return tok.value
"""
        result = PatchApplier(tmp_path).apply(diff, dry_run=True)
        assert result.dry_run is True
        assert isinstance(result.success, bool)
