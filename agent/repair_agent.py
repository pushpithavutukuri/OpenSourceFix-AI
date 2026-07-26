"""
agent/repair_agent.py

Autonomous iterative repair agent.

Transforms the pipeline from a one-shot generator into a self-correcting
agent that reasons about failures and retries until tests pass or a
stopping condition is reached.

Loop
----
    Generate patch
        ↓
    Apply patch (sandbox or disk)
        ↓
    Run tests
        ↓
    Passed? → done
        ↓
    Analyze failure
        ↓
    Build repair prompt with error context
        ↓
    Generate improved patch
        ↓
    Repeat (up to max_attempts)

This is structurally identical to how Codex, SWE-agent, and Claude Code
operate — read the error, reason about it, produce a better fix.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent.retry_manager import RetryManager, AttemptRecord
from fix_generation.patch_generator import PatchGenerator, PatchResult
from fix_generation.patch_applier import PatchApplier
from validation.validator import Validator
from validation.failure_analyzer import FailureAnalyzer, FailureAnalysis

logger = logging.getLogger(__name__)


@dataclass
class RepairSession:
    """Complete record of one repair run."""
    issue_number: int
    target_file: str
    function_name: str
    attempts: List[AttemptRecord] = field(default_factory=list)
    final_status: str = "PENDING"    # "PASS" | "FAIL" | "EXHAUSTED"
    total_attempts: int = 0
    winning_diff: str = ""
    winning_explanation: str = ""

    def succeeded(self) -> bool:
        return self.final_status == "PASS"

    def summary(self) -> str:
        lines = [
            f"Repair session for issue #{self.issue_number}",
            f"Target: {self.target_file}::{self.function_name}()",
            f"Attempts: {self.total_attempts}",
            f"Final status: {self.final_status}",
        ]
        for i, attempt in enumerate(self.attempts, 1):
            icon = "✅" if attempt.passed else "❌"
            lines.append(f"  Attempt {i}: {icon} {attempt.failure_type or 'passed'}")
        return "\n".join(lines)


class RepairAgent:
    """
    Autonomous agent that iteratively repairs a bug until tests pass.

    Args:
        model_client:  LLM client with .generate(prompt) -> str
        repo_path:     Path to the cloned repository
        max_attempts:  Maximum repair iterations (default 5)
        use_sandbox:   If True, run tests in Docker (requires docker_runner)
    """

    def __init__(
        self,
        model_client,
        repo_path: Path,
        max_attempts: int = 5,
        use_sandbox: bool = False,
    ):
        self.model = model_client
        self.repo_path = repo_path
        self.max_attempts = max_attempts
        self.use_sandbox = use_sandbox

        self.patch_generator = PatchGenerator(model_client, max_retries=1)
        self.applier = PatchApplier(repo_path)
        self.validator = Validator()
        self.failure_analyzer = FailureAnalyzer(model_client)
        self.retry_manager = RetryManager(max_attempts=max_attempts)

    def repair(self, issue, location, index: dict) -> RepairSession:
        """
        Run the iterative repair loop.

        Args:
            issue:    GitHubIssue dataclass.
            location: FunctionLocation — the bug site.
            index:    RepoIndex from RepositoryIndexer.

        Returns:
            RepairSession with all attempt records and final outcome.
        """
        session = RepairSession(
            issue_number=issue.number,
            target_file=location.file,
            function_name=location.function,
        )

        # Track the original file content so we can revert between attempts
        original_content = self._read_file(location.file, index)
        feedback: Optional[str] = None
        previous_analysis: Optional[FailureAnalysis] = None

        logger.info(
            "RepairAgent starting for issue #%d — %s::%s() — max %d attempts",
            issue.number, location.file, location.function, self.max_attempts,
        )

        for attempt_num in range(1, self.max_attempts + 1):
            logger.info("--- Attempt %d/%d ---", attempt_num, self.max_attempts)
            print(f"\n  [Repair] Attempt {attempt_num}/{self.max_attempts}...", flush=True)

            # 1. Revert file to original before each attempt
            self._revert_file(location.file, index, original_content)

            # 2. Generate patch (with failure feedback from previous attempt)
            patch_result = self.patch_generator.generate(
                issue, location, index,
                # Inject failure context into the prompt
                extra_context=self._build_feedback_context(feedback, previous_analysis),
            )

            if not patch_result.validation_passed:
                record = self.retry_manager.record_attempt(
                    attempt_num=attempt_num,
                    diff=patch_result.diff,
                    passed=False,
                    failure_type="invalid_diff",
                    failure_detail="Diff validator rejected the patch.",
                    analysis=None,
                )
                session.attempts.append(record)
                feedback = "The generated diff was structurally invalid. Ensure it follows unified diff format."
                continue

            # 3. Apply patch
            apply_result = self.applier.apply(patch_result.diff, dry_run=False)
            if not apply_result.success:
                record = self.retry_manager.record_attempt(
                    attempt_num=attempt_num,
                    diff=patch_result.diff,
                    passed=False,
                    failure_type="apply_failed",
                    failure_detail=apply_result.stderr,
                    analysis=None,
                )
                session.attempts.append(record)
                feedback = f"Patch failed to apply:\n{apply_result.stderr}"
                continue

            # 4. Run tests
            val_result = self.validator.validate(str(self.repo_path))
            passed = val_result["status"] == "PASS"

            if passed:
                record = self.retry_manager.record_attempt(
                    attempt_num=attempt_num,
                    diff=patch_result.diff,
                    passed=True,
                    failure_type=None,
                    failure_detail=None,
                    analysis=None,
                )
                session.attempts.append(record)
                session.final_status = "PASS"
                session.winning_diff = patch_result.diff
                session.winning_explanation = patch_result.explanation
                session.total_attempts = attempt_num
                print(f"  [Repair] ✅ Tests passed on attempt {attempt_num}!", flush=True)
                logger.info("RepairAgent succeeded on attempt %d.", attempt_num)
                return session

            # 5. Analyze failure for next iteration
            test_output = val_result.get("details", {}).get("stdout", "")
            analysis = self.failure_analyzer.analyze(test_output)
            record = self.retry_manager.record_attempt(
                attempt_num=attempt_num,
                diff=patch_result.diff,
                passed=False,
                failure_type=analysis.failure_type,
                failure_detail=analysis.root_cause,
                analysis=analysis,
            )
            session.attempts.append(record)
            previous_analysis = analysis
            feedback = self._build_repair_feedback(analysis, test_output)

            print(
                f"  [Repair] ❌ {analysis.failure_type}: {analysis.root_cause[:80]}",
                flush=True,
            )

        # All attempts exhausted
        self._revert_file(location.file, index, original_content)
        session.final_status = "EXHAUSTED"
        session.total_attempts = self.max_attempts
        logger.warning("RepairAgent exhausted all %d attempts.", self.max_attempts)
        return session

    # ── private ────────────────────────────────────────────────────────────

    def _read_file(self, rel_path: str, index: dict) -> str:
        abs_path = index.get(rel_path, {}).get("abs_path", "")
        if abs_path and Path(abs_path).exists():
            return Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        return ""

    def _revert_file(self, rel_path: str, index: dict, original: str) -> None:
        abs_path = index.get(rel_path, {}).get("abs_path", "")
        if abs_path and original:
            Path(abs_path).write_text(original, encoding="utf-8")

    def _build_feedback_context(
        self,
        feedback: Optional[str],
        analysis: Optional["FailureAnalysis"],
    ) -> str:
        if not feedback:
            return ""
        parts = [f"## Previous Attempt Failed\n{feedback}"]
        if analysis and analysis.suggested_fix:
            parts.append(f"\nSuggested direction: {analysis.suggested_fix}")
        return "\n".join(parts)

    def _build_repair_feedback(self, analysis: "FailureAnalysis", raw_output: str) -> str:
        return (
            f"Test suite failed with {analysis.failure_type}.\n"
            f"Root cause: {analysis.root_cause}\n"
            f"Failed tests: {', '.join(analysis.failed_tests[:5])}\n"
            f"Raw output (truncated):\n{raw_output[:800]}"
        )
