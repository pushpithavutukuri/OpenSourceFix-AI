class FeedbackLoop:

    def create_feedback(self, issue, test_result):

        if test_result["passed"]:
            return "All tests passed. No further changes required."

        feedback = f"""
The generated patch failed the test suite.

Issue:
{issue}

Pytest Output:
{test_result['stdout']}

Errors:
{test_result['stderr']}

Please generate an improved code patch that fixes these errors.
"""

        return feedback.strip()
