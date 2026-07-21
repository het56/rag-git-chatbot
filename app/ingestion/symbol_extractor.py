import ast

def extract_symbols(file_path, code):

    try:
        tree = ast.parse(code)
    except:
        return {"functions": [], "classes": []}

    functions = []
    classes = []

    for node in ast.walk(tree):

        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)

        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

    return {
        "file": file_path,
        "functions": functions,
        "classes": classes
    }