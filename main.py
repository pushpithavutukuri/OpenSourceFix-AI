from repository_analysis.code_parser import extract_python_structure

file_path = "repos/fastapi/fastapi/applications.py"

result = extract_python_structure(file_path)

print("\nCode Structure\n")
print(result)
