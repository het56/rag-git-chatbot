import os

def build_tree(repo_path):
    tree = []

    for root, dirs, files in os.walk(repo_path):

        level = root.replace(repo_path, "").count(os.sep)
        indent = "  " * level

        tree.append(f"{indent}{os.path.basename(root)}/")

        for file in files:
            tree.append(f"{indent}  {file}")

    return "\n".join(tree)