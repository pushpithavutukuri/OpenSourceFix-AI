"""
issue_fetcher.py
Fetches GitHub issues via the REST API.
"""

import logging
import requests
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    author: str
    state: str
    url: str
    labels: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IssueFetcher:
    """Retrieve issues from a public or private GitHub repository."""

    def __init__(self, token: Optional[str] = None):
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """
        Fetch a single issue by number.

        Args:
            owner:        GitHub username or org (e.g. "tiangolo").
            repo:         Repository name (e.g. "fastapi").
            issue_number: The issue number.

        Returns:
            GitHubIssue dataclass.
        """
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        comments = self._fetch_comments(owner, repo, issue_number)

        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            author=data["user"]["login"],
            state=data["state"],
            url=data["html_url"],
            labels=[lbl["name"] for lbl in data.get("labels", [])],
            comments=comments,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> List[str]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        resp = requests.get(url, headers=self.headers, timeout=10)
        if resp.status_code != 200:
            return []
        return [c["body"] for c in resp.json()]
