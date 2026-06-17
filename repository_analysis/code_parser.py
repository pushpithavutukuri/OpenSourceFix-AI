import ast


def extract_python_structure(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        functions = set()
        classes = set()
        imports = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.FunctionDef):
                functions.add(node.name)

            elif isinstance(node, ast.ClassDef):
                classes.add(node.name)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        return {
            "functions": sorted(list(functions)),
            "classes": sorted(list(classes)),
            "imports": sorted(list(imports))
        }

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None
