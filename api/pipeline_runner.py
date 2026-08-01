"""
Runs the full pipeline in a background thread and tracks step progress.
The frontend polls /api/run/{id} to get live updates.
"""

import logging
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Each step the frontend will display
STEPS = [
    "repository_analysis",
    "issue_analysis",
    "semantic_retrieval",
    "bug_localization",
    "patch_generation",
    "validation",
    "pr_generation",
]


@dataclass
class StepStatus:
    name: str
    status: str = "pending"   # pending | running | done | failed
    detail: str = ""


@dataclass
class PipelineStatus:
    run_id: str
    overall: str = "pending"   # pending | running | done | failed
    steps: List[StepStatus] = field(default_factory=list)
    error: str = ""


class PipelineRunner:
    """Runs the pipeline and exposes status for the API to serve."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._steps = {name: StepStatus(name=name) for name in STEPS}
        self._overall = "pending"
        self._error = ""
        self._result: Dict[str, Any] = {}

    def status(self) -> dict:
        return {
            "run_id": self.run_id,
            "overall": self._overall,
            "steps": [
                {"name": s.name, "status": s.status, "detail": s.detail}
                for s in self._steps.values()
            ],
            "error": self._error,
        }

    def result(self) -> dict:
        return self._result

    def is_done(self) -> bool:
        return self._overall in ("done", "failed")

    async def run(self, req):
        """Main pipeline coroutine — called by FastAPI background task."""
        self._overall = "running"
        try:
            await self._execute(req)
            self._overall = "done"
        except Exception as exc:
            self._error = str(exc)
            self._overall = "failed"
            logger.error("Pipeline run %s failed: %s", self.run_id, traceback.format_exc())

    # ── private ────────────────────────────────────────────────────────────

    def _step_start(self, name: str, detail: str = ""):
        self._steps[name].status = "running"
        self._steps[name].detail = detail

    def _step_done(self, name: str, detail: str = ""):
        self._steps[name].status = "done"
        self._steps[name].detail = detail

    def _step_fail(self, name: str, detail: str = ""):
        self._steps[name].status = "failed"
        self._steps[name].detail = detail

    async def _execute(self, req):
        import asyncio
        from utils.config import load_config
        from utils.llm_client import get_llm_client
        from repository_analysis import RepoLoader, RepositoryIndexer
        from issue_analysis import IssueFetcher
        from bug_localization import BugLocalizer, FunctionLocalizer
        from fix_generation import PatchGenerator, PatchApplier
        from retrieval import RetrievalPipeline
        from validation.validator import Validator
        from validation.failure_analyzer import FailureAnalyzer
        from pr_generator import PRSummaryGenerator, MarkdownGenerator
        from memory import RepositoryCache

        cfg = load_config()
        cfg["llm"]["api_key"] = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
        github_token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
        llm = get_llm_client(cfg["llm"])
        cache = RepositoryCache()

        # 1. Repository analysis
        self._step_start("repository_analysis", "Cloning repository...")
        repo_path = await asyncio.to_thread(
            RepoLoader(cfg["repo"]["base_dir"]).load, req.repo_url
        )

        indexer = RepositoryIndexer(repo_path)
        if cache.is_valid(repo_path):
            cached = cache.load(repo_path)
            index = cached.index
            dep_graph = cache.restore_dep_graph(cached)
        else:
            index = await asyncio.to_thread(indexer.build)
            dep_graph = indexer.dependency_graph
            await asyncio.to_thread(cache.save, repo_path, index, dep_graph)

        self._step_done("repository_analysis", f"{len(index)} files indexed")

        # 2. Issue analysis
        self._step_start("issue_analysis", f"Fetching issue #{req.issue_number}...")
        issue = await asyncio.to_thread(
            IssueFetcher(token=github_token).fetch,
            req.owner, req.repo_name, req.issue_number
        )
        self._step_done("issue_analysis", issue.title[:80])

        # 3. Semantic retrieval
        self._step_start("semantic_retrieval", "Building FAISS index...")
        retrieval = RetrievalPipeline(
            cache_dir=cfg["retrieval"]["cache_dir"],
            model_name=cfg["retrieval"]["model"],
            device=cfg["retrieval"]["device"],
        )
        await asyncio.to_thread(retrieval.build, index, repo_path)
        ranked = await asyncio.to_thread(retrieval.get_ranker().rank_to_tuples, issue)
        top_files = [f for f, _ in ranked[:5]]
        self._step_done("semantic_retrieval", f"Top: {top_files[0] if top_files else 'none'}")

        # 4. Bug localization
        self._step_start("bug_localization", "Localizing bug...")
        localization = await asyncio.to_thread(
            BugLocalizer(cfg["bug_localization"]["top_n"]).localize,
            ranked, dep_graph, index
        )
        fn_locations = await asyncio.to_thread(
            FunctionLocalizer(llm).localize, issue, localization, index
        )
        top_fn = fn_locations[0] if fn_locations else None
        detail = f"{top_fn.file}::{top_fn.function}() [{top_fn.confidence}]" if top_fn else "no function found"
        self._step_done("bug_localization", detail)

        # 5. Patch generation
        self._step_start("patch_generation", "Generating unified diff...")
        patch_result = None
        if top_fn:
            patch_result = await asyncio.to_thread(
                PatchGenerator(llm).generate, issue, top_fn, index
            )
        self._step_done(
            "patch_generation",
            f"Valid: {patch_result.validation_passed}" if patch_result else "skipped"
        )

        # 6. Validation
        self._step_start("validation", "Running tests...")
        val_result = {"status": "SKIP", "message": "No patch generated.", "details": {}}
        if patch_result and patch_result.validation_passed:
            applier = PatchApplier(repo_path)
            apply = await asyncio.to_thread(applier.apply, patch_result.diff, not req.apply_patch)
            if apply.success and req.apply_patch:
                val_result = await asyncio.to_thread(Validator().validate, str(repo_path))
            else:
                val_result = {"status": "PASS" if apply.success else "FAIL", "message": "Dry-run", "details": {}}
        self._step_done("validation", val_result.get("status", "SKIP"))

        # 7. PR generation
        self._step_start("pr_generation", "Writing PR description...")
        pr_md = ""
        if patch_result and top_fn:
            summary = PRSummaryGenerator().generate(
                issue_title=issue.title,
                issue_description=issue.body[:400],
                files_changed=[top_fn.file],
                patch_summary=f"Fixed `{top_fn.function}()` in `{top_fn.file}`

{patch_result.explanation}",
                validation_result=val_result,
            )
            pr_md = MarkdownGenerator().generate(summary)
        self._step_done("pr_generation", "Done")

        self._result = {
            "issue_title": issue.title,
            "suspect_files": [f for f, _ in ranked[:5]],
            "function_location": {
                "file": top_fn.file,
                "function": top_fn.function,
                "confidence": top_fn.confidence,
                "reason": top_fn.reason,
            } if top_fn else None,
            "patch": {
                "diff": patch_result.diff if patch_result else "",
                "explanation": patch_result.explanation if patch_result else "",
                "valid": patch_result.validation_passed if patch_result else False,
                "attempts": patch_result.attempts if patch_result else 0,
            },
            "validation": val_result,
            "pr_markdown": pr_md,
        }
