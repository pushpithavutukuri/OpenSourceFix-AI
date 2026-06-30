from datetime import datetime


class PRSummaryGenerator:
    """
    Generates a structured Pull Request summary.
    """

    def generate(
        self,
        issue_title,
        issue_description,
        files_changed,
        patch_summary,
        validation_result,
    ):

        status = (
            "Tests Passed"
            if validation_result["status"] == "PASS"
            else "Tests Failed"
        )

        summary = {
            "title": f"Fix: {issue_title}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": issue_description,
            "files_changed": files_changed,
            "patch_summary": patch_summary,
            "validation": status,
        }

        return summary
