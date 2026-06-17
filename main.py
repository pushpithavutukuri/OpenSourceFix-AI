from repository_analysis.code_parser import extract_python_structure

file_path = "repos/fastapi/fastapi/applications.py"

result = extract_python_structure(file_path)

print("\nFunctions:")
for func in result["functions"]:
    print(f"  - {func}")

print("\nClasses:")
for cls in result["classes"]:
    print(f"  - {cls}")

print("\nImports:")
for imp in result["imports"]:
    print(f"  - {imp}")
