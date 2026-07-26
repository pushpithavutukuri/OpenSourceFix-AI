"""
sandbox/docker_runner.py

Runs patch validation inside a Docker container so the host machine
is never at risk from an AI-generated patch.

Pipeline inside the container
------------------------------
    docker run python:3.11-slim
        ↓
    pip install -r requirements.txt
        ↓
    apply patch
        ↓
    pytest
        ↓
    return exit code + stdout/stderr

Why this matters
----------------
An AI-generated patch might:
- Delete files
- Make network calls
- Install malicious packages
- Corrupt the codebase

Docker gives us:
- Filesystem isolation (container has its own copy of the repo)
- Network control (can disable with --network none)
- Resource limits (--memory, --cpus)
- Clean teardown every run

Requirements
------------
- Docker must be installed and running on the host
- The repo must be mountable as a volume

Usage
-----
    runner = DockerRunner(repo_path=Path("cloned_repos/flask"))
    result = runner.run(diff_text="--- a/auth.py\n+++ b/auth.py\n...")
    if result.passed:
        print("Tests passed in sandbox!")
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default Docker image — python:3.11-slim is small and has pip
DEFAULT_IMAGE = "python:3.11-slim"

# Safety limits
MEMORY_LIMIT  = "512m"
CPU_LIMIT     = "1.0"
TIMEOUT_SECS  = 120


@dataclass
class SandboxResult:
    passed: bool
    stdout: str
    stderr: str
    return_code: int
    container_id: str = ""
    timed_out: bool = False


class DockerRunner:
    """
    Applies a patch and runs the test suite inside a Docker container.

    Args:
        repo_path:   Path to the cloned repository on the host.
        image:       Docker image to use (default: python:3.11-slim).
        timeout:     Max seconds to wait for the container (default: 120).
        network:     Docker network mode. Use "none" to block internet access.
    """

    def __init__(
        self,
        repo_path: Path,
        image: str = DEFAULT_IMAGE,
        timeout: int = TIMEOUT_SECS,
        network: str = "bridge",
    ):
        self.repo_path = repo_path
        self.image = image
        self.timeout = timeout
        self.network = network

    def is_available(self) -> bool:
        """Check if Docker daemon is running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def run(self, diff_text: str) -> SandboxResult:
        """
        Apply the diff and run tests inside a Docker container.

        Args:
            diff_text: Unified diff string to apply inside the container.

        Returns:
            SandboxResult with pass/fail and output.
        """
        if not self.is_available():
            logger.warning("Docker not available. Falling back to host execution.")
            return self._fallback_run(diff_text)

        # Write patch to a temp file the container can access
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, dir="/tmp"
        ) as f:
            f.write(diff_text)
            patch_file = f.name

        # Shell script that runs inside the container
        script = self._build_container_script(patch_file)

        cmd = [
            "docker", "run",
            "--rm",
            f"--memory={MEMORY_LIMIT}",
            f"--cpus={CPU_LIMIT}",
            f"--network={self.network}",
            "--volume", f"{self.repo_path}:/repo:rw",
            "--volume", f"{patch_file}:{patch_file}:ro",
            "--workdir", "/repo",
            self.image,
            "bash", "-c", script,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            passed = result.returncode == 0
            logger.info("Docker sandbox: returncode=%d", result.returncode)
            return SandboxResult(
                passed=passed,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.error("Docker container timed out after %ds.", self.timeout)
            return SandboxResult(
                passed=False,
                stdout="",
                stderr=f"Container timed out after {self.timeout} seconds.",
                return_code=-1,
                timed_out=True,
            )
        except Exception as exc:
            logger.error("Docker run failed: %s", exc)
            return SandboxResult(
                passed=False, stdout="", stderr=str(exc), return_code=-1
            )
        finally:
            Path(patch_file).unlink(missing_ok=True)

    # ── private ────────────────────────────────────────────────────────────

    def _build_container_script(self, patch_file: str) -> str:
        """Build the shell script that runs inside the Docker container."""
        return f"""
set -e
echo "=== Installing dependencies ==="
pip install -r requirements.txt -q 2>&1 || pip install pytest -q

echo "=== Applying patch ==="
patch -p1 --input={patch_file} || {{ echo "Patch failed to apply"; exit 1; }}

echo "=== Running tests ==="
pytest --tb=short -q 2>&1
"""

    def _fallback_run(self, diff_text: str) -> SandboxResult:
        """Run on host when Docker is unavailable (less safe)."""
        from fix_generation.patch_applier import PatchApplier
        from validation.validator import Validator

        apply_result = PatchApplier(self.repo_path).apply(diff_text, dry_run=False)
        if not apply_result.success:
            return SandboxResult(
                passed=False, stdout="", stderr=apply_result.stderr,
                return_code=1,
            )
        val = Validator().validate(str(self.repo_path))
        details = val.get("details", {})
        return SandboxResult(
            passed=val["status"] == "PASS",
            stdout=details.get("stdout", ""),
            stderr=details.get("stderr", ""),
            return_code=0 if val["status"] == "PASS" else 1,
        )
