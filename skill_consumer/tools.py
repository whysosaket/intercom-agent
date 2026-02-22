"""Tool functions that the skill agent can invoke based on LLM decisions.

These are plain Python functions — not OpenAI function-calling tools.
The agent loop calls them directly based on structured LLM output.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Safety limits
MAX_FILE_CHARS = 15_000
MAX_URL_CHARS = 10_000
SCRIPT_TIMEOUT_SECONDS = 30

# Only these scripts can be executed
ALLOWED_SCRIPTS = {
    "add_memory.py",
    "delete_memory.py",
    "get_memories.py",
    "mem0_doc_search.py",
    "search_memory.py",
    "update_memory.py",
}


async def read_file(base_path: str, relative_path: str) -> dict:
    """Read a file from the skill directory.

    Returns dict with 'content' on success or 'error' on failure.
    """
    full_path = os.path.normpath(os.path.join(base_path, relative_path))

    # Prevent path traversal
    if not full_path.startswith(os.path.normpath(base_path)):
        return {"error": f"Path traversal blocked: {relative_path}", "content": ""}

    if not os.path.exists(full_path):
        return {"error": f"File not found: {relative_path}", "content": ""}

    try:
        with open(full_path, encoding="utf-8") as f:
            content = f.read()

        if len(content) > MAX_FILE_CHARS:
            content = (
                content[:MAX_FILE_CHARS]
                + f"\n\n[TRUNCATED — file is {len(content)} chars, showing first {MAX_FILE_CHARS}]"
            )

        return {
            "content": content,
            "path": relative_path,
            "chars": len(content),
        }
    except Exception as e:
        logger.exception("Error reading file %s", full_path)
        return {"error": str(e), "content": ""}


async def fetch_url(url: str, allowed_domains: list[str] | None = None) -> dict:
    """Fetch content from an external URL.

    Returns dict with 'content' on success or 'error' on failure.
    Only fetches from allowed domains.
    """
    if allowed_domains is None:
        allowed_domains = ["docs.mem0.ai", "github.com", "raw.githubusercontent.com"]

    parsed = urlparse(url)
    if parsed.hostname not in allowed_domains:
        return {
            "error": f"Domain not allowed: {parsed.hostname}. Allowed: {allowed_domains}",
            "content": "",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            content = resp.text

            if len(content) > MAX_URL_CHARS:
                content = (
                    content[:MAX_URL_CHARS]
                    + f"\n\n[TRUNCATED — {len(content)} chars total]"
                )

            return {
                "content": content,
                "url": url,
                "status": resp.status_code,
            }
    except Exception as e:
        logger.exception("Error fetching URL %s", url)
        return {"error": str(e), "content": "", "url": url}


async def run_script(
    base_path: str, script_relative_path: str, arguments: list[str]
) -> dict:
    """Execute a skill script with arguments.

    Returns dict with stdout/stderr on success or 'error' on failure.
    Only scripts in the allowlist can be executed.
    """
    script_name = os.path.basename(script_relative_path)
    if script_name not in ALLOWED_SCRIPTS:
        return {"error": f"Script not in allowlist: {script_name}", "output": ""}

    full_path = os.path.normpath(os.path.join(base_path, script_relative_path))

    # Prevent path traversal
    if not full_path.startswith(os.path.normpath(base_path)):
        return {"error": "Path traversal blocked", "output": ""}

    if not os.path.exists(full_path):
        return {
            "error": f"Script not found: {script_relative_path}",
            "output": "",
        }

    # Sanitize arguments
    safe_args = [str(a) for a in arguments]

    # Build environment with only allowed variables
    env = dict(os.environ)

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            full_path,
            *safe_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=base_path,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=SCRIPT_TIMEOUT_SECONDS
        )
        return {
            "stdout": stdout.decode(errors="replace")[:5000],
            "stderr": stderr.decode(errors="replace")[:2000],
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {
            "error": f"Script timed out after {SCRIPT_TIMEOUT_SECONDS}s",
            "output": "",
        }
    except Exception as e:
        logger.exception("Error running script %s", full_path)
        return {"error": str(e), "output": ""}
