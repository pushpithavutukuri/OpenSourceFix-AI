"""
evaluator.py

Measures how well the pipeline performs on known bugs.

This is the metric that matters at Google-level:
    "Given a GitHub issue, did we find the right file?"
    "Did our patch make the tests pass?"

Metrics
-------
file_hit_rate_at_1   : Was the correct file the #1 ranked result?
file_hit_rate_at_5   : Was the correct file in the top 5?
function_hit_rate    : Did we identify the correct function?
patch_pass_rate      : Did the generated patch make all tests pass?

These map directly to SWE-bench evaluation criteria, so you can
compare your numbers against published baselines.

Usage
-----
ground_truth = [
    {
        "issue_number": 1234,
        "correct_file": "auth/session.py",
        "correct_function": "refresh_token",
    }
]
evaluator = Evaluator()
report = evaluator.evaluate(pipeline_results, ground_truth)
print(report.summary())
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SingleResult:
    issue_number: int
    correct_file: str
    correct_function: str

    # What the pipeline produced
    ranked_files: List[str] = field(default_factory=list)
    predicted_function: str = ""
    patch_passed_tests: Optional[bool] = None

    # Computed metrics
    hit_at_1: bool = False
    hit_at_5: bool = False
    function_correct: bool = False


@dataclass
class EvaluationReport:
    results: List[SingleResult]
    total: int = 0
    hit_at_1: int = 0
    hit_at_5: int = 0
    function_hits: int = 0
    patch_passes: int = 0
    patch_total: int = 0   # issues where patch generation was attempted

    def summary(self) -> str:
        if self.total == 0:
            return "No results to evaluate."

        lines = [
            "",
            "=" * 50,
            "  OpenSourceFix AI — Evaluation Report",
            "=" * 50,
            f"  Issues evaluated    : {self.total}",
            f"  File Hit@1          : {self.hit_at_1}/{self.total} = {100*self.hit_at_1/self.total:.1f}%",
            f"  File Hit@5          : {self.hit_at_5}/{self.total} = {100*self.hit_at_5/self.total:.1f}%",
            f"  Function Hit Rate   : {self.function_hits}/{self.total} = {100*self.function_hits/self.total:.1f}%",
        ]
        if self.patch_total > 0:
            lines.append(f"  Patch Pass Rate     : {self.patch_passes}/{self.patch_total} = {100*self.patch_passes/self.patch_total:.1f}%")
        lines.append("=" * 50)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "file_hit_at_1": self.hit_at_1 / self.total if self.total else 0,
            "file_hit_at_5": self.hit_at_5 / self.total if self.total else 0,
            "function_hit_rate": self.function_hits / self.total if self.total else 0,
            "patch_pass_rate": self.patch_passes / self.patch_total if self.patch_total else None,
        }


class Evaluator:
    """
    Computes evaluation metrics by comparing pipeline output against ground truth.

    This class is intentionally stateless — pass in results and ground truth,
    get back a report. Easy to run in CI.
    """

    def evaluate(
        self,
        pipeline_results: List[dict],
        ground_truth: List[dict],
    ) -> EvaluationReport:
        """
        Compute evaluation metrics.

        Args:
            pipeline_results: List of dicts, each with:
                {
                    "issue_number":       int,
                    "ranked_files":       [str, ...],        # ordered by score
                    "predicted_function": str,               # optional
                    "patch_passed_tests": bool | None,       # optional
                }

            ground_truth: List of dicts, each with:
                {
                    "issue_number":    int,
                    "correct_file":    str,    # relative path as in repo index
                    "correct_function": str,   # optional
                }

        Returns:
            EvaluationReport with computed metrics.
        """
        # Index ground truth by issue number for fast lookup
        gt_map: Dict[int, dict] = {g["issue_number"]: g for g in ground_truth}

        report = EvaluationReport(results=[])

        for pr in pipeline_results:
            issue_num = pr["issue_number"]
            gt = gt_map.get(issue_num)
            if not gt:
                logger.warning("No ground truth for issue #%d — skipping.", issue_num)
                continue

            correct_file = gt.get("correct_file", "")
            correct_fn   = gt.get("correct_function", "")
            ranked       = pr.get("ranked_files", [])
            pred_fn      = pr.get("predicted_function", "")
            patch_passed = pr.get("patch_passed_tests")

            # Normalize paths for comparison (handle OS separators)
            def norm(p): return p.replace("\\", "/").strip()

            hit1 = len(ranked) >= 1 and norm(ranked[0]) == norm(correct_file)
            hit5 = any(norm(r) == norm(correct_file) for r in ranked[:5])
            fn_correct = bool(correct_fn) and norm(pred_fn) == norm(correct_fn)

            result = SingleResult(
                issue_number=issue_num,
                correct_file=correct_file,
                correct_function=correct_fn,
                ranked_files=ranked,
                predicted_function=pred_fn,
                patch_passed_tests=patch_passed,
                hit_at_1=hit1,
                hit_at_5=hit5,
                function_correct=fn_correct,
            )
            report.results.append(result)
            report.total += 1
            if hit1: report.hit_at_1 += 1
            if hit5: report.hit_at_5 += 1
            if fn_correct: report.function_hits += 1
            if patch_passed is not None:
                report.patch_total += 1
                if patch_passed: report.patch_passes += 1

        logger.info("Evaluation complete: %s", report.summary())
        return report
