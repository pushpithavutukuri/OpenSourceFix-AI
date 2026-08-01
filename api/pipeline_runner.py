"""
Runs the pipeline in a background task and tracks per-step status.
The frontend polls /api/run/{id} every 1.5s to get updates.
"""

import asyncio
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STEPS = [
    "repository_analysis",
    "issue_analysis",
    "semantic_retrieval",
    "bug_localization",
    "patch_generation",
    "validation",
    "pr_generation",
]

# User-friendly messages for common failure modes
_FRIENDLY_ERRORS = {
    "401": "GitHub token is missing or invalid. Set GITHUB_TOKEN in your environment.",
    "404": "Repository or issue not found. Check the URL and issue number.",
    "403": "GitHub rate limit hit. Add a GITHUB_TOKEN to increase your limit.",
    "api_key": "LLM API key is missing. Set GEMINI_API_KEY in your environment.",
    "GEMINI_API_KEY": "LLM API key is missing. Set GEMINI_API_KEY in your environment.",
    "Connection": "Could not connect to the API. Check your internet connection.",
}


def _friendly(exc: Exception) -> str:
    msg = str(exc)
    for key, friendly in _FRIENDLY_ERRORS.items():
        if key in msg:
            return friendly
    # Don't expose full tracebacks to the frontend
    return msg.split("\n")[0][:200]


@dataclass
class StepStatus:
    name: str
    status: str = "pending"   # pending | running | done | failed
    detail: str = ""
    elapsed: float = 0.0


