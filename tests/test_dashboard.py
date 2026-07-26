"""
test_dashboard.py
Tests for the benchmark dashboard HTML generator.
"""

import pytest
from pathlib import Path
from evaluation.evaluator import Evaluator


class TestBenchmarkDashboard:
    def _make_report(self):
        gt = [{"issue_number": 1, "correct_file": "auth.py", "correct_function": "login"}]
        pr = [{"issue_number": 1, "ranked_files": ["auth.py", "utils.py"], "predicted_function": "login", "patch_passed_tests": True}]
        return Evaluator().evaluate(pr, gt)

    def test_generates_html_file(self, tmp_path):
        from evaluation.dashboard import BenchmarkDashboard
        report = self._make_report()
        output = tmp_path / "dashboard.html"
        BenchmarkDashboard().generate(report, str(output))
        assert output.exists()
        content = output.read_text()
        assert "<html" in content
        assert "OpenSourceFix AI" in content

    def test_html_contains_metrics(self, tmp_path):
        from evaluation.dashboard import BenchmarkDashboard
        report = self._make_report()
        output = tmp_path / "dashboard.html"
        BenchmarkDashboard().generate(report, str(output))
        content = output.read_text()
        assert "100.0%" in content   # hit@1 should be 100% for this case
        assert "File Hit@1" in content

    def test_html_contains_issue_row(self, tmp_path):
        from evaluation.dashboard import BenchmarkDashboard
        report = self._make_report()
        output = tmp_path / "dashboard.html"
        BenchmarkDashboard().generate(report, str(output))
        content = output.read_text()
        assert "#1" in content
        assert "auth.py" in content
