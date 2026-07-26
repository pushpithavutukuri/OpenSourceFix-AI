"""
validation/failure_analyzer.py

Analyzes pytest output to produce a structured explanation of WHY
tests failed, not just THAT they failed.

This feeds directly into the repair agent's feedback prompt, giving
the LLM specific, actionable information instead of raw pytest logs.

Example transformation
----------------------
Input (raw pytest stdout):
    FAILED tests/test_auth.py::test_refresh - AssertionError: assert None == 'token_value'
    E   AssertionError: assert None == 'token_value'

Output (FailureAnalysis):
    failure_type:   "assertion_error"
    root_cause:     "refresh_token() returned None instead of 'token_value'"
    failed_tests:   ["tests/test_auth.py::test_refresh"]
    affected_lines: ["auth/session.py:42"]
    suggested_fix:  "Check that refresh_token() returns a value in all code paths"
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Regex patterns for pytest output parsing
_FAILED_RE      = re.compile(r"FAILED (.+?) -")
_ERROR_TYPE_RE  = re.compile(r"E\s+(\w+(?:Error|Exception|Warning)):")
_ASSERT_RE      = re.compile(r"AssertionError: assert (.+)")
_FILE_LINE_RE   = re.compile(r"(\S+\.py):(\d+): in (\w+)")
_IMPORT_ERR_RE  = re.compile(r"ImportError: (.+)")
_SYNTAX_ERR_RE  = re.compile(r"SyntaxError: (.+)")
_TYPE_ERR_RE    = re.compile(r"TypeError: (.+)")
_VALUE_ERR_RE   = re.compile(r"ValueError: (.+)")


@dataclass
class FailureAnalysis:
    failure_type: str            # "assertion_error" | "syntax_error" | "import_error" | ...
    root_cause: str              # human-readable explanation
    failed_tests: List[str] = field(default_factory=list)
    affected_lines: List[str] = field(default_factory=list)
    suggested_fix: str = ""
    llm_analysis: str = ""       # populated if LLM was used
    raw_snippet: str = ""        # key section of pytest output


class FailureAnalyzer:
    """
    Analyzes pytest output into a structured FailureAnalysis.

    Two-pass approach:
    1. Rule-based parsing  — fast, handles common patterns
    2. LLM analysis        — for complex failures rule-based can't classify
    """

    def __init__(self, model_client=None):
        self.model = model_client

    def analyze(self, pytest_output: str) -> FailureAnalysis:
        """
        Analyze raw pytest stdout/stderr.

        Args:
            pytest_output: Combined stdout + stderr from pytest run.

        Returns:
            FailureAnalysis with structured failure information.
        """
        if not pytest_output.strip():
            return FailureAnalysis(failure_type="unknown", root_cause="No pytest output captured.")

        # Pass 1: rule-based
        analysis = self._rule_based_analysis(pytest_output)

        # Pass 2: LLM enrichment for unclear failures
        if analysis.failure_type == "unknown" and self.model:
            analysis = self._llm_analysis(pytest_output, analysis)

        logger.info(
            "FailureAnalyzer: type=%s, tests=%d",
            analysis.failure_type, len(analysis.failed_tests),
        )
        return analysis

    # ── private ────────────────────────────────────────────────────────────

    def _rule_based_analysis(self, output: str) -> FailureAnalysis:
        failed_tests = _FAILED_RE.findall(output)
        affected_lines = [
            f"{m.group(1)}:{m.group(2)}" for m in _FILE_LINE_RE.finditer(output)
        ]

        # Classify by error type
        if _SYNTAX_ERR_RE.search(output):
            match = _SYNTAX_ERR_RE.search(output)
            return FailureAnalysis(
                failure_type="syntax_error",
                root_cause=f"SyntaxError: {match.group(1)}",
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix="Fix the syntax error in the generated patch before applying.",
                raw_snippet=self._extract_snippet(output),
            )

        if _IMPORT_ERR_RE.search(output):
            match = _IMPORT_ERR_RE.search(output)
            return FailureAnalysis(
                failure_type="import_error",
                root_cause=f"ImportError: {match.group(1)}",
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix="Check that all imports referenced in the patch exist in the repository.",
                raw_snippet=self._extract_snippet(output),
            )

        if _ASSERT_RE.search(output):
            match = _ASSERT_RE.search(output)
            assertion = match.group(1)
            root_cause = self._explain_assertion(assertion)
            return FailureAnalysis(
                failure_type="assertion_error",
                root_cause=root_cause,
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix=self._suggest_from_assertion(assertion),
                raw_snippet=self._extract_snippet(output),
            )

        if _TYPE_ERR_RE.search(output):
            match = _TYPE_ERR_RE.search(output)
            return FailureAnalysis(
                failure_type="type_error",
                root_cause=f"TypeError: {match.group(1)}",
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix="Check argument types and return types in the patched function.",
                raw_snippet=self._extract_snippet(output),
            )

        if _VALUE_ERR_RE.search(output):
            match = _VALUE_ERR_RE.search(output)
            return FailureAnalysis(
                failure_type="value_error",
                root_cause=f"ValueError: {match.group(1)}",
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix="Check that input values are validated before use.",
                raw_snippet=self._extract_snippet(output),
            )

        if failed_tests:
            return FailureAnalysis(
                failure_type="test_failure",
                root_cause=f"{len(failed_tests)} test(s) failed.",
                failed_tests=failed_tests,
                affected_lines=affected_lines,
                suggested_fix="Review the test expectations against the patched behavior.",
                raw_snippet=self._extract_snippet(output),
            )

        return FailureAnalysis(
            failure_type="unknown",
            root_cause="Could not determine failure type from pytest output.",
            raw_snippet=output[:500],
        )

    def _llm_analysis(self, output: str, base: FailureAnalysis) -> FailureAnalysis:
        """Use LLM to analyze complex failures."""
        prompt = f"""Analyze this pytest failure output and explain what went wrong.

