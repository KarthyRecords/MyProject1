"""Keep sensitive material out of what is sent to any LLM provider."""
import os
import re

_SKIP_SUFFIXES = (".tfvars", ".pem", ".key", ".p12", ".pfx", ".tfstate", ".lock", ".min.js")
_SKIP_NAMES = ("package-lock.json",)

_REDACTIONS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED AWS KEY]"),
    (re.compile(r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED GITHUB TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED API KEY]"),
    (re.compile(r"arn:aws:([a-z0-9-]+)::\d{12}:"), r"arn:aws:\1::<ACCOUNT_ID>:"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api_key)\b(\s*[:=]\s*)(\S+)"), r"\1\2[REDACTED]"),
]


def is_skipped(path):
    """True for files that must never be read into a prompt."""
    low = path.lower()
    base = os.path.basename(low)
    if base.startswith(".env") or "id_rsa" in base or "secret" in low or ".tfstate" in base:
        return True
    return base in _SKIP_NAMES or low.endswith(_SKIP_SUFFIXES)


def redact(text):
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text
