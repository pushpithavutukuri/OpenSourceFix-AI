import ast


def extract_python_structure(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        functions = []
        classes = []

        for node in ast.walk(tree):

            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)

            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

        return {
            "functions": functions,
            "classes": classes
        }

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None
