"""
issue_parser.py

Parses raw GitHub issue data into a clean structure that can be
used by the issue analysis and bug localization pipeline.
"""

import re
from datetime import datetime


class IssueParser:
    """Parses and cleans GitHub issue information."""

    def __init__(self):
        pass

    def clean_text(self, text: str) -> str:
        """
        Remove markdown syntax and extra whitespace.
        """

        if not text:
            return ""

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)

        # Remove inline code
        text = re.sub(r"`.*?`", "", text)

        # Remove markdown links
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

        # Remove markdown headings
        text = re.sub(r"#+", "", text)

        # Remove bullet symbols
        text = re.sub(r"[-*]", " ", text)

        # Remove extra spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract_metadata(self, issue: dict) -> dict:
        """
        Extract metadata from a GitHub issue.
        """

        labels = []

        for label in issue.get("labels", []):
            labels.append(label["name"])

        assignees = []

        for assignee in issue.get("assignees", []):
            assignees.append(assignee["login"])

        metadata = {
            "issue_number": issue.get("number"),
            "title": issue.get("title", ""),
            "body": self.clean_text(issue.get("body", "")),
            "state": issue.get("state"),
            "author": issue.get("user", {}).get("login"),
            "labels": labels,
            "assignees": assignees,
            "comments": issue.get("comments", 0),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "url": issue.get("html_url")
        }

        return metadata

    def parse_issue(self, issue: dict) -> dict:
        """
        Parse complete GitHub issue.
        """

        parsed_issue = self.extract_metadata(issue)

        parsed_issue["title_length"] = len(parsed_issue["title"])
        parsed_issue["body_length"] = len(parsed_issue["body"])

        parsed_issue["has_labels"] = len(parsed_issue["labels"]) > 0
        parsed_issue["has_assignees"] = len(parsed_issue["assignees"]) > 0

        return parsed_issue


if __name__ == "__main__":

    sample_issue = {
        "number": 101,
        "title": "Login page crashes",
        "body": """
        ## Description

        Login fails after password reset.

        ```python
        print("error")
        ```

        Happens on Chrome.
        """,
        "state": "open",
        "comments": 4,
        "created_at": str(datetime.now()),
        "updated_at": str(datetime.now()),
        "html_url": "https://github.com/example/repo/issues/101",
        "user": {
            "login": "riya"
        },
        "labels": [
            {"name": "bug"},
            {"name": "frontend"}
        ],
        "assignees": [
            {"login": "developer1"}
        ]
    }

    parser = IssueParser()

    parsed = parser.parse_issue(sample_issue)

    for key, value in parsed.items():
        print(f"{key}: {value}")
