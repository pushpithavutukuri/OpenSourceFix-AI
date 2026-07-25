"""
test_evaluator.py
Tests for Evaluator metrics computation.
"""

from evaluation.evaluator import Evaluator


class TestEvaluator:

    def _gt(self, issue_num, correct_file, correct_function=""):
        return {"issue_number": issue_num, "correct_file": correct_file, "correct_function": correct_function}

    def _pr(self, issue_num, ranked, predicted_fn="", patch_passed=None):
        return {"issue_number": issue_num, "ranked_files": ranked, "predicted_function": predicted_fn, "patch_passed_tests": patch_passed}

    def test_perfect_hit_at_1(self):
        gt = [self._gt(1, "auth.py", "login")]
        pr = [self._pr(1, ["auth.py", "utils.py"], "login")]
        report = Evaluator().evaluate(pr, gt)
        assert report.hit_at_1 == 1
        assert report.hit_at_5 == 1
        assert report.function_hits == 1

    def test_hit_at_5_not_at_1(self):
        gt = [self._gt(1, "auth.py")]
        pr = [self._pr(1, ["utils.py", "models.py", "views.py", "forms.py", "auth.py"])]
        report = Evaluator().evaluate(pr, gt)
        assert report.hit_at_1 == 0
        assert report.hit_at_5 == 1

    def test_complete_miss(self):
        gt = [self._gt(1, "auth.py")]
        pr = [self._pr(1, ["unrelated.py", "other.py"])]
        report = Evaluator().evaluate(pr, gt)
        assert report.hit_at_1 == 0
        assert report.hit_at_5 == 0

    def test_patch_pass_rate(self):
        gt = [self._gt(1, "a.py"), self._gt(2, "b.py")]
        pr = [
            self._pr(1, ["a.py"], patch_passed=True),
            self._pr(2, ["b.py"], patch_passed=False),
        ]
        report = Evaluator().evaluate(pr, gt)
        assert report.patch_total == 2
        assert report.patch_passes == 1

    def test_empty_inputs(self):
        report = Evaluator().evaluate([], [])
        assert report.total == 0
        assert "No results" in report.summary()

    def test_to_dict_structure(self):
        gt = [self._gt(1, "auth.py")]
        pr = [self._pr(1, ["auth.py"])]
        d = Evaluator().evaluate(pr, gt).to_dict()
        assert "file_hit_at_1" in d
        assert "file_hit_at_5" in d
        assert "function_hit_rate" in d


class TestStackTraceParser:
    def test_parses_python_traceback(self):
        from repository_analysis.stack_trace_parser import StackTraceParser
        text = """
Traceback (most recent call last):
  File "auth/session.py", line 42, in refresh_token
    return token.value
  File "utils/db.py", line 10, in get_token
    return db.query(Token).first()
AttributeError: 'NoneType' object has no attribute 'value'
"""
        result = StackTraceParser().parse(text)
        assert result.has_traceback
        assert result.error_type == "AttributeError"
        # innermost first → refresh_token is index 0
        assert result.frames[0].function == "refresh_token"
        assert result.frames[0].line == 42

    def test_no_traceback_returns_empty(self):
        from repository_analysis.stack_trace_parser import StackTraceParser
        result = StackTraceParser().parse("This is a feature request with no stack trace.")
        assert not result.has_traceback
        assert result.frames == []

    def test_to_bug_hints(self):
        from repository_analysis.stack_trace_parser import StackTraceParser
        text = """
Traceback (most recent call last):
  File "auth/session.py", line 42, in refresh_token
    return token.value
ValueError: bad value
"""
        result = StackTraceParser().parse(text)
        hints = StackTraceParser().to_bug_hints(result)
        assert hints[0]["file"] == "auth/session.py"
        assert hints[0]["confidence"] == "high"
