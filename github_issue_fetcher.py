import requests


class GitHubIssueFetcher:

    def __init__(self):
        self.base_url = "https://api.github.com"

    def fetch_issue(self, owner, repo, issue_number):

        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"

        response = requests.get(url)

        if response.status_code != 200:
            raise Exception(
                f"Failed to fetch issue. Status code: {response.status_code}"
            )

        data = response.json()

        return {
            "title": data["title"],
            "body": data["body"],
            "state": data["state"],
            "author": data["user"]["login"],
            "url": data["html_url"]
        }


if __name__ == "__main__":

    fetcher = GitHubIssueFetcher()

    issue = fetcher.fetch_issue(
        "microsoft",
        "vscode",
        100
    )

    print(issue)
