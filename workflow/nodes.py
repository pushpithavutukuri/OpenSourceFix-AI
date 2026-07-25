"""
workflow/nodes.py  —  LangGraph node implementations.

All nodes now call real pipeline modules.
Stubs are fully replaced for Week 2.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def repository_node(state):
    """Clone/update repo, build index + FAISS retrieval index."""
    print("\n[Node 1/7] Repository Analysis...")
    from repository_analysis import RepoLoader, RepositoryIndexer
    from retrieval import RetrievalPipeline
    from utils.config import load_config

    cfg = load_config()
    repo_path = RepoLoader(cfg["repo"]["base_dir"]).load(state["repo_url"])
    indexer = RepositoryIndexer(repo_path)
    index = indexer.build()

    retrieval = RetrievalPipeline(
        cache_dir=cfg["retrieval"]["cache_dir"],
        model_name=cfg["retrieval"]["model"],
        device=cfg["retrieval"]["device"],
    )
    retrieval.build(index, repo_path)

    state["repo_path"] = str(repo_path)
    state["repo_metadata"] = {
        "index": index,
        "dep_graph": indexer.dependency_graph,
        "retrieval": retrieval,
    }
    print(f"   {len(index)} files indexed.")
    return state


def issue_node(state):
    """Fetch GitHub issue and extract keywords."""
    print("[Node 2/7] Issue Analysis...")
    from issue_analysis import IssueFetcher, KeywordExtractor
    from utils.config import load_config

    cfg = load_config()
    token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
    issue = IssueFetcher(token=token).fetch(
        state["issue_owner"], state["issue_repo"], state["issue_number"]
    )
    keywords = KeywordExtractor().extract(issue)
    state["parsed_issue"] = {"issue_obj": issue, "keywords": keywords}
    print(f"   Issue: {issue.title}")
    return state


def retrieval_node(state):
    """Semantic file ranking via BGE + FAISS."""
    print("[Node 3/7] Semantic Retrieval...")
    issue = state["parsed_issue"]["issue_obj"]
    ranker = state["repo_metadata"]["retrieval"].get_ranker()
    ranked = ranker.rank_to_tuples(issue)
    state["retrieved_files"] = ranked
    print(f"   Top file: {ranked[0][0] if ranked else 'none'}")
    return state


def localization_node(state):
    """File-level + function-level bug localization."""
    print("[Node 4/7] Bug Localization...")
    from bug_localization import BugLocalizer, FunctionLocalizer
    from utils.config import load_config
    from utils.llm_client import get_llm_client

    cfg = load_config()
    cfg["llm"]["api_key"] = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
    llm = get_llm_client(cfg["llm"])

    index = state["repo_metadata"]["index"]
    dep_graph = state["repo_metadata"]["dep_graph"]
    issue = state["parsed_issue"]["issue_obj"]

    localization = BugLocalizer(cfg["bug_localization"]["top_n"]).localize(
        state["retrieved_files"], dep_graph, index
    )
    fn_locations = FunctionLocalizer(llm).localize(issue, localization, index)

    state["suspect_files"] = [(f, s) for f, s in state["retrieved_files"][:cfg["bug_localization"]["top_n"]]]
    state["function_locations"] = fn_locations

    if fn_locations:
        top = fn_locations[0]
        print(f"   Top suspect: {top.file}::{top.function}() [{top.confidence}]")
    return state


def fix_generation_node(state):
    """Generate a real unified diff patch."""
    print("[Node 5/7] Generating Patch (unified diff)...")
    from fix_generation import PatchGenerator, PatchApplier
    from utils.config import load_config
    from utils.llm_client import get_llm_client

    cfg = load_config()
    cfg["llm"]["api_key"] = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
    llm = get_llm_client(cfg["llm"])

    issue = state["parsed_issue"]["issue_obj"]
    index = state["repo_metadata"]["index"]
    fn_locations = state.get("function_locations", [])

    if not fn_locations:
        print("   No function locations — skipping patch generation.")
        state["patch"] = {"diff": "", "explanation": "No function located.", "valid": False}
        return state

    top_location = fn_locations[0]
    patch_result = PatchGenerator(llm).generate(issue, top_location, index)

    # Dry-run: verify patch applies cleanly without touching files
    apply_result = PatchApplier(Path(state["repo_path"])).apply(patch_result.diff, dry_run=True)

    state["patch"] = {
        "diff": patch_result.diff,
        "explanation": patch_result.explanation,
        "target_file": patch_result.target_file,
        "function_name": patch_result.function_name,
        "valid": patch_result.validation_passed,
        "applies_cleanly": apply_result.success,
        "attempts": patch_result.attempts,
    }

    status = "✓ valid + applies cleanly" if (patch_result.validation_passed and apply_result.success) else "⚠ issues found"
    print(f"   Patch {status} (attempt {patch_result.attempts})")
    return state


def validation_node(state):
    """Apply the patch for real and run the test suite."""
    print("[Node 6/7] Validation...")
    from validation.validator import Validator
    from fix_generation import PatchApplier

    patch = state.get("patch", {})
    repo_path = state["repo_path"]

    if not patch.get("valid") or not patch.get("applies_cleanly"):
        print("   Skipping test run — patch did not validate.")
        state["validation"] = {"status": "SKIP", "message": "Patch validation failed.", "details": {}}
        return state

    apply_result = PatchApplier(Path(repo_path)).apply(patch["diff"], dry_run=False)
    if not apply_result.success:
        state["validation"] = {"status": "FAIL", "message": "Patch failed to apply.", "details": {"stderr": apply_result.stderr}}
        return state

    state["validation"] = Validator().validate(repo_path)
    print(f"   Tests: {state['validation']['status']}")
    return state


def pr_node(state):
    """Generate PR summary and GitHub markdown."""
    print("[Node 7/7] Generating PR Summary...")
    from pr_generator import PRSummaryGenerator, MarkdownGenerator

    issue = state["parsed_issue"]["issue_obj"]
    patch = state.get("patch", {})
    validation = state.get("validation", {"status": "SKIP"})

    files_changed = [patch["target_file"]] if patch.get("target_file") else [
        f for f, _ in state.get("suspect_files", [])[:3]
    ]

    patch_summary = (
        f"Fixed `{patch.get('function_name', 'unknown')}()` in `{patch.get('target_file', 'unknown')}`\n\n"
        f"{patch.get('explanation', '')}\n\n"
        f"```diff\n{patch.get('diff', '')[:1500]}\n```"
    ) if patch.get("diff") else "No patch generated."

    summary = PRSummaryGenerator().generate(
        issue_title=issue.title,
        issue_description=issue.body[:400],
        files_changed=files_changed,
        patch_summary=patch_summary,
        validation_result=validation,
    )
    state["pr_summary"] = MarkdownGenerator().generate(summary)
    print("\n" + "="*60)
    print(state["pr_summary"][:600])
    print("="*60)
    return state
