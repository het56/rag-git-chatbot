import os
from app.scheduler.rebuild import rebuild_repo

REPOS_ROOT = "data/repos"

for repo_name in os.listdir(REPOS_ROOT):

    repo_path = os.path.join(
        REPOS_ROOT,
        repo_name
    )

    rebuild_repo(
        repo_path,
        repo_name
    )