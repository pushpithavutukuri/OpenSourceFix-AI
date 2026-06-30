from .pytest_runner import PytestRunner


class Validator:

    def __init__(self):
        self.runner = PytestRunner()

    def validate(self, repo_path: str):

        result = self.runner.run_tests(repo_path)

        if result["passed"]:
            return {
                "status": "PASS",
                "message": "All tests passed successfully.",
                "details": result
            }

        return {
            "status": "FAIL",
            "message": "Tests failed.",
            "details": result
        }
