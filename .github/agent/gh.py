"""Tiny GitHub REST helper. Standard library only."""
import json
import os
import urllib.error
import urllib.request

DIFF_ACCEPT = "application/vnd.github.v3.diff"
JSON_ACCEPT = "application/vnd.github+json"


class GitHubError(RuntimeError):
    def __init__(self, status, message):
        super().__init__("GitHub API %s: %s" % (status, message))
        self.status = status


def call(method, path, payload=None, accept=JSON_ACCEPT):
    api = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(api + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        raise GitHubError(err.code, err.read()[:200].decode("utf-8", "replace")) from None
    except urllib.error.URLError as err:
        raise GitHubError(0, str(err)) from None


def merged_prs(repo, limit=15):
    """Titles of recently merged pull requests (data only, never instructions)."""
    raw = call("GET", "/repos/%s/pulls?state=closed&sort=updated&direction=desc&per_page=30" % repo)
    merged = [p for p in json.loads(raw) if p.get("merged_at")]
    return ["#%s %s" % (p["number"], p["title"]) for p in merged[:limit]]


def pr_info(repo, number):
    return json.loads(call("GET", "/repos/%s/pulls/%s" % (repo, number)))


def pr_diff(repo, number):
    return call("GET", "/repos/%s/pulls/%s" % (repo, number), accept=DIFF_ACCEPT)


def upsert_comment(repo, number, body, marker):
    """Update the agent's earlier comment on this PR if there is one, else add a new one."""
    existing = json.loads(call("GET", "/repos/%s/issues/%s/comments?per_page=100" % (repo, number)))
    for comment in existing:
        if marker in comment.get("body", ""):
            call("PATCH", "/repos/%s/issues/comments/%s" % (repo, comment["id"]), {"body": body})
            return "updated"
    call("POST", "/repos/%s/issues/%s/comments" % (repo, number), {"body": body})
    return "created"
