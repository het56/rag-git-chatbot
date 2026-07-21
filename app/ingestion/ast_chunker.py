import ast

ROUTE_DECORATORS = {
    "app.get", "app.post", "app.put", "app.delete", "app.patch",
    "router.get", "router.post", "router.put", "router.delete", "router.patch",
    "app.route", "blueprint.route", "get", "post", "put", "delete", "patch",
}


def _decorator_names(node):
    names = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            func = dec.func
        else:
            func = dec

        if isinstance(func, ast.Attribute):
            obj = func.value.id if isinstance(func.value, ast.Name) else ""
            names.append(f"{obj}.{func.attr}" if obj else func.attr)
        elif isinstance(func, ast.Name):
            names.append(func.id)
    return names


def _called_names(node):
    calls = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.add(child.func.attr)
    return sorted(calls)


def _walk_with_class(node, parent_class=None):
    """Yield (node, parent_class_name) — tracks the nearest enclosing class."""
    yield node, parent_class
    next_class = node.name if isinstance(node, ast.ClassDef) else parent_class
    for child in ast.iter_child_nodes(node):
        yield from _walk_with_class(child, next_class)


def chunk_python_file(file_path, content):
    chunks = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return chunks

    lines = content.splitlines()

    for node, parent_class in _walk_with_class(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            code = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            decs = _decorator_names(node)
            is_route = any(d in ROUTE_DECORATORS for d in decs)
            calls = _called_names(node)

            header = f"# Method of class {parent_class}\n" if parent_class else ""

            chunks.append({
                "type": "route" if is_route else "function",
                "name": node.name,
                "file": file_path,
                "text": header + code,
                "calls": calls,
                "decorators": decs,
                "line": node.lineno,
                "parent_class": parent_class,
            })

        elif isinstance(node, ast.ClassDef):
            code = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            methods = [
                n.name for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            chunks.append({
                "type": "class",
                "name": node.name,
                "file": file_path,
                "text": code,
                "methods": methods,
                "calls": [],
                "line": node.lineno,
                "parent_class": parent_class,
            })

    return chunks
