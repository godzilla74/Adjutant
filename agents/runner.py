"""Sub-agent execution via the Claude Code CLI or Codex CLI."""

import asyncio
import glob
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 900  # seconds

_SUBAGENT_MODEL_FALLBACK = "claude-sonnet-4-6"
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")


def _get_subagent_model() -> str:
    """Return the Claude model to use for claude CLI sub-agents.

    Reads from env var first, then DB.  Always returns a Claude model —
    claude CLI sub-agents cannot use OpenAI models.
    """
    env_override = os.environ.get("AGENT_SUBAGENT_MODEL", "")
    if env_override and not env_override.startswith(_OPENAI_PREFIXES):
        return env_override
    try:
        from backend.db import get_agent_config
        model = get_agent_config().get("subagent_model", "")
        if model and not model.startswith(_OPENAI_PREFIXES):
            return model
    except Exception:
        pass
    return _SUBAGENT_MODEL_FALLBACK


def _get_openai_subagent_model() -> str:
    """Return the OpenAI model to use for codex CLI sub-agents."""
    try:
        from backend.db import get_agent_config
        model = get_agent_config().get("subagent_model", "")
        if model and model.startswith(_OPENAI_PREFIXES):
            return model
    except Exception:
        pass
    return "gpt-4o"


def _subagent_uses_openai() -> bool:
    """Return True if the configured subagent model is an OpenAI model."""
    env_override = os.environ.get("AGENT_SUBAGENT_MODEL", "")
    if env_override:
        return env_override.startswith(_OPENAI_PREFIXES)
    try:
        from backend.db import get_agent_config
        model = get_agent_config().get("subagent_model", "")
        if model:
            return model.startswith(_OPENAI_PREFIXES)
    except Exception:
        pass
    return False


async def _run_openai_subagent(task: str, system_prompt: str) -> str:
    """Run a sub-agent via Codex CLI or provider API when OpenAI is configured."""
    if _find_codex():
        return await _run_codex_cli(task, system_prompt)
    from backend.db import get_agent_config
    from backend.provider import make_provider
    cfg = get_agent_config()
    model = _get_openai_subagent_model()
    provider = make_provider(model)
    response = await provider.create(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": task}],
        max_tokens=4096,
    )
    return response.content[0].text


def _find_codex() -> str | None:
    """Return the path to the codex binary, searching PATH and common nvm locations."""
    found = shutil.which("codex")
    if found:
        return found
    home = str(Path.home())
    for pattern in [
        f"{home}/.nvm/versions/node/*/bin/codex",
        f"{home}/.local/bin/codex",
    ]:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


_RESEARCH_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary. "
    "Focus on accurate, well-sourced research. Cite sources. Be concise."
)

_GENERAL_SYSTEM = (
    "You are a specialized sub-agent. Complete your assigned task thoroughly "
    "and return a clear, organized summary."
)

_RESEARCH_TOOLS = "WebSearch,WebFetch"
_GENERAL_TOOLS = "Read,Glob,Grep,WebSearch,WebFetch"


async def _run_claude_cli(
    task: str,
    allowed_tools: str,
    system_prompt: str,
    timeout: int = AGENT_TIMEOUT,
    bypass_permissions: bool = False,
) -> str:
    cmd = [
        "claude", "-p", task,
        "--output-format", "json",
        "--system-prompt", system_prompt,
        "--model", _get_subagent_model(),
        "--no-session-persistence",
    ]
    if bypass_permissions:
        cmd += ["--permission-mode", "bypassPermissions"]
    else:
        cmd += ["--allowedTools", allowed_tools]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
            cwd=str(Path.home()),
        )
    except FileNotFoundError:
        return "Sub-agent failed: 'claude' executable not found on PATH."
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await proc.communicate()
        except (asyncio.TimeoutError, OSError):
            pass
        return f"Sub-agent timed out after {timeout}s."

    raw = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        logger.error("Sub-agent failed (exit %d): %s", proc.returncode, err or raw)
        return f"Sub-agent failed (exit {proc.returncode}): {err or raw}"

    try:
        data = json.loads(raw)
        return data.get("result", raw)
    except json.JSONDecodeError:
        return raw


async def _run_codex_cli(
    task: str,
    system_prompt: str,
    timeout: int = AGENT_TIMEOUT,
) -> str:
    """Run a task via the Codex CLI (codex exec).

    Codex has no --system-prompt flag, so instructions are prepended to the
    prompt text.  The final agent message is captured via -o/--output-last-message
    to avoid parsing the JSONL event stream.
    """
    codex_bin = _find_codex()
    if not codex_bin:
        return "Sub-agent failed: 'codex' executable not found."

    # Prepend system instructions — codex has no --system-prompt flag
    full_prompt = f"{system_prompt}\n\n---\n\n{task}" if system_prompt else task

    model = _get_openai_subagent_model()

    try:
        from backend.db import get_agent_config
        token = get_agent_config().get("openai_access_token", "")
    except Exception:
        token = ""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_path = f.name

    try:
        cmd = [
            codex_bin, "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "-m", model,
            "-o", output_path,
            full_prompt,
        ]
        env = {**os.environ}
        if token:
            env["OPENAI_API_KEY"] = token

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(Path.home()),
            )
        except FileNotFoundError:
            return "Sub-agent failed: 'codex' executable not found."

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.communicate()
            except (ProcessLookupError, asyncio.TimeoutError, OSError):
                pass
            return f"Sub-agent timed out after {timeout}s."

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raw = stdout.decode("utf-8", errors="replace").strip()
            logger.error("Codex sub-agent failed (exit %d): %s", proc.returncode, err or raw)
            return f"Sub-agent failed (exit {proc.returncode}): {err or raw}"

        try:
            result = Path(output_path).read_text(encoding="utf-8").strip()
            return result or stdout.decode("utf-8", errors="replace").strip()
        except OSError:
            return stdout.decode("utf-8", errors="replace").strip()

    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


async def run_research_agent(task: str) -> str:
    """Spawn a web-research-focused sub-agent (15-minute hard cap)."""
    if _subagent_uses_openai():
        return await _run_openai_subagent(task, _RESEARCH_SYSTEM)
    return await _run_claude_cli(task, _RESEARCH_TOOLS, _RESEARCH_SYSTEM)


async def run_general_agent(task: str) -> str:
    """Spawn a general-purpose sub-agent (15-minute hard cap)."""
    if _subagent_uses_openai():
        return await _run_openai_subagent(task, _GENERAL_SYSTEM)
    return await _run_claude_cli(task, _GENERAL_TOOLS, _GENERAL_SYSTEM)


async def run_extension_agent(task: str, system_prompt: str) -> str:
    """Run a generated tool extension's sub-task using the configured subagent provider."""
    if _subagent_uses_openai():
        if _find_codex():
            return await _run_codex_cli(task, system_prompt)
    else:
        if shutil.which("claude"):
            return await _run_claude_cli(task, "", system_prompt, bypass_permissions=True)
        if _find_codex():
            return await _run_codex_cli(task, system_prompt)

    # Provider API fallback
    from backend.db import get_agent_config
    from backend.provider import make_provider
    cfg = get_agent_config()
    model = cfg.get("subagent_model", _SUBAGENT_MODEL_FALLBACK)
    provider = make_provider(model)
    response = await provider.create(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": task}],
        max_tokens=4096,
    )
    return response.content[0].text
