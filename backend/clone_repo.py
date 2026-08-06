from git import Repo
import os

def clone_repository(repo_url: str, repo_name: str):
    """
    Clone a GitHub repository into the repos folder.
    """

    destination = os.path.join("..", "repos", repo_name)

    if os.path.exists(destination):
        print(f"{repo_name} already exists.")
        return destination

    Repo.clone_from(repo_url, destination)
    print(f"Repository cloned to {destination}")

    return destination


if __name__ == "__main__":

    repo_url = "https://github.com/pallets/flask.git"

    clone_repository(repo_url, "flask")
