import os

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".mypy_cache", ".pytest_cache",
}

MAX_FILE_BYTES = 200_000  # skip files larger than 200 KB


def load_repo_files(repo_path):
    files_data = []

    for root, dirs, files in os.walk(repo_path):
        # Prune ignored directories in-place so os.walk skips them
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            path = os.path.join(root, file)

            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue

                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if len(content.strip()) > 0:
                    files_data.append({"file": path, "content": content})

            except (OSError, PermissionError):
                pass

    return files_data
