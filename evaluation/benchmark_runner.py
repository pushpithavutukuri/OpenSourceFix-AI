"""
benchmark_runner.py

Runs the full pipeline end-to-end on a set of benchmark issues
and feeds the results into the Evaluator.

This is what you run before a demo or interview to get real numbers:

    python -m evaluation.benchmark_runner --benchmark data/benchmark.json

Benchmark file format (JSON)
-----------------------------
[
    {
        "repo_url":         "https://github.com/pallets/flask",
        "owner":            "pallets",
        "repo_name":        "flask",
        "issue_number":     1234,
        "correct_file":     "src/flask/sessions.py",
        "correct_function": "open_session"
    }
]

Output
------
Prints the EvaluationReport summary and saves full results to
evaluation/results/<timestamp>.json
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from evaluation.evaluator import Evaluator, EvaluationReport

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Runs the pipeline on a list of benchmark cases and evaluates the results.

    Each benchmark case is one GitHub issue with a known correct answer.
    The runner handles exceptions per-case so one failure does not abort the
    entire benchmark.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path

    def run(self, benchmark_cases: List[dict]) -> EvaluationReport:
        """
        Run all benchmark cases and return an EvaluationReport.

        Args:
            benchmark_cases: List of dicts from the benchmark JSON file.

        Returns:
            EvaluationReport with metrics across all cases.
        """
        from utils.config import load_config
        from utils.logger import setup_logging
        from utils.llm_client import get_llm_client
        from repository_analysis import RepoLoader, RepositoryIndexer
        from issue_analysis import IssueFetcher
        from bug_localization import BugLocalizer, FunctionLocalizer
        from retrieval import RetrievalPipeline

        cfg = load_config(self.config_path)
        setup_logging(cfg["logging"]["level"])
        cfg["llm"]["api_key"] = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
        github_token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
        llm = get_llm_client(cfg["llm"])

        pipeline_results = []
        ground_truth = []

        for i, case in enumerate(benchmark_cases):
            issue_num = case["issue_number"]
            print(f"\n[{i+1}/{len(benchmark_cases)}] Issue #{issue_num}: {case.get('repo_name', '')}...")

            ground_truth.append({
                "issue_number":    issue_num,
                "correct_file":    case.get("correct_file", ""),
                "correct_function": case.get("correct_function", ""),
            })

            try:
                result = self._run_single(case, cfg, github_token, llm)
                pipeline_results.append(result)
                print(f"   Top file: {result['ranked_files'][0] if result['ranked_files'] else 'none'}")
                print(f"   Function: {result['predicted_function'] or 'not found'}")
            except Exception as exc:
                logger.error("Case #%d failed: %s", issue_num, exc)
                pipeline_results.append({
                    "issue_number": issue_num,
                    "ranked_files": [],
                    "predicted_function": "",
                    "patch_passed_tests": None,
                })

        report = Evaluator().evaluate(pipeline_results, ground_truth)
        print(report.summary())
        self._save_results(pipeline_results, ground_truth, report)
        return report

    # ── private ────────────────────────────────────────────────────────────

    def _run_single(self, case: dict, cfg: dict, github_token: str, llm) -> dict:
        from repository_analysis import RepoLoader, RepositoryIndexer
        from issue_analysis import IssueFetcher
        from bug_localization import BugLocalizer, FunctionLocalizer
        from retrieval import RetrievalPipeline

        # Clone + index
        repo_path = RepoLoader(cfg["repo"]["base_dir"]).load(case["repo_url"])
        indexer = RepositoryIndexer(repo_path)
        index = indexer.build()

        # Fetch issue
        issue = IssueFetcher(token=github_token).fetch(
            case["owner"], case["repo_name"], case["issue_number"]
        )

        # Semantic retrieval
        retrieval = RetrievalPipeline(
            cache_dir=cfg["retrieval"]["cache_dir"],
            model_name=cfg["retrieval"]["model"],
            device=cfg["retrieval"]["device"],
        )
        retrieval.build(index, repo_path)
        ranked = retrieval.get_ranker().rank_to_tuples(issue)

        # File-level localization
        localization = BugLocalizer(cfg["bug_localization"]["top_n"]).localize(
            ranked, indexer.dependency_graph, index
        )

        # Function-level localization
        fn_locations = FunctionLocalizer(llm).localize(issue, localization, index)
        predicted_fn = fn_locations[0].function if fn_locations else ""

        return {
            "issue_number":       case["issue_number"],
            "ranked_files":       [f for f, _ in ranked],
            "predicted_function": predicted_fn,
            "patch_passed_tests": None,   # patch not run in benchmark mode
        }

    def _save_results(self, pipeline_results, ground_truth, report: EvaluationReport):
        output_dir = Path("evaluation/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"benchmark_{timestamp}.json"
        output = {
            "timestamp": timestamp,
            "metrics": report.to_dict(),
            "pipeline_results": pipeline_results,
            "ground_truth": ground_truth,
        }
        output_path.write_text(json.dumps(output, indent=2))
        print(f"\nFull results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run OpenSourceFix AI benchmark")
    parser.add_argument("--benchmark", required=True, help="Path to benchmark JSON file")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cases = json.loads(Path(args.benchmark).read_text())
    runner = BenchmarkRunner(config_path=args.config)
    runner.run(cases)


if __name__ == "__main__":
    main()