class PipelineRunner:
    """Runs the pipeline and tracks step progress for the API."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._steps: Dict[str, StepStatus] = {n: StepStatus(name=n) for n in STEPS}
        self._overall = "pending"
        self._error = ""
        self._result: Dict[str, Any] = {}
        self._started_at = time.time()

    def status(self) -> dict:
        return {
            "run_id":  self.run_id,
            "overall": self._overall,
            "elapsed": round(time.time() - self._started_at, 1),
            "steps": [
                {
                    "name":    s.name,
                    "status":  s.status,
                    "detail":  s.detail,
                    "elapsed": round(s.elapsed, 1),
                }
                for s in self._steps.values()
            ],
            "error": self._error,
        }

    def result(self) -> dict:
        return self._result

    def is_done(self) -> bool:
        return self._overall in ("done", "failed")

    async def run(self, req) -> None:
        self._overall = "running"
        try:
            await self._execute(req)
            self._overall = "done"
        except Exception as exc:
            self._error = _friendly(exc)
            self._overall = "failed"
            # Log the full traceback server-side, send only a clean message to the client
            logger.error("Run %s failed:\n%s", self.run_id, traceback.format_exc())

    # ── step helpers ───────────────────────────────────────────────────────

    def _start(self, name: str, detail: str = "") -> float:
        self._steps[name].status = "running"
        self._steps[name].detail = detail
        logger.info("[%s] %s — %s", self.run_id, name, detail)
        return time.time()

    def _done(self, name: str, t0: float, detail: str = "") -> None:
        elapsed = time.time() - t0
        self._steps[name].status = "done"
        self._steps[name].detail = detail
        self._steps[name].elapsed = elapsed
        logger.info("[%s] %s done (%.1fs) — %s", self.run_id, name, elapsed, detail)

    def _fail(self, name: str, t0: float, exc: Exception) -> None:
        elapsed = time.time() - t0
        detail = _friendly(exc)
        self._steps[name].status = "failed"
        self._steps[name].detail = detail
        self._steps[name].elapsed = elapsed
        logger.warning("[%s] %s failed (%.1fs) — %s", self.run_id, name, elapsed, detail)

    # ── pipeline ───────────────────────────────────────────────────────────

    async def _execute(self, req) -> None:
        from utils.config import load_config
        from utils.llm_client import get_llm_client
        from repository_analysis import RepoLoader, RepositoryIndexer
        from issue_analysis import IssueFetcher
        from bug_localization import BugLocalizer, FunctionLocalizer
        from fix_generation import PatchGenerator, PatchApplier
        from retrieval import RetrievalPipeline
        from validation.validator import Validator
        from pr_generator import PRSummaryGenerator, MarkdownGenerator
        from memory import RepositoryCache

        cfg = load_config()

        api_key = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        cfg["llm"]["api_key"] = api_key
        github_token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
        llm = get_llm_client(cfg["llm"])
        cache = RepositoryCache()

        # 1. Repository analysis
        t = self._start("repository_analysis", "Cloning repository...")
        try:
            repo_path = await asyncio.to_thread(
                RepoLoader(cfg["repo"]["base_dir"]).load, req.repo_url
            )
            indexer = RepositoryIndexer(repo_path)
            if cache.is_valid(repo_path):
                cached = cache.load(repo_path)
                index = cached.index
                dep_graph = cache.restore_dep_graph(cached)
                self._done("repository_analysis", t, f"{len(index)} files (from cache)")
            else:
                self._steps["repository_analysis"].detail = "Scanning and parsing files..."
                index = await asyncio.to_thread(indexer.build)
                dep_graph = indexer.dependency_graph
                await asyncio.to_thread(cache.save, repo_path, index, dep_graph)
                self._done("repository_analysis", t, f"{len(index)} files indexed")
        except Exception as exc:
            self._fail("repository_analysis", t, exc)
            raise

        # 2. Issue analysis
        t = self._start("issue_analysis", f"Fetching issue #{req.issue_number}...")
        try:
            issue = await asyncio.to_thread(
                IssueFetcher(token=github_token).fetch,
                req.owner, req.repo_name, req.issue_number,
            )
            self._done("issue_analysis", t, issue.title[:80])
        except Exception as exc:
            self._fail("issue_analysis", t, exc)
            raise

        # 3. Semantic retrieval
        t = self._start("semantic_retrieval", "Building embedding index...")
        try:
            retrieval = RetrievalPipeline(
                cache_dir=cfg["retrieval"]["cache_dir"],
                model_name=cfg["retrieval"]["model"],
                device=cfg["retrieval"]["device"],
            )
            await asyncio.to_thread(retrieval.build, index, repo_path)
            ranked = await asyncio.to_thread(retrieval.get_ranker().rank_to_tuples, issue)
            top_file = ranked[0][0] if ranked else "none"
            self._done("semantic_retrieval", t, f"Top: {top_file}")
        except Exception as exc:
            self._fail("semantic_retrieval", t, exc)
            raise

        # 4. Bug localization
        t = self._start("bug_localization", "Finding suspect files...")
        try:
            localization = await asyncio.to_thread(
                BugLocalizer(cfg["bug_localization"]["top_n"]).localize,
                ranked, dep_graph, index,
            )
            self._steps["bug_localization"].detail = "Identifying function..."
            fn_locations = await asyncio.to_thread(
                FunctionLocalizer(llm).localize, issue, localization, index,
            )
            top_fn = fn_locations[0] if fn_locations else None
            detail = (
                f"{top_fn.file}::{top_fn.function}() [{top_fn.confidence}]"
                if top_fn else "no function identified"
            )
            self._done("bug_localization", t, detail)
        except Exception as exc:
            self._fail("bug_localization", t, exc)
            raise

        # 5. Patch generation
        t = self._start("patch_generation", "Generating unified diff...")
        patch_result = None
        try:
            if top_fn:
                patch_result = await asyncio.to_thread(
                    PatchGenerator(llm).generate, issue, top_fn, index,
                )
                status_str = "valid" if patch_result.validation_passed else "invalid diff"
                self._done("patch_generation", t, f"{status_str} — {patch_result.attempts} attempt(s)")
            else:
                self._done("patch_generation", t, "skipped — no function located")
        except Exception as exc:
            self._fail("patch_generation", t, exc)
            raise

        # 6. Validation
        t = self._start("validation", "Checking patch...")
        val_result = {"status": "SKIP", "message": "No patch to validate.", "details": {}}
        try:
            if patch_result and patch_result.validation_passed:
                applier = PatchApplier(repo_path)
                apply = await asyncio.to_thread(applier.apply, patch_result.diff, True)
                if not apply.success:
                    val_result = {
                        "status": "FAIL",
                        "message": "Patch did not apply cleanly.",
                        "details": {"stderr": apply.stderr},
                    }
                elif req.apply_patch:
                    await asyncio.to_thread(applier.apply, patch_result.diff, False)
                    self._steps["validation"].detail = "Running tests..."
                    val_result = await asyncio.to_thread(Validator().validate, str(repo_path))
                else:
                    val_result = {
                        "status": "PASS",
                        "message": "Patch applies cleanly (dry-run).",
                        "details": {},
                    }
            self._done("validation", t, val_result["status"])
        except Exception as exc:
            self._fail("validation", t, exc)
            raise

        # 7. PR generation
        t = self._start("pr_generation", "Writing PR description...")
        pr_md = ""
        try:
            if patch_result and top_fn:
                summary = PRSummaryGenerator().generate(
                    issue_title=issue.title,
                    issue_description=issue.body[:400],
                    files_changed=[top_fn.file],
                    patch_summary=(
                        f"Fixed `{top_fn.function}()` in `{top_fn.file}`\n\n"
                        f"{patch_result.explanation}"
                    ),
                    validation_result=val_result,
                )
                pr_md = MarkdownGenerator().generate(summary)
            self._done("pr_generation", t, "done")
        except Exception as exc:
            self._fail("pr_generation", t, exc)
            raise

        self._result = {
            "issue_title":  issue.title,
            "issue_body":   issue.body[:600],
            "suspect_files": [
                {"path": path, "score": round(score, 3)}
                for path, score in ranked[:8]
            ],
            "function_location": {
                "file":       top_fn.file,
                "function":   top_fn.function,
                "start_line": top_fn.start_line,
                "end_line":   top_fn.end_line,
                "confidence": top_fn.confidence,
                "reason":     top_fn.reason,
            } if top_fn else None,
            "patch": {
                "diff":        patch_result.diff if patch_result else "",
                "explanation": patch_result.explanation if patch_result else "",
                "valid":       patch_result.validation_passed if patch_result else False,
                "attempts":    patch_result.attempts if patch_result else 0,
            },
            "validation": val_result,
            "pr_markdown": pr_md,
        }
