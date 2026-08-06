import json
import os

import google.generativeai as genai

from models.schemas import (
    IssueData,
    IssueAnalysis,
    FixResult,
    ValidationResult,
    PullRequestSummary
)


class PRGenerator:

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found.")

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )

    def generate_pr(
        self,
        issue: IssueData,
        analysis: IssueAnalysis,
        fix: FixResult,
        validation: ValidationResult
    ) -> PullRequestSummary:

        patches = ""

        for patch in fix.patches:

            patches += f"""

File:
{patch.path}

Explanation:
{fix.explanation}

"""

        prompt = f"""
You are an experienced open-source contributor.

Generate a professional GitHub Pull Request.

Issue Title:
{issue.title}

Issue Description:
{issue.body}

Problem Summary:
{analysis.problem_summary}

Implementation:
{analysis.implementation_steps}

Validation Passed:
{validation.passed}

Validation Output:
{validation.stdout}

Files Changed:

{patches}

Return ONLY valid JSON.

Example:

{{
    "title":"Fix session expiration login bug",

    "description":"Detailed PR description..."
}}
"""

        response = self.model.generate_content(prompt)

        text = response.text.strip()

        if text.startswith("```json"):

            text = text.replace(
                "```json",
                ""
            )

            text = text.replace(
                "```",
                ""
            )

        data = json.loads(text)

        return PullRequestSummary(

            title=data["title"],

            description=data["description"]

        )


if __name__ == "__main__":

    issue = IssueData(
        title="Fix login bug",
        body="Application crashes after session expires.",
        labels=["bug"],
        comments=[]
    )

    analysis = IssueAnalysis(
        problem_summary="Session is not validated.",
        possible_root_causes=[
            "Missing session validation"
        ],
        files_to_modify=[
            "auth.py"
        ],
        implementation_steps=[
            "Validate session before login."
        ],
        testing_strategy="Run authentication tests."
    )

    fix = FixResult(
        explanation="Added session validation.",
        risks=[
            "May affect login flow."
        ],
        patches=[]
    )

    validation = ValidationResult(
        passed=True,
        stdout="All tests passed.",
        stderr=""
    )

    generator = PRGenerator()

    pr = generator.generate_pr(
        issue,
        analysis,
        fix,
        validation
    )

    print("\nTitle:")
    print(pr.title)

    print("\nDescription:")
    print(pr.description)
