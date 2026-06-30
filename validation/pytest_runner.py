import subprocess


class PytestRunner:
    """
    Runs pytest inside a cloned repository.
    """

    def run_tests(self, repo_path: str):
        try:
            result = subprocess.run(
                ["pytest"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )

            return {
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }

        except Exception as e:
            return {
                "passed": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1
            }
