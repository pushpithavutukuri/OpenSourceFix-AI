"""
diff_validator.py

Validates a unified diff string before we try to apply it.
Catches malformed LLM output early so we can retry.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

_HUNK_RE   = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", re.MULTILINE)
_HEADER_RE = re.compile(r"^--- .+\n\+\+\+ .+", re.MULTILINE)


@dataclass
class DiffValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hunk_count: int = 0
    files_changed: List[str] = field(default_factory=list)


class DiffValidator:
    """Validates a unified diff string."""

    def validate(self, diff_text: str, repo_index: dict = None) -> DiffValidationResult:
        result = DiffValidationResult(valid=False)

        if not diff_text or not diff_text.strip():
            result.errors.append("Diff is empty.")
            return result

        if "binary files" in diff_text.lower():
            result.errors.append("Diff contains binary file markers.")
            return result

        if not _HEADER_RE.search(diff_text):
            result.errors.append("No valid --- / +++ header pair found.")
            return result

        hunks = _HUNK_RE.findall(diff_text)
        if not hunks:
            result.errors.append("No @@ hunk headers found.")
            return result

        result.hunk_count = len(hunks)

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                fp = line[6:].strip()
                result.files_changed.append(fp)
                if repo_index and fp not in repo_index:
                    result.warnings.append(f"File '{fp}' not found in repository index.")

        result.valid = len(result.errors) == 0
        if result.valid:
            logger.info("Diff validated: %d hunks, %d files.", result.hunk_count, len(result.files_changed))
        else:
            logger.warning("Diff invalid: %s", result.errors)
        return result
