import os


def pull_latest_changes(repo_path):

    os.system(
        f"cd {repo_path} && git pull"
    )