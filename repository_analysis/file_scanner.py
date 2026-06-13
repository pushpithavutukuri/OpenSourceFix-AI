import os

def scan_repository(repo_path):
    total_files = 0
    python_files = 0
    folders = 0

    for root, dirs, files in os.walk(repo_path):
        folders += len(dirs)
        total_files += len(files)

        for file in files:
            if file.endswith(".py"):
                python_files += 1

    return {
        "total_files": total_files,
        "python_files": python_files,
        "folders": folders
    }
