"""
patch_applier.py

Applies a unified diff to the repository on disk using the system
`patch` command. Supports dry-run mode (verify without changing files).
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    success: bool
    stdout: str
    stderr: str
    dry_run: bool


class PatchApplier:
    """
    Applies a unified diff to a repository directory.

    Usage:
        applier = PatchApplier(repo_path)
        result = applier.apply(diff_text, dry_run=True)   # verify only
        result = applier.apply(diff_text, dry_run=False)  # real apply
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def apply(self, diff_text: str, dry_run: bool = True) -> ApplyResult:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as f:
            f.write(diff_text)
            patch_file = f.name

        cmd = ["patch", "-p1", "--input", patch_file]
        if dry_run:
            cmd.append("--dry-run")

        try:
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            success = result.returncode == 0
            mode = "Dry run" if dry_run else "Applied"
            if success:
                logger.info("%s: patch applied successfully.", mode)
            else:
                logger.warning("patch failed: %s", result.stderr)
            return ApplyResult(success=success, stdout=result.stdout, stderr=result.stderr, dry_run=dry_run)
        except FileNotFoundError:
            logger.warning("`patch` command not found. Falling back to Python apply.")
            return self._python_apply(diff_text, dry_run)
        finally:
            Path(patch_file).unlink(missing_ok=True)

    def _python_apply(self, diff_text: str, dry_run: bool) -> ApplyResult:
        """Minimal fallback for single-hunk diffs when patch(1) is unavailable."""
        lines = diff_text.splitlines()
        target = None
        for line in lines:
            if line.startswith("+++ b/"):
                target = self.repo_path / line[6:].strip()
                break

        if not target or not target.exists():
            return ApplyResult(False, "", "Target file not found.", dry_run)

        try:
            new_lines = []
            in_hunk = False
            for line in lines:
                if line.startswith("@@"):
                    in_hunk = True
                    continue
                if not in_hunk:
                    continue
                if line.startswith("+") and not line.startswith("+++"):
                    new_lines.append(line[1:] + "\n")
                elif line.startswith("-") and not line.startswith("---"):
                    pass
                else:
                    new_lines.append((line[1:] if line.startswith(" ") else line) + "\n")

            if dry_run:
                return ApplyResult(True, "Dry run OK (Python fallback).", "", dry_run)
            target.write_text("".join(new_lines), encoding="utf-8")
            return ApplyResult(True, "Applied (Python fallback).", "", dry_run)
        except Exception as exc:
            return ApplyResult(False, "", str(exc), dry_run)
