"""
OpenSourceFix AI

Autonomous Open-Source Issue Resolution Agent.

Main pipeline for repository analysis, issue understanding,
bug localization, and AI-assisted fix generation.

Authors:
Pushpitha Vutukuri
Keerthika Muddada
"""

import argparse
import json
import os

from utils.logger import setup_logging
from utils.config import load_config
from utils.llm_client import get_llm_client

from repository_analysis import RepoLoader, RepositoryIndexer, FileRanker
from issue_analysis import IssueFetcher, KeywordExtractor
from bug_localization import BugLocalizer
from fix_generation.fix_generator import FixGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenSourceFix AI — autonomous bug fixer")
    parser.add_argument("--repo",      required=True, help="GitHub repository URL")
    parser.add_argument("--owner",     required=True, help="GitHub owner (username or org)")
    parser.add_argument("--repo-name", required=True, help="Repository name")
    parser.add_argument("--issue",     required=True, type=int, help="GitHub issue number")
    parser.add_argument("--config",    default="config/config.yaml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    setup_logging(
        level=cfg["logging"]["level"],
        log_file=cfg["logging"]["log_file"],
    )

    # Override secrets from environment variables if set
    github_token = os.getenv("GITHUB_TOKEN") or cfg["github"]["token"]
    llm_api_key  = os.getenv("GEMINI_API_KEY") or cfg["llm"]["api_key"]
    cfg["llm"]["api_key"] = llm_api_key

    # ── 1. Clone / update repository ──────────────────────────────────────
    print("\n[1/6] Loading repository...")
    loader = RepoLoader(base_dir=cfg["repo"]["base_dir"])
    repo_path = loader.load(args.repo)

    # ── 2. Build repository index ──────────────────────────────────────────
    print("[2/6] Building repository index...")
    indexer = RepositoryIndexer(repo_path)
    index = indexer.build()
    dep_graph = indexer.dependency_graph
    print(f"      Indexed {len(index)} Python files.")

    # ── 3. Fetch GitHub issue ──────────────────────────────────────────────
    print(f"[3/6] Fetching issue #{args.issue}...")
    fetcher = IssueFetcher(token=github_token)
    issue = fetcher.fetch(args.owner, args.repo_name, args.issue)
    print(f"      Issue: {issue.title}")

    # ── 4. Extract keywords ────────────────────────────────────────────────
    print("[4/6] Extracting keywords...")
    extractor = KeywordExtractor()
    keywords = extractor.extract(issue)
    print(f"      Keywords: {keywords[:10]}")

    # ── 5. Rank files + localize bug ───────────────────────────────────────
    print("[5/6] Ranking files and localizing bug...")
    ranker = FileRanker()
    ranked = ranker.rank(index, keywords)

    localizer = BugLocalizer(top_n=cfg["bug_localization"]["top_n"])
    localization = localizer.localize(ranked, dep_graph, index)

    print("\n  Primary suspect files:")
    for f in localization.primary_files:
        print(f"    [{localization.scores.get(f, 0):>3}]  {f}")

    if localization.related_files:
        print("\n  Related files (via dependency graph):")
        for f in localization.related_files:
            print(f"    {f}")

    # ── 6. Generate fix ────────────────────────────────────────────────────
    print("\n[6/6] Generating fix...")
    llm_client = get_llm_client(cfg["llm"])
    generator = FixGenerator(model_client=llm_client)
    proposal = generator.generate(issue, localization, index)

    print("\n" + "=" * 70)
    print(f"Fix Proposal for Issue #{proposal.issue_number}")
    print("=" * 70)
    print(proposal.proposed_fix)
    print("=" * 70)


if __name__ == "__main__":
    main()
