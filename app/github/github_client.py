import requests


def get_latest_commit(repo_url):

    owner_repo = repo_url.replace(
        "https://github.com/",
        ""
    ).replace(".git", "")

    url = f"https://api.github.com/repos/{owner_repo}/commits"

    try:

        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return None

        commits = response.json()

        return commits[0]["sha"]

    except Exception as e:
        print("GitHub error:", e)
        return None