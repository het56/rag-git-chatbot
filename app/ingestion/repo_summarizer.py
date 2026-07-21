import os


def create_repo_summary(repo_path, file_summaries, tree, ask_llm_fn):
    summaries_text = "\n\n".join(
        fs["text"] for fs in file_summaries[:25]
    )

    prompt = f"""You are analyzing a GitHub repository.

DIRECTORY STRUCTURE:
{tree[:2000]}

FILE SUMMARIES:
{summaries_text[:5000]}

Write a comprehensive repository overview covering:
- What this project does (purpose and goal)
- Main modules and what each one is responsible for
- Key technologies and frameworks used
- How data flows through the system end-to-end
- Entry points, main APIs, or CLI commands

REPOSITORY OVERVIEW:"""

    try:
        summary = ask_llm_fn(prompt)
    except Exception as e:
        summary = f"(repo summary failed: {e})"

    return {
        "type": "repo_summary",
        "name": "repository_overview",
        "file": os.path.basename(os.path.abspath(repo_path)),
        "text": f"REPOSITORY OVERVIEW:\n{summary}",
        "calls": [],
        "line": 0,
        "parent_class": None,
    }
