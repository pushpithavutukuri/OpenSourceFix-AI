"""
stack_trace_parser.py

Extracts structured information from Python stack traces embedded in
GitHub issue bodies or comments.

Why this is valuable
--------------------
A stack trace is the highest-signal input we can get for bug localization.
If the issue says:

    File "auth/session.py", line 42, in refresh_token
        return token.value
    AttributeError: 'NoneType' object has no attribute 'value'

We can skip semantic search entirely and go straight to line 42 of
auth/session.py with extremely high confidence.

Stack trace frames are returned sorted innermost-first (closest to the
error), because that is usually the highest-signal frame.

Output schema
-------------
[
    StackFrame(file="auth/session.py", line=42, function="refresh_token",
               code="return token.value", error="AttributeError: ...")
]
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Python traceback patterns
_FRAME_RE = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<function>\S+)\n\s+(?P<code>.+)',
    re.MULTILINE,
)
_ERROR_RE = re.compile(r"^([A-Z][a-zA-Z]+Error|[A-Z][a-zA-Z]+Exception|AssertionError|KeyboardInterrupt)[:\s].*$", re.MULTILINE)
_TRACEBACK_START = re.compile(r"Traceback \(most recent call last\):")


@dataclass
class StackFrame:
    file: str
    line: int
    function: str
    code: str
    error: str = ""          # populated only on the innermost frame


@dataclass
class ParsedTraceback:
    frames: List[StackFrame]   # innermost first
    error_type: str
    error_message: str
    has_traceback: bool


class StackTraceParser:
    """
    Parses Python tracebacks from free-form text (issue body + comments).

    Usage:
        parser = StackTraceParser()
        result = parser.parse(issue.body + " ".join(issue.comments))
        if result.has_traceback:
            # Use result.frames[0] as the primary bug location
    """

    def parse(self, text: str) -> ParsedTraceback:
        """
        Extract all stack frames from the given text.

        Args:
            text: Combined issue body + comments.

        Returns:
            ParsedTraceback with frames sorted innermost-first.
        """
        if not _TRACEBACK_START.search(text):
            return ParsedTraceback(frames=[], error_type="", error_message="", has_traceback=False)

        frames = []
        for match in _FRAME_RE.finditer(text):
            frames.append(StackFrame(
                file=self._normalize_path(match.group("file")),
                line=int(match.group("line")),
                function=match.group("function"),
                code=match.group("code").strip(),
            ))

        # Attach error type to innermost frame
        error_type = ""
        error_message = ""
        error_match = _ERROR_RE.search(text)
        if error_match:
            error_line = error_match.group(0)
            parts = error_line.split(":", 1)
            error_type = parts[0].strip()
            error_message = parts[1].strip() if len(parts) > 1 else ""
            if frames:
                frames[-1].error = error_line

        # Reverse so innermost (most relevant) is first
        frames.reverse()

        logger.info("StackTraceParser: found %d frames, error=%s", len(frames), error_type)
        return ParsedTraceback(
            frames=frames,
            error_type=error_type,
            error_message=error_message,
            has_traceback=len(frames) > 0,
        )

    def to_bug_hints(self, traceback: ParsedTraceback) -> List[dict]:
        """
        Convert parsed frames into the hint format used by BugLocalizer.

        Returns:
            List of {"file": ..., "line": ..., "function": ..., "confidence": ...}
        """
        hints = []
        for i, frame in enumerate(traceback.frames):
            # Innermost frame gets high confidence, outer frames lower
            confidence = "high" if i == 0 else ("medium" if i == 1 else "low")
            hints.append({
                "file": frame.file,
                "line": frame.line,
                "function": frame.function,
                "confidence": confidence,
                "source": "stack_trace",
            })
        return hints

    # ── private ────────────────────────────────────────────────────────────

    def _normalize_path(self, path: str) -> str:
        """
        Normalize file paths from tracebacks.

        Tracebacks often include absolute paths or site-packages paths.
        We strip common prefixes to get repo-relative paths.
        """
        # Remove leading slpath components until we hit something that looks like source
        parts = path.replace("\\", "/").split("/")
        # Drop everything up to and including common root names
        skip_tokens = {"home", "usr", "Users", "workspace", "app", "src", "opt"}
        for i, part in enumerate(parts):
            if part in skip_tokens and i < len(parts) - 2:
                # heuristic: keep from the next meaningful segment
                pass
        # Return the last 3 path components as a reasonable relative path
        return "/".join(parts[-3:]) if len(parts) >= 3 else path
