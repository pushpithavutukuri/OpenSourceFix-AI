import os


class RepositoryAnalyzer:
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

    def analyze_repository(self, repo_path):
        code_files = []

        for root, dirs, files in os.walk(repo_path):

            # Ignore unnecessary folders
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            for file in files:
                if any(file.endswith(ext) for ext in self.supported_extensions):
                    file_path = os.path.join(root, file)
                    code_files.append(file_path)

        return code_files

    def generate_summary(self, repo_path):
        files = self.analyze_repository(repo_path)

        summary = {
            "total_code_files": len(files),
            "python_files": 0,
            "javascript_files": 0,
            "typescript_files": 0,
            "files": files
        }

        for file in files:
            if file.endswith(".py"):
                summary["python_files"] += 1

            elif file.endswith((".js", ".jsx")):
                summary["javascript_files"] += 1

            elif file.endswith((".ts", ".tsx")):
                summary["typescript_files"] += 1

        return summary


if __name__ == "__main__":
    analyzer = RepositoryAnalyzer()

    repo_path = "."

    summary = analyzer.generate_summary(repo_path)

    print("\nRepository Summary")
    print("-" * 40)
    print(f"Total Code Files: {summary['total_code_files']}")
    print(f"Python Files: {summary['python_files']}")
    print(f"JavaScript Files: {summary['javascript_files']}")
    print(f"TypeScript Files: {summary['typescript_files']}")

    print("\nFiles Found:")
    for file in summary["files"]:
        print(file)