## Pytest Output
{output[:1500]}

Respond with ONLY a JSON object:
{{
    "failure_type": "<assertion_error|syntax_error|import_error|type_error|value_error|logic_error|unknown>",
    "root_cause":   "<one sentence: what exactly failed and why>",
    "suggested_fix": "<one sentence: what the patch should do differently>"
}}
"""
        import json, re as re2
        try:
            raw = self.model.generate(prompt)
            clean = re2.sub(r"```[a-z]*", "", raw).strip()
            match = re2.search(r"\{.*\}", clean, re2.DOTALL)
            if match:
                data = json.loads(match.group())
                base.failure_type  = data.get("failure_type", base.failure_type)
                base.root_cause    = data.get("root_cause", base.root_cause)
                base.suggested_fix = data.get("suggested_fix", "")
                base.llm_analysis  = raw
        except Exception as exc:
            logger.warning("LLM failure analysis failed: %s", exc)
        return base

    def _explain_assertion(self, assertion: str) -> str:
        """Turn a raw assert string into a readable sentence."""
        # assert None == 'value'  →  "Function returned None instead of 'value'"
        none_match = re.match(r"(None) == (.+)", assertion)
        if none_match:
            return f"Function returned None instead of {none_match.group(2)}"
        eq_match = re.match(r"(.+) == (.+)", assertion)
        if eq_match:
            return f"Expected {eq_match.group(2)} but got {eq_match.group(1)}"
        return f"Assertion failed: {assertion}"

    def _suggest_from_assertion(self, assertion: str) -> str:
        if "None" in assertion:
            return "Ensure the patched function returns a value in all code paths."
        if "==" in assertion:
            return "Check the return value matches what the tests expect."
        return "Review the patched logic against the test expectations."

    def _extract_snippet(self, output: str, max_lines: int = 20) -> str:
        """Extract the most relevant section of pytest output."""
        lines = output.splitlines()
        # Find the first FAILED line and return surrounding context
        for i, line in enumerate(lines):
            if "FAILED" in line or "ERROR" in line or "assert" in line.lower():
                start = max(0, i - 3)
                end = min(len(lines), i + max_lines)
                return "\n".join(lines[start:end])
        return "\n".join(lines[:max_lines])
