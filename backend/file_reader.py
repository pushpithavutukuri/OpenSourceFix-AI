import os

SUPPORTED_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
]


def read_repository(repo_path):

    documents = []

    for root, dirs, files in os.walk(repo_path):

        dirs[:] = [
            d for d in dirs
            if d not in [".git", "__pycache__", "node_modules", "venv"]
        ]

        for file in files:

            if file.endswith(tuple(SUPPORTED_EXTENSIONS)):

                path = os.path.join(root, file)

                try:

                    with open(path, "r", encoding="utf-8") as f:

                        documents.append(
                            {
                                "path": path,
                                "content": f.read()
                            }
                        )

                except Exception:

                    pass

    return documents


if __name__ == "__main__":

    repo = "../repos/flask"

    docs = read_repository(repo)

    print(f"Total source files: {len(docs)}")

    for doc in docs[:5]:
        print(doc["path"])
