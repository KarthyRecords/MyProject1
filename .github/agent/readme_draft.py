"""Draft a first README from the repo's own files and write it to README.draft.md.

It never overwrites README.md. The workflow opens a pull request so you review it.
Usage: python readme_draft.py
"""
import fnmatch
import os
import subprocess
import sys

import llm
from readme_status import END, START, strip_fences
from safety import is_skipped, redact

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_PATTERNS = ["README.md", "Dockerfile*", "docker-compose*", "Makefile", "requirements*.txt", "package.json",
                "*.tf", "k8s/*", "k8s/*/*", ".github/workflows/*.yml", "docs/*.md"]


def tracked_files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if not is_skipped(p)]


def pick_key_files(files, per_file=3000, total=20000):
    chosen, used = [], 0
    for pattern in KEY_PATTERNS:
        for path in files:
            if path in [c[0] for c in chosen] or not fnmatch.fnmatch(path, pattern):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    body = handle.read(per_file)
            except (OSError, UnicodeDecodeError):
                continue
            if used + len(body) > total:
                return chosen
            chosen.append((path, body))
            used += len(body)
    return chosen


def ensure_markers(text):
    if START in text and END in text:
        return text
    return text.rstrip() + "\n\n## Status\n\n" + START + "\n" + END + "\n"


def main():
    files = tracked_files()
    parts = ["<file_list>\n" + "\n".join(files[:300]) + "\n</file_list>"]
    for path, body in pick_key_files(files):
        parts.append('<file path="%s">\n%s\n</file>' % (path, body))
    with open(os.path.join(HERE, "prompts", "readme_draft.md"), encoding="utf-8") as handle:
        system = handle.read()
    user = redact(llm.clip("\n\n".join(parts))[0])
    reply = ensure_markers(strip_fences(llm.chat(system, user, max_tokens=2500, temperature=0.3)))
    with open("README.draft.md", "w", encoding="utf-8") as out:
        out.write(reply + "\n")
    print("Wrote README.draft.md (%d characters). Review it before using it." % len(reply))


if __name__ == "__main__":
    try:
        main()
    except llm.LLMError as err:
        print("LLM call failed: %s" % err)
        sys.exit(1)
