"""
patch_generator.py

Sends function-level localization to an LLM and gets back a real
unified diff (git diff format) that can be applied with patch(1).

Week 1: LLM returns prose ("you should change X to Y")
Week 2: LLM returns a unified diff that applies cleanly
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from bug_localization.function_localizer import FunctionLocation
from fix_generation.diff_validator import DiffValidator

logger = logging.getLogger(__name__)

MAX_CONTEXT_LINES = 40


@dataclass
class PatchResult:
    diff: str
    target_file: str
    function_name: str
    explanation: str
    validation_passed: bool
    validation_warnings: List[str] = field(default_factory=list)
    attempts: int = 1


class PatchGenerator:
    """
    Generates a unified diff patch from function-level localization.

    Includes retry logic: if the LLM returns an invalid diff, we retry
    with feedback about what was wrong (up to max_retries times).
    """

    def __init__(self, model_client, max_retries: int = 2):
        self.model = model_client
        self.max_retries = max_retries
        self.validator = DiffValidator()

    def generate(self, issue, location: FunctionLocation, index: dict) -> PatchResult:
        source = self._load_source(location, index)
        feedback = None
        diff = ""
        explanation = ""
        val = None

        for attempt in range(1, self.max_retries + 2):
            prompt = self._build_prompt(issue, location, source, feedback)
            raw = self.model.generate(prompt)
            diff, explanation = self._extract_diff_and_explanation(raw)
            val = self.validator.validate(diff, repo_index=index)

            if val.valid:
                logger.info("PatchGenerator: valid diff on attempt %d (%d hunks).", attempt, val.hunk_count)
                return PatchResult(
                    diff=diff, target_file=location.file, function_name=location.function,
                    explanation=explanation, validation_passed=True,
                    validation_warnings=val.warnings, attempts=attempt,
                )

            feedback = "\n".join(val.errors)
            logger.warning("Attempt %d produced invalid diff: %s. Retrying...", attempt, feedback)

        logger.error("PatchGenerator: all %d attempts failed.", self.max_retries + 1)
        return PatchResult(
            diff=diff, target_file=location.file, function_name=location.function,
            explanation=explanation, validation_passed=False,
            validation_warnings=val.errors if val else [], attempts=self.max_retries + 1,
        )

    def _load_source(self, location: FunctionLocation, index: dict) -> str:
        abs_path = index.get(location.file, {}).get("abs_path", "")
        if not abs_path or not Path(abs_path).exists():
            return location.code_snippet
        lines = Path(abs_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, location.start_line - 1 - MAX_CONTEXT_LINES)
        end = min(len(lines), location.end_line + MAX_CONTEXT_LINES)
        return "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines[start:end]))

    def _build_prompt(self, issue, location: FunctionLocation, source: str, feedback: Optional[str]) -> str:
        retry_note = ""
        if feedback:
            retry_note = f"""
## Previous Attempt Failed
Your previous diff was rejected:
{feedback}
Please fix these issues in your new response.
"""
        return f"""You are an expert software engineer fixing a GitHub bug.

## Issue
Title: {issue.title}
Description:
{issue.body[:500]}

## Bug Location
File:     {location.file}
Function: {location.function} (lines {location.start_line}–{location.end_line})
Reason:   {location.reason}

## Source Code (with line numbers)
```python
{source}
```
{retry_note}
## Task
Produce a unified diff (git diff format) that fixes the bug.

Rules:
- Output ONLY the diff block between <DIFF> and </DIFF> tags.
- Output your explanation between <EXPLANATION> and </EXPLANATION> tags.
- The diff MUST start with: --- a/{location.file}
- The diff MUST have:       +++ b/{location.file}
- Include @@ hunk headers with correct line numbers.
- Context lines (unchanged) start with a space.
- Removed lines start with -
- Added lines start with +

<DIFF>
--- a/{location.file}
+++ b/{location.file}
@@ ... @@
 (your diff here)
</DIFF>

<EXPLANATION>
(your explanation here)
</EXPLANATION>
"""

    def _extract_diff_and_explanation(self, raw: str):
        diff_match = re.search(r"<DIFF>(.*?)</DIFF>", raw, re.DOTALL)
        exp_match  = re.search(r"<EXPLANATION>(.*?)</EXPLANATION>", raw, re.DOTALL)
        diff = diff_match.group(1).strip() if diff_match else raw.strip()
        explanation = exp_match.group(1).strip() if exp_match else ""
        return diff, explanation
