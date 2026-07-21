import os


def get_commit_hash(repo_path):

    cmd = f"cd {repo_path} && git rev-parse HEAD"

    return os.popen(cmd).read().strip()