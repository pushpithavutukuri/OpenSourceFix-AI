"""
main.py  —  OpenSourceFix AI pipeline entry point (Week 2).

Usage:
    python main.py \
        --repo  https://github.com/YOU/repo \
        --owner YOU \
        --repo-name repo \
        --issue 1
"""

import argparse
import os

from utils.logger import setup_logging
from utils.config import load_config
from utils.llm_client import get_llm_client

from repository_analysis import RepoLoader, RepositoryIndexer
from issue_analysis import IssueFetcher
from bug_localization import BugLocalizer, FunctionLocalizer
from fix_generation import PatchGenerator, PatchApplier
from fix_generation.fix_generator import FixGenerator
from retrieval import RetrievalPipeline
from pr_generator import PRSummaryGenerator, MarkdownGenerator
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="OpenSourceFix AI")
    p.add_argument("--repo",      required=True)
    p.add_argument("--owner",     required=True)
    p.add_argument("--repo-name", required=True)
    p.add_argument("--issue",     required=True, type=int)
    p.add_argument("--config",    default="config/config.yaml")
    p.add_argument("--apply-patch", action="store_true",
                   help="Actually apply the patch to disk (default: dry-run only)")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    setup_logging(cfg["logging"]["level"], cfg["logging"]["log_file"])

    github_token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
    cfg["llm"]["api_key"] = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
    llm = get_llm_client(cfg["llm"])

    # 1. Clone repo
    print("\n[1/7] Loading repository...")
    repo_path = RepoLoader(cfg["repo"]["base_dir"]).load(args.repo)

    # 2. Index
    print("[2/7] Building repository index...")
    indexer = RepositoryIndexer(repo_path)
    index = indexer.build()
    print(f"      {len(index)} files indexed.")

    # 3. Fetch issue
    print(f"[3/7] Fetching issue #{args.issue}...")
    issue = IssueFetcher(token=github_token).fetch(args.owner, args.repo_name, args.issue)
    print(f"      {issue.title}")

    # 4. BGE + FAISS
    print("[4/7] Building semantic retrieval index...")
    retrieval = RetrievalPipeline(
        cache_dir=cfg["retrieval"]["cache_dir"],
        model_name=cfg["retrieval"]["model"],
        device=cfg["retrieval"]["device"],
    )
    retrieval.build(index, repo_path)
    stats = retrieval.stats()
    print(f"      {stats.get('total_chunks', 0)} chunks indexed.")

    # 5. File ranking + file-level localization
    print("[5/7] Ranking files and localizing bug...")
    ranked = retrieval.get_ranker().rank_to_tuples(issue)
    localization = BugLocalizer(cfg["bug_localization"]["top_n"]).localize(
        ranked, indexer.dependency_graph, index
    )
    print("\n  Primary suspect files:")
    for f in localization.primary_files:
        print(f"    [{localization.scores.get(f, 0):.3f}]  {f}")

    # 6. Function-level localization (NEW Week 2)
    print("\n[6/7] Function-level localization + patch generation...")
    fn_locations = FunctionLocalizer(llm).localize(issue, localization, index)

    if not fn_locations:
        print("  No function located. Falling back to prose fix generation.")
        proposal = FixGenerator(llm).generate(issue, localization, index)
        print("\n" + "="*70)
        print(proposal.proposed_fix)
        print("="*70)
        return

    top = fn_locations[0]
    print(f"  → {top.file}::{top.function}() [{top.confidence}]")
    print(f"    {top.reason}")

    patch_result = PatchGenerator(llm).generate(issue, top, index)

    # Dry-run by default; --apply-patch to write to disk
    dry_run = not args.apply_patch
    apply_result = PatchApplier(repo_path).apply(patch_result.diff, dry_run=dry_run)

    print("\n" + "="*70)
    print(f"PATCH for {top.file}::{top.function}()")
    print("="*70)
    print(patch_result.diff[:2000])
    print("="*70)
    print(f"Validation passed : {patch_result.validation_passed}")
    print(f"Applies cleanly   : {apply_result.success} ({'dry-run' if dry_run else 'APPLIED TO DISK'})")
    print(f"Attempts needed   : {patch_result.attempts}")
    print(f"\nExplanation:\n{patch_result.explanation}")

    # 7. PR summary
    print("\n[7/7] Generating PR summary...")
    summary = PRSummaryGenerator().generate(
        issue_title=issue.title,
        issue_description=issue.body[:400],
        files_changed=[top.file],
        patch_summary=f"Fixed `{top.function}()` in `{top.file}`\n\n{patch_result.explanation}\n\n```diff\n{patch_result.diff[:1000]}\n```",
        validation_result={"status": "PASS" if apply_result.success else "FAIL"},
    )
    md = MarkdownGenerator().generate(summary)
    print(md[:800])


if __name__ == "__main__":
    main()
