"""Review a pull request and post (or update) one comment on it.

It only comments. It never pushes code, approves, or merges.
Environment: GITHUB_REPOSITORY, GITHUB_TOKEN, and PR_NUMBER (or GITHUB_EVENT_PATH).
"""
import json
import os
import re
import sys

import gh
import llm
from safety import is_skipped, redact

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = "<!-- repo-agent-review -->"


def filter_diff(diff):
    """Drop sections for files that must not be sent (secrets, lock files, state)."""
    sections = re.split(r"(?m)^(?=diff --git )", diff)
    kept = []
    for section in sections:
        match = re.match(r"diff --git a/(\S+) b/", section)
        if match and is_skipped(match.group(1)):
            continue
        kept.append(section)
    return "".join(kept)


def pr_number():
    if os.environ.get("PR_NUMBER"):
        return int(os.environ["PR_NUMBER"])
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            return int(json.load(handle)["pull_request"]["number"])
    raise SystemExit("set PR_NUMBER or run from a pull_request event")


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    number = pr_number()
    info = gh.pr_info(repo, number)
    diff, truncated = llm.clip(redact(filter_diff(gh.pr_diff(repo, number))))
    with open(os.path.join(HERE, "prompts", "pr_review.md"), encoding="utf-8") as handle:
        system = handle.read()
    user = "<pr_title>\n%s\n</pr_title>\n\n<pr_description>\n%s\n</pr_description>\n\n<diff>\n%s\n</diff>" % (
        info.get("title", ""), redact((info.get("body") or "")[:2000]), diff)
    review = llm.chat(system, user, max_tokens=1500)[:6000]
    _base, _key, model = llm.settings()
    note = "\n\n_Automated review by %s. It can be wrong, so treat it as a second pair of eyes.%s_" % (
        model, " The diff was too long and was cut, so later files were not reviewed." if truncated else "")
    body = "### AI review\n\n" + review + note + "\n\n" + MARKER
    try:
        print("Comment %s." % gh.upsert_comment(repo, number, body, MARKER))
    except gh.GitHubError as err:
        # Pull requests from forks get a read-only token, so print the review instead.
        print("Could not post the comment (%s). Review follows:\n\n%s" % (err, body))


if __name__ == "__main__":
    try:
        main()
    except (llm.LLMError, gh.GitHubError) as err:
        print("Review skipped: %s" % err)
        sys.exit(1)
