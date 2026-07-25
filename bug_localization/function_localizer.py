"""
function_localizer.py

Upgrades bug localization from file-level to function-level using an LLM.

Week 1:  "The bug is probably in auth.py"
Week 2:  "The bug is in auth.py::refresh_token() at line 42"
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from bug_localization.bug_localizer import BugLocalization

logger = logging.getLogger(__name__)

MAX_FILE_LINES = 200


@dataclass
class FunctionLocation:
    file: str
    function: str
    start_line: int
    end_line: int
    confidence: str        # "high" | "medium" | "low"
    reason: str
    code_snippet: str = ""


class FunctionLocalizer:
    """
    Uses an LLM to narrow localization from file-level to function-level.

    For each primary suspect file:
    1. Extract source (capped at MAX_FILE_LINES to stay in context window)
    2. Ask LLM: which function is responsible for this bug?
    3. Parse JSON response → FunctionLocation
    4. Return sorted by confidence: high → medium → low
    """

    def __init__(self, model_client):
        self.model = model_client

    def localize(self, issue, localization: BugLocalization, index: dict) -> List[FunctionLocation]:
        results = []
        for rel_path in localization.primary_files:
            meta = index.get(rel_path, {})
            abs_path = meta.get("abs_path", "")
            if not abs_path or not Path(abs_path).exists():
                continue
            loc = self._localize_file(issue, rel_path, abs_path, meta)
            if loc:
                results.append(loc)

        order = {"high": 0, "medium": 1, "low": 2}
        results.sort(key=lambda r: order.get(r.confidence, 3))
        logger.info("FunctionLocalizer: %d locations found.", len(results))
        return results

    def _localize_file(self, issue, rel_path, abs_path, meta) -> Optional[FunctionLocation]:
        source_lines = Path(abs_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        source_snippet = "\n".join(
            f"{i+1:4d} | {line}" for i, line in enumerate(source_lines[:MAX_FILE_LINES])
        )
        functions = meta.get("functions", [])
        prompt = self._build_prompt(issue, rel_path, source_snippet, functions)
        try:
            raw = self.model.generate(prompt)
            return self._parse_response(raw, rel_path, source_lines)
        except Exception as exc:
            logger.warning("FunctionLocalizer failed for %s: %s", rel_path, exc)
            return None

    def _build_prompt(self, issue, rel_path, source_snippet, functions) -> str:
        fn_list = ", ".join(functions) if functions else "unknown"
        return f"""You are an expert software engineer performing bug localization.

## GitHub Issue
Title: {issue.title}
Description:
{issue.body[:600]}

## File Under Analysis
Path: {rel_path}
Known functions: {fn_list}

## Source Code (with line numbers)
```python
{source_snippet}
```

## Task
Identify the single function most likely to contain the bug described in the issue.

Respond with ONLY a JSON object in this exact format (no markdown, no explanation):
{{
    "function": "<function_name>",
    "start_line": <int>,
    "end_line": <int>,
    "confidence": "<high|medium|low>",
    "reason": "<one sentence explaining why this function is suspect>"
}}
"""

    def _parse_response(self, raw, rel_path, source_lines) -> Optional[FunctionLocation]:
        clean = re.sub(r"```[a-z]*", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            logger.warning("No JSON found in function localizer response.")
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error: %s", exc)
            return None

        start = max(1, int(data.get("start_line", 1))) - 1
        end = min(len(source_lines), int(data.get("end_line", start + 10)))
        snippet = "\n".join(source_lines[start:end])

        return FunctionLocation(
            file=rel_path,
            function=data.get("function", "unknown"),
            start_line=start + 1,
            end_line=end,
            confidence=data.get("confidence", "low"),
            reason=data.get("reason", ""),
            code_snippet=snippet,
        )
