from app.scheduler.check_updates import repo_has_changed
from app.scheduler.update_repo import pull_latest_changes


def rebuild_repo(repo_path, repo_name):

    changed = repo_has_changed(
        repo_path,
        repo_name
    )

    if not changed:

        print("No changes")

        return

    print("Repo changed")

    pull_latest_changes(repo_path)

    print("Pulled latest changes")