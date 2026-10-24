"""Fail unless the only change in the working tree is inside the STATUS markers of README.md.

Run after readme_status.py. This is a second layer: the script already writes only that
section, and this check proves it from git's point of view.
"""
import subprocess
import sys

START = "<!-- STATUS:START -->"
END = "<!-- STATUS:END -->"


def outside(text):
    if text.count(START) != 1 or text.count(END) != 1:
        return None
    a = text.index(START) + len(START)
    return text[:a], text[text.index(END):]


def main():
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
    # Python's bytecode cache is a by-product of running the scripts, not a change.
    changed = [line[3:] for line in status.splitlines() if "__pycache__/" not in line[3:]]
    if not changed:
        print("No changes.")
        return
    if changed != ["README.md"]:
        print("FAIL: files other than README.md changed: %s" % changed)
        sys.exit(1)
    old = subprocess.run(["git", "show", "HEAD:README.md"], capture_output=True, text=True, check=True).stdout
    with open("README.md", encoding="utf-8") as handle:
        new = handle.read()
    before, after = outside(old), outside(new)
    if before is None or after is None:
        print("FAIL: STATUS markers missing or duplicated")
        sys.exit(1)
    if before != after:
        print("FAIL: README.md changed outside the STATUS markers")
        sys.exit(1)
    print("OK: only the STATUS section changed.")


if __name__ == "__main__":
    main()
