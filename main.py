from repository_analysis.dependency_graph import build_dependency_graph

repo_path = "repos/fastapi"

graph = build_dependency_graph(repo_path)

for file, imports in list(graph.items())[:5]:

    print("\nFile:")
    print(file)

    print("Imports:")

    for imp in imports:
        print(f"  - {imp}")
