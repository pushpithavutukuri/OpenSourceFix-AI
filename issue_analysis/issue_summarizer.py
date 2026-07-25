"""
issue_summarizer.py

Condenses a verbose GitHub issue (which may include long stack traces,
environment details, workaround discussions, etc.) into a crisp
one-paragraph technical brief that the LLM in later stages can
consume without hitting context limits.

Why this matters
----------------
A raw issue body can be 2000+ tokens of noise.
The summarizer extracts the signal:
    - What broke
    - Where it broke (file/function if mentioned)
    - Under what conditions
    - Any stack trace pointers

Output schema
-------------
{
    "one_line":    "Session token is not refreshed after expiry in refresh_token()",
    "technical":   "The refresh_token() function in auth/session.py returns the old
                    token value without checking token.is_expired(), causing 401
                    errors when the downstream service validates the token.",
    "stack_hints": ["auth/session.py", "refresh_token"],
    "severity":    "high"
}
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IssueSummary:
    one_line: str                               # ≤ 15 words
    technical: str                              # 2–4 sentence technical description
    stack_hints: List[str] = field(default_factory=list)   # files/functions mentioned
    severity: str = "medium"                    # "high" | "medium" | "low"


class IssueSummarizer:
    """
    Summarizes a GitHub issue into a structured technical brief using an LLM.

    Falls back to a simple truncation strategy if the LLM call fails,
    so the pipeline never stalls on this stage.
    """

    def __init__(self, model_client):
        self.model = model_client

    def summarize(self, issue) -> IssueSummary:
        """
        Produce a structured summary of the issue.

        Args:
            issue: GitHubIssue dataclass.

        Returns:
            IssueSummary with one_line, technical, stack_hints, severity.
        """
        prompt = self._build_prompt(issue)
        try:
            raw = self.model.generate(prompt)
            result = self._parse_response(raw)
            if result:
                logger.info("Summarized issue #%d: %s", issue.number, result.one_line)
                return result
        except Exception as exc:
            logger.warning("IssueSummarizer LLM call failed: %s. Using fallback.", exc)

        return self._fallback_summary(issue)

    # ── private ────────────────────────────────────────────────────────────

    def _build_prompt(self, issue) -> str:
        # Include comments if they exist — they often clarify root cause
        comments_text = ""
        if issue.comments:
            comments_text = "\n\nTop comments:\n" + "\n---\n".join(issue.comments[:3])

        return f"""You are a senior engineer triaging a GitHub issue.
Produce a structured technical summary.

## Issue #{issue.number}: {issue.title}

{issue.body[:1200]}{comments_text}

Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "one_line":    "<15 words or fewer: what broke and where>",
    "technical":   "<2-4 sentences: root cause, affected component, reproduction condition>",
    "stack_hints": ["<file or function name mentioned in the issue>", ...],
    "severity":    "<high|medium|low>"
}}

Severity guide:
- high   : data loss, security issue, crash on normal usage, blocks all users
- medium : feature broken for some users, workaround exists
- low    : minor inconvenience, cosmetic, edge case
"""

    def _parse_response(self, raw: str) -> Optional[IssueSummary]:
        clean = re.sub(r"```[a-z]*", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
            return IssueSummary(
                one_line=data.get("one_line", "")[:120],
                technical=data.get("technical", ""),
                stack_hints=data.get("stack_hints", []),
                severity=data.get("severity", "medium"),
            )
        except json.JSONDecodeError:
            return None

    def _fallback_summary(self, issue) -> IssueSummary:
        """Simple truncation fallback when LLM is unavailable."""
        return IssueSummary(
            one_line=issue.title[:100],
            technical=issue.body[:400].strip(),
            stack_hints=[],
            severity="medium",
        )
