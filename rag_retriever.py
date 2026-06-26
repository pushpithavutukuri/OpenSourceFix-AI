import os


class RAGRetriever:
    def __init__(self):
        self.supported_extensions = [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx"
        ]

        self.ignore_dirs = {
            ".git",
            "venv",
            "node_modules",
            "__pycache__",
            "dist",
            "build"
        }

    def retrieve_files(self, repo_path, keyword):
        """
        Retrieve files containing the given keyword.

        Args:
            repo_path (str): Path to repository
            keyword (str): Search keyword

        Returns:
            list: Matching file paths
        """

        matched_files = []

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d for d in dirs
                if d not in self.ignore_dirs
            ]

            for file in files:

                if not any(
                    file.endswith(ext)
                    for ext in self.supported_extensions
                ):
                    continue

                file_path = os.path.join(root, file)

                try:
                    with open(
                        file_path,
                        "r",
                        encoding="utf-8"
                    ) as f:

                        content = f.read().lower()

                        if keyword.lower() in content:
                            matched_files.append(file_path)

                except Exception:
                    continue

        return matched_files

    def get_file_contents(self, file_paths):
        """
        Read contents of retrieved files.

        Args:
            file_paths (list): List of file paths

        Returns:
            dict: {file_path: content}
        """

        retrieved_content = {}

        for file_path in file_paths:

            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    retrieved_content[file_path] = f.read()

            except Exception:
                continue

        return retrieved_content


if __name__ == "__main__":

    retriever = RAGRetriever()

    keyword = "login"

    matching_files = retriever.retrieve_files(
        repo_path=".",
        keyword=keyword
    )

    print(f"\nFiles related to '{keyword}'\n")

    for file in matching_files:
        print(file)
