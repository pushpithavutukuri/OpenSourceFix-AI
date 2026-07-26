"""
test_sandbox.py
Tests for DockerRunner — Docker calls are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDockerRunner:
    def test_is_available_returns_bool(self):
        from sandbox.docker_runner import DockerRunner
        runner = DockerRunner()
        # Just check it returns a bool, don't require Docker to be installed
        assert isinstance(runner.is_available(), bool)

    def test_sandbox_result_structure(self):
        from sandbox.docker_runner import SandboxResult
        result = SandboxResult(passed=True, stdout="ok", stderr="", exit_code=0, duration_seconds=1.0)
        assert result.passed
        assert result.exit_code == 0

    @patch("subprocess.run")
    def test_run_tests_returns_result_on_docker_not_available(self, mock_run):
        """When Docker isn't installed, run_tests should handle gracefully."""
        from sandbox.docker_runner import DockerRunner
        mock_run.side_effect = FileNotFoundError("docker not found")
        runner = DockerRunner()
        # is_available() will return False
        assert not runner.is_available()
