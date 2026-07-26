"""
fix_generation/multi_file_patch_generator.py

Generates patches that span multiple files.

Many bugs require changes in more than one place:
    - Fix the bug in auth/session.py
    - Update the Token model in models/token.py
    - Fix the test in tests/test_auth.py

This module generates a collection of unified diffs, one per file,
that together constitute a complete fix.

Output schema
-------------
MultiFilePatch:
    patches: [
        PatchResult(target_file="auth/session.py", diff="...", ...),
        PatchResult(target_file="models/token.py",  diff="...", ...),
    ]
    combined_explanation: "..."
    all_valid: bool
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from fix_generation.patch_generator import PatchGenerator, PatchResult
from fix_generation.diff_validator import DiffValidator
from retrieval.repository_ranker import RankedFile

logger = logging.getLogger(__name__)

MAX_CONTEXT_LINES = 60
MAX_FILES_TO_PATCH = 4    # cap to avoid prompt bloat


@dataclass
class MultiFilePatch:
    patches: List[PatchResult]
    combined_explanation: str
    all_valid: bool
    files_changed: List[str] = field(default_factory=list)

    def combined_diff(self) -> str:
        """Concatenate all diffs into one string (for display)."""
        return "\n\n".join(p.diff for p in self.patches if p.diff)


class MultiFilePatchGenerator:
    """
    Generates a coordinated patch across multiple files.

    Strategy
    --------
    1. Show the LLM ALL relevant file snippets in one prompt
    2. Ask it to produce one diff block per file that needs changing
    3. Parse and validate each diff block independently
    4. Return all valid patches as a MultiFilePatch

    This is better than calling PatchGenerator N times because:
    - The LLM sees the full context of related files
    - Changes are coordinated (e.g., new function in A + call in B)
    - One LLM call instead of N
    """

    def __init__(self, model_client, max_retries: int = 2):
        self.model = model_client
        self.max_retries = max_retries
        self.validator = DiffValidator()

    def generate(
        self,
        issue,
        ranked_files: List[RankedFile],
        index: dict,
        primary_location=None,   # FunctionLocation — optional focus point
    ) -> MultiFilePatch:
        """
        Generate a multi-file patch.

        Args:
            issue:           GitHubIssue dataclass.
            ranked_files:    From RepositoryRanker.rank().
            index:           RepoIndex dict.
            primary_location: Optional FunctionLocation for the primary bug site.

        Returns:
            MultiFilePatch with one PatchResult per changed file.
        """
        # Select top files to include in the prompt
        files_to_patch = [
            rf for rf in ranked_files[:MAX_FILES_TO_PATCH]
            if not rf.path.startswith("test")  # don't patch test files by default
        ]
        test_files = [
            rf for rf in ranked_files
            if rf.reason == "test_coverage"
        ][:1]

        all_files = files_to_patch + test_files
        snippets = self._collect_snippets(all_files, index)
        feedback = None

        for attempt in range(1, self.max_retries + 2):
            prompt = self._build_prompt(issue, all_files, snippets, primary_location, feedback)
            raw = self.model.generate(prompt)
            patches = self._parse_patches(raw, index)

            if patches:
                all_valid = all(p.validation_passed for p in patches)
                logger.info(
                    "MultiFilePatchGenerator: %d patches on attempt %d, all_valid=%s",
                    len(patches), attempt, all_valid,
                )
                explanation = self._extract_explanation(raw)
                return MultiFilePatch(
                    patches=patches,
                    combined_explanation=explanation,
                    all_valid=all_valid,
                    files_changed=[p.target_file for p in patches],
                )
            feedback = "No valid diff blocks found. Use <FILE path=...> tags around each diff."

        return MultiFilePatch(patches=[], combined_explanation="", all_valid=False)

    # ── private ────────────────────────────────────────────────────────────

    def _collect_snippets(self, ranked_files: List[RankedFile], index: dict) -> str:
        parts = []
        for rf in ranked_files:
            abs_path = index.get(rf.path, {}).get("abs_path", "")
            if not abs_path or not Path(abs_path).exists():
                continue
            lines = Path(abs_path).read_text(encoding="utf-8", errors="ignore").splitlines()
            snippet = "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines[:MAX_CONTEXT_LINES]))
            parts.append(f"### {rf.path} [{rf.reason}]\n```python\n{snippet}\n```")
        return "\n\n".join(parts)

    def _build_prompt(self, issue, files, snippets, primary_location, feedback) -> str:
        primary_note = ""
        if primary_location:
            primary_note = f"\nPrimary bug location: {primary_location.file}::{primary_location.function}() — {primary_location.reason}"

        retry_note = f"\n## Previous Attempt Failed\n{feedback}" if feedback else ""
        file_list = "\n".join(f"- {rf.path} ({rf.reason})" for rf in files)

        return f"""You are an expert software engineer fixing a GitHub bug that spans multiple files.

## Issue #{issue.number}: {issue.title}
{issue.body[:500]}{primary_note}

## Files That Need Changing
{file_list}

## Source Code
{snippets}
{retry_note}
## Task
Generate unified diffs for ALL files that need to change to fix this bug.

Rules:
- Wrap each file's diff in <FILE path="relative/path.py"> ... </FILE> tags
- Inside each FILE tag, write a standard unified diff starting with --- a/ and +++ b/
- Include @@ hunk headers with correct line numbers
- Only include files that actually need changes
- After all FILE tags, write <EXPLANATION> ... </EXPLANATION>

<FILE path="example/file.py">
--- a/example/file.py
+++ b/example/file.py
@@ -10,5 +10,6 @@
 context
-old line
+new line
</FILE>

<EXPLANATION>
Why these changes fix the bug.
</EXPLANATION>
"""

    def _parse_patches(self, raw: str, index: dict) -> List[PatchResult]:
        import re
        patches = []
        file_blocks = re.findall(
            r'<FILE path="([^"]+)">(.*?)</FILE>',
            raw, re.DOTALL
        )
        for path, diff_text in file_blocks:
            diff = diff_text.strip()
            val = self.validator.validate(diff, repo_index=index)
            patches.append(PatchResult(
                diff=diff,
                target_file=path,
                function_name="multi-file",
                explanation="",
                validation_passed=val.valid,
                validation_warnings=val.warnings,
                attempts=1,
            ))
        return patches

    def _extract_explanation(self, raw: str) -> str:
        import re
        match = re.search(r"<EXPLANATION>(.*?)</EXPLANATION>", raw, re.DOTALL)
        return match.group(1).strip() if match else ""
