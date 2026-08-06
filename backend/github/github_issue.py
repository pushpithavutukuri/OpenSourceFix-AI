import requests
from urllib.parse import urlparse


class GitHubIssueFetcher:
    """
    Fetch GitHub issue details using the GitHub REST API.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, github_token=None):
        self.headers = {
            "Accept": "application/vnd.github+json"
        }

        if github_token:
            self.headers["Authorization"] = f"Bearer {github_token}"

    def parse_repo_url(self, repo_url):
        """
        Extract owner and repository name.

        Example:
        https://github.com/pallets/flask
        ->
        owner = pallets
        repo = flask
        """

        parsed = urlparse(repo_url)

        parts = parsed.path.strip("/").split("/")

        if len(parts) < 2:
            raise ValueError("Invalid GitHub repository URL.")

        owner = parts[0]
        repo = parts[1]

        return owner, repo

    def fetch_issue(self, repo_url, issue_number):
        """
        Fetch issue details.

        Returns:
        {
            title,
            body,
            state,
            labels,
            comments
        }
        """

        owner, repo = self.parse_repo_url(repo_url)

        issue_url = (
            f"{self.BASE_URL}/repos/"
            f"{owner}/{repo}/issues/{issue_number}"
        )

        response = requests.get(
            issue_url,
            headers=self.headers,
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(
                f"GitHub API Error: {response.status_code}"
            )

        issue = response.json()

        comments = []

        comments_url = issue["comments_url"]

        comment_response = requests.get(
            comments_url,
            headers=self.headers,
            timeout=30
        )

        if comment_response.status_code == 200:

            for comment in comment_response.json():

                comments.append(
                    comment["body"]
                )

        return {
            "title": issue["title"],
            "body": issue["body"],
            "state": issue["state"],
            "labels": [
                label["name"]
                for label in issue["labels"]
            ],
            "comments": comments
        }


if __name__ == "__main__":

    repo = input("Repository URL: ")

    issue_number = int(
        input("Issue Number: ")
    )

    fetcher = GitHubIssueFetcher()

    issue = fetcher.fetch_issue(
        repo,
        issue_number
    )

    print("\n========================")
    print("TITLE")
    print("========================")
    print(issue["title"])

    print("\n========================")
    print("DESCRIPTION")
    print("========================")
    print(issue["body"])

    print("\n========================")
    print("LABELS")
    print("========================")
    print(issue["labels"])

    print("\n========================")
    print("COMMENTS")
    print("========================")

    for i, comment in enumerate(
        issue["comments"],
        start=1
    ):
        print(f"\nComment {i}")
        print(comment)
