import os

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".java", ".rb", ".rs", ".cpp", ".c", ".h",
    ".cs", ".php", ".swift", ".kt",
}


def should_summarize(file_path, content):
    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path).lower()
    is_readme = basename in ("readme.md", "readme.txt", "readme.rst")
    if ext not in CODE_EXTENSIONS and not is_readme:
        return False
    return len(content.strip()) >= 50


def create_file_summary(file_path, content, ask_llm_fn):
    prompt = f"""You are a code analyst. Summarize this file in 5-8 concise lines.

Cover:
- What this file does
- Key functions, classes, or routes it defines
- Its role in the overall system

FILE: {file_path}

CONTENT:
{content[:3000]}

SUMMARY:"""

    try:
        summary = ask_llm_fn(prompt)
    except Exception as e:
        summary = f"(summary failed: {e})"

    return {
        "type": "file_summary",
        "name": os.path.basename(file_path),
        "file": file_path,
        "text": f"FILE SUMMARY [{file_path}]:\n{summary}",
        "calls": [],
        "line": 0,
        "parent_class": None,
    }
