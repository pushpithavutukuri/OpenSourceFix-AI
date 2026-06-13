from repository_analysis.repo_loader import clone_repository
from repository_analysis.file_scanner import scan_repository

repo_url = "https://github.com/tiangolo/fastapi"

repo_path = clone_repository(repo_url)

summary = scan_repository(repo_path)

print(summary)
