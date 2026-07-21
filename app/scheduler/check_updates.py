from app.scheduler.repo_monitor import get_commit_hash
from app.storage.s3_client import S3Client



def repo_has_changed(repo_path, repo_name):

    s3 = S3Client()

    try:

        repo_info = s3.download_json(
            f"{repo_name}/repo_info.json"
        )

    except:

        return True

    old_commit = repo_info["last_commit"]

    current_commit = get_commit_hash(
        repo_path
    )

    return current_commit != old_commit