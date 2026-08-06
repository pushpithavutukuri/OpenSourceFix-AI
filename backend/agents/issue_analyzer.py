import json
import os
from typing import Dict

import google.generativeai as genai


class IssueAnalyzer:
    """
    Uses Gemini to analyze a GitHub issue and convert it
    into structured implementation requirements.
    """

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables."
            )

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )

    def analyze(self, issue: Dict):

        prompt = f"""
You are an expert software engineer.

Analyze the following GitHub issue.

Issue Title:
{issue['title']}

Issue Description:
{issue['body']}

Labels:
{issue['labels']}

Comments:
{issue['comments']}

Return ONLY valid JSON.

Format:

{{
    "problem_summary":"",
    "possible_root_causes":[],
    "files_to_modify":[],
    "implementation_steps":[],
    "testing_strategy":""
}}
"""

        response = self.model.generate_content(prompt)

        text = response.text.strip()

        if text.startswith("```json"):
            text = text.replace("```json", "")
            text = text.replace("```", "")
            text = text.strip()

        return json.loads(text)


if __name__ == "__main__":

    sample_issue = {
        "title": "Fix login failure when session expires",
        "body": """
Users are redirected to the login page,
but after logging in again,
the application throws a 500 error.
""",
        "labels": [
            "bug",
            "authentication"
        ],
        "comments": [
            "Looks related to session middleware.",
            "Probably happens after token refresh."
        ]
    }

    analyzer = IssueAnalyzer()

    result = analyzer.analyze(sample_issue)

    print(
        json.dumps(
            result,
            indent=4
        )
    )
