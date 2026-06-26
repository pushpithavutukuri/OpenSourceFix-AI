"""
fix_generator.py
Sends bug-localization context + file snippets to an LLM and returns a proposed fix.
"""

import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from bug_localization.bug_localizer import BugLocalization
from issue_analysis.issue_fetcher import GitHubIssue

logger = logging.getLogger(__name__)

MAX_SNIPPET_LINES = 120   # keep LLM context manageable


@dataclass
class FixProposal:
    issue_number: int
    proposed_fix: str
    affected_files: List[str]
    explanation: str
    confidence: str   # "high" | "medium" | "low"


class FixGenerator:
    """
    Generates a natural-language fix proposal using an LLM.

    Currently supports:
        - Gemini via google-generativeai
        - Any OpenAI-compatible endpoint (Qwen, LM Studio)

    Switch the backend by changing `backend` in config.yaml.
    """

    def __init__(self, model_client, max_tokens: int = 2048):
        """
        Args:
            model_client: An object with a `.generate(prompt: str) -> str` method.
                          See utils/llm_client.py for adapters.
            max_tokens:   Max tokens for the LLM response.
        """
        self.model = model_client
        self.max_tokens = max_tokens

    def generate(
        self,
        issue: GitHubIssue,
        localization: BugLocalization,
        index: dict,
    ) -> FixProposal:
        """
        Build a prompt from the issue and top files, call the LLM, return a proposal.
        """
        snippets = self._collect_snippets(localization.primary_files, index)
        prompt = self._build_prompt(issue, localization, snippets)

        logger.info("Sending fix-generation prompt to LLM for issue #%d", issue.number)
        raw_response = self.model.generate(prompt)

        return FixProposal(
            issue_number=issue.number,
            proposed_fix=raw_response,
            affected_files=localization.primary_files,
            explanation="LLM-generated fix based on keyword + AST localization.",
            confidence="medium",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_snippets(self, primary_files: List[str], index: dict) -> str:
        parts = []
        for rel_path in primary_files:
            abs_path = index.get(rel_path, {}).get("abs_path")
            if not abs_path:
                continue
            try:
                lines = Path(abs_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                snippet = "\n".join(lines[:MAX_SNIPPET_LINES])
                parts.append(f"### {rel_path}\n```python\n{snippet}\n```")
            except Exception as exc:
                logger.warning("Could not read %s: %s", abs_path, exc)
        return "\n\n".join(parts)

    def _build_prompt(
        self,
        issue: GitHubIssue,
        localization: BugLocalization,
        snippets: str,
    ) -> str:
        return f"""You are an expert software engineer reviewing a bug report.

## Issue #{issue.number}: {issue.title}

{issue.body}

## Most Likely Bug Files
{chr(10).join(f'- {f}' for f in localization.primary_files)}

## Relevant Code Snippets
{snippets}

## Task
1. Identify the root cause of the bug.
2. Propose a specific code fix (show the exact lines to change).
3. Explain why this fix resolves the issue.
4. Note any edge cases or risks.

Respond in this format:
ROOT CAUSE:
...

PROPOSED FIX:
...

EXPLANATION:
...

RISKS / EDGE CASES:
...
"""
