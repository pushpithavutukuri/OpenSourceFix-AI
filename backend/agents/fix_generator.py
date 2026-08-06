import os
from typing import List, Dict

import google.generativeai as genai


class FixGenerator:
    """
    Generates repository-aware code fixes using Gemini.
    """

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found."
            )

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )

    def generate_fix(
        self,
        issue: Dict,
        analysis: Dict,
        retrieved_chunks: List[Dict]
    ):

        code_context = ""

        for chunk in retrieved_chunks:

            code_context += f"""

FILE:
{chunk['path']}

CODE:

{chunk['text']}

==================================================
"""

        prompt = f"""
You are an experienced software engineer.

Repository Context:

{code_context}

Issue Title:

{issue['title']}

Issue Description:

{issue['body']}

Issue Analysis:

Problem Summary:
{analysis['problem_summary']}

Possible Root Causes:
{analysis['possible_root_causes']}

Implementation Steps:
{analysis['implementation_steps']}

Generate:

1. Files that should change.

2. Updated code.

3. Explanation.

4. Potential risks.

Return Markdown only.

"""

        response = self.model.generate_content(prompt)

        return response.text


if __name__ == "__main__":

    issue = {
        "title": "Fix login failure",
        "body": "Session expires unexpectedly."
    }

    analysis = {
        "problem_summary":
        "Expired session causes authentication failure.",

        "possible_root_causes": [
            "Missing session validation"
        ],

        "implementation_steps": [
            "Check session before login"
        ]
    }

    retrieved_chunks = [

        {
            "path": "auth.py",
            "text":
            """
def login():
    pass
"""
        }

    ]

    generator = FixGenerator()

    fix = generator.generate_fix(
        issue,
        analysis,
        retrieved_chunks
    )

    print(fix)
