import json
import os
from typing import List

import google.generativeai as genai

from models.schemas import (
    IssueData,
    IssueAnalysis,
    CodeChunk,
    FilePatch,
    FixResult
)


class FixGenerator:

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found.")

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )

    def generate_fix(
        self,
        issue: IssueData,
        analysis: IssueAnalysis,
        retrieved_chunks: List[CodeChunk]
    ) -> FixResult:

        context = ""

        for chunk in retrieved_chunks:

            context += f"""

FILE:
{chunk.path}

CODE:

{chunk.text}

====================================================
"""

        prompt = f"""
You are an expert software engineer.

GitHub Issue

Title:
{issue.title}

Description:
{issue.body}

Problem Summary:
{analysis.problem_summary}

Possible Root Causes:
{analysis.possible_root_causes}

Implementation Steps:
{analysis.implementation_steps}

Repository Context:

{context}

Return ONLY valid JSON.

Example:

{{
  "explanation":"...",
  "risks":[
      "...",
      "..."
  ],
  "patches":[
      {{
        "path":"src/auth.py",
        "old_code":"...",
        "new_code":"..."
      }}
  ]
}}
"""

        response = self.model.generate_content(
            prompt
        )

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

        patches = []

        for patch in data["patches"]:

            patches.append(

                FilePatch(

                    path=patch["path"],

                    old_code=patch["old_code"],

                    new_code=patch["new_code"]

                )

            )

        return FixResult(

            explanation=data["explanation"],

            risks=data["risks"],

            patches=patches

        )
