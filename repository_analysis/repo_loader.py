from git import Repo
import os

def clone_repository(repo_url, destination="repos"):
    os.makedirs(destination, exist_ok=True)

    repo_name = repo_url.split("/")[-1]

    local_path = os.path.join(destination, repo_name)

    if os.path.exists(local_path):
        print(f"Repository already exists: {local_path}")
        return local_path

    Repo.clone_from(repo_url, local_path)

    print(f"Cloned successfully: {local_path}")

    return local_path
