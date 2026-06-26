from github_issue_fetcher import GitHubIssueFetcher


fetcher = GitHubIssueFetcher()

issue = fetcher.fetch_issue(
    "microsoft",
    "vscode",
    100
)

print("\nIssue Information\n")
print(issue)
