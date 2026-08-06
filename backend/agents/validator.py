import os
import subprocess
import tempfile
import shutil
from typing import Dict


class ValidationAgent:
    """
    Runs project tests after applying a generated fix.
    """

    def __init__(self):
        pass

    def create_temp_copy(self, repo_path: str):

        temp_dir = tempfile.mkdtemp()

        destination = os.path.join(
            temp_dir,
            os.path.basename(repo_path)
        )

        shutil.copytree(
            repo_path,
            destination,
            dirs_exist_ok=True
        )

        return destination

    def apply_changes(
        self,
        repo_path: str,
        generated_files: Dict[str, str]
    ):

        for relative_path, code in generated_files.items():

            full_path = os.path.join(
                repo_path,
                relative_path
            )

            folder = os.path.dirname(full_path)

            os.makedirs(
                folder,
                exist_ok=True
            )

            with open(
                full_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(code)

    def run_pytest(
        self,
        repo_path: str
    ):

        try:

            result = subprocess.run(
                ["pytest"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )

            return {
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except subprocess.TimeoutExpired:

            return {
                "passed": False,
                "stdout": "",
                "stderr": "Tests timed out."
            }

        except Exception as e:

            return {
                "passed": False,
                "stdout": "",
                "stderr": str(e)
            }

    def validate(
        self,
        repo_path: str,
        generated_files: Dict[str, str]
    ):

        temp_repo = self.create_temp_copy(repo_path)

        self.apply_changes(
            temp_repo,
            generated_files
        )

        result = self.run_pytest(
            temp_repo
        )

        shutil.rmtree(
            os.path.dirname(temp_repo),
            ignore_errors=True
        )

        return result


if __name__ == "__main__":

    validator = ValidationAgent()

    generated_files = {

        "sample.py":
"""
def add(a, b):
    return a + b
"""

    }

    report = validator.validate(
        "../repos/flask",
        generated_files
    )

    print(report)
