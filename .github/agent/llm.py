"""Provider-neutral chat client. Standard library only.

Speaks the OpenAI-compatible /chat/completions format, which GitHub Models, Groq,
Cerebras, OpenRouter, Mistral and Gemini's compatibility endpoint all accept.
Switch provider by changing three settings, never the code:

  LLM_BASE_URL   default https://models.github.ai/inference
  LLM_API_KEY    default: the GITHUB_TOKEN already present in Actions
  LLM_MODEL      default openai/gpt-4o  (check the GitHub Models catalog for current names)
"""
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://models.github.ai/inference"
DEFAULT_MODEL = "openai/gpt-4o"
MAX_INPUT_CHARS = 24000

sleep = time.sleep  # replaced in tests


class LLMError(RuntimeError):
    pass


def settings():
    base = (os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    key = os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN") or ""
    model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
    return base, key, model


def clip(text, limit=MAX_INPUT_CHARS):
    """Free tiers have small context windows, so cut long input and say so."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n[... truncated ...]", True


def chat(system, user, max_tokens=1200, temperature=0.2, retries=3, timeout=60):
    base, key, model = settings()
    if not key:
        raise LLMError("no API key: set LLM_API_KEY, or run in Actions where GITHUB_TOKEN exists")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    request = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + key,
            # Some providers sit behind Cloudflare, which blocks Python's default
            # "Python-urllib" User-Agent with HTTP 403 "error code: 1010".
            "User-Agent": "repo-agent/1.0 (+https://github.com)",
        },
    )
    delay = 5.0
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                status = getattr(response, "status", "?")
                final_url = getattr(response, "url", base)
            try:
                data = json.loads(raw)
            except ValueError:
                snippet = raw[:200].decode("utf-8", "replace")
                raise LLMError(
                    "provider returned non-JSON (HTTP %s from %s, %d bytes): %r"
                    % (status, final_url, len(raw), snippet)
                ) from None
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as err:
            retryable = err.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == retries:
                detail = err.read()[:200].decode("utf-8", "replace")
                raise LLMError("HTTP %s from provider: %s" % (err.code, detail)) from None
            try:
                wait = float(err.headers.get("Retry-After") or delay)
            except ValueError:
                wait = delay
            sleep(min(wait, 60))
            delay *= 2
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == retries:
                raise LLMError("could not reach provider: %s" % err) from None
            sleep(delay)
            delay *= 2
        except (KeyError, IndexError, ValueError) as err:
            raise LLMError("unexpected response shape from provider: %r" % err) from None
    raise LLMError("gave up after %d attempts" % retries)
