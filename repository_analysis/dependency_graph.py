from repository_analysis.code_parser import extract_python_structure
import os


def build_dependency_graph(repo_path):
    graph = {}

    for root, _, files in os.walk(repo_path):

        for file in files:

            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)

            result = extract_python_structure(file_path)

            if result is None:
                continue

            graph[file_path] = result["imports"]

    return graph
