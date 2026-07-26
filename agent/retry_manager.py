"""
agent/retry_manager.py

Manages attempt records for the repair agent.
Tracks what was tried, what failed, and why — building the audit trail
that makes the agent's decisions explainable.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AttemptRecord:
    attempt_num: int
    diff: str
    passed: bool
    failure_type: Optional[str]    # "syntax_error" | "assertion_error" | "import_error" | ...
    failure_detail: str
    analysis: Optional[object]     # FailureAnalysis — typed as object to avoid circular import


class RetryManager:
    """
    Records attempt history and provides stopping-condition logic.

    Stopping conditions (beyond max_attempts):
    - Same failure type seen 3 times in a row → switch strategy signal
    - Syntax error on attempt 1 → immediately retry with stricter prompt
    """

    def __init__(self, max_attempts: int = 5):
        self.max_attempts = max_attempts
        self._history: List[AttemptRecord] = []

    def record_attempt(
        self,
        attempt_num: int,
        diff: str,
        passed: bool,
        failure_type: Optional[str],
        failure_detail: str,
        analysis: Optional[object],
    ) -> AttemptRecord:
        record = AttemptRecord(
            attempt_num=attempt_num,
            diff=diff,
            passed=passed,
            failure_type=failure_type,
            failure_detail=failure_detail,
            analysis=analysis,
        )
        self._history.append(record)
        logger.info(
            "Attempt %d recorded: passed=%s, failure_type=%s",
            attempt_num, passed, failure_type,
        )
        return record

    def should_change_strategy(self) -> bool:
        """True if the last 3 attempts had the same failure type."""
        if len(self._history) < 3:
            return False
        last_three = [r.failure_type for r in self._history[-3:]]
        return len(set(last_three)) == 1 and last_three[0] is not None

    def repeated_failure_type(self) -> Optional[str]:
        if self.should_change_strategy():
            return self._history[-1].failure_type
        return None

    def history(self) -> List[AttemptRecord]:
        return list(self._history)

    def best_attempt(self) -> Optional[AttemptRecord]:
        """Return the attempt closest to passing (fewest failed tests)."""
        non_passing = [r for r in self._history if not r.passed]
        if not non_passing:
            return None
        # Prefer apply_failed < syntax < assertion (heuristic ordering)
        order = {"apply_failed": 0, "syntax_error": 1, "import_error": 2,
                 "assertion_error": 3, "unknown": 4}
        return min(non_passing, key=lambda r: order.get(r.failure_type or "unknown", 99))
