# extensions/browser_task.py
"""General-purpose headed browser automation tool.

Uses browser-use to run an AI agent in a VISIBLE Chromium window.
The agent follows natural language instructions and returns a structured result.

Install once:
    pip install browser-use langchain-anthropic
    playwright install chromium
"""

import json
import os
import sys

# Resolve project root so we can import agents.runner for the configured model
_ext_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_ext_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

TOOL_DEFINITION = {
    "name": "browser_task",
    "description": (
        "Run a task in a VISIBLE headed browser using an AI agent. "
        "Use for form filling, web signups, data extraction, or any UI automation. "
        "The agent stops and reports back if it hits a verification wall "
        "(phone/email/CAPTCHA). Returns JSON with status and result. "
        "Takes 1-5 minutes depending on complexity."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Full natural language task for the browser agent",
            },
            "sensitive_data": {
                "type": "object",
                "description": (
                    "Key→value map of secrets referenced as {key} placeholders in the task. "
                    "Values are never logged or sent to the LLM. "
                    'e.g. {"email": "x@y.com", "password": "abc123"}'
                ),
            },
            "max_steps": {
                "type": "integer",
                "description": "Maximum browser steps before stopping (default: 40)",
            },
        },
        "required": ["task"],
    },
}


async def execute(inputs: dict) -> str:
    task: str = inputs.get("task", "")
    sensitive_data: dict = inputs.get("sensitive_data") or {}
    max_steps: int = inputs.get("max_steps", 40)

    # ── Import browser-use (fail gracefully if not installed) ─────────────────
    try:
        from browser_use import Agent
    except ImportError:
        return json.dumps({
            "status": "error",
            "result": (
                "browser-use is not installed. Run:\n"
                "  pip install browser-use langchain-anthropic\n"
                "  playwright install chromium"
            ),
        })

    # ── Build LLM (try browser-use's built-in first, fall back to langchain) ──
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    llm = _make_llm(api_key)
    if llm is None:
        return json.dumps({
            "status": "error",
            "result": "Could not initialize LLM. Ensure ANTHROPIC_API_KEY is set and langchain-anthropic or browser-use's Anthropic wrapper is installed.",
        })

    # ── Build browser (visible) ───────────────────────────────────────────────
    browser = _make_browser()

    # ── Wrap sensitive data as {placeholder} references in the task ───────────
    # browser-use injects sensitive_data so values never reach the LLM verbatim
    agent_kwargs: dict = dict(
        task=task,
        llm=llm,
        max_failures=3,
    )
    if browser is not None:
        # Newer API uses browser_session / browser
        try:
            agent_kwargs["browser_session"] = browser
        except Exception:
            agent_kwargs["browser"] = browser

    if sensitive_data:
        agent_kwargs["sensitive_data"] = sensitive_data

    # ── Run ───────────────────────────────────────────────────────────────────
    try:
        agent = Agent(**agent_kwargs)
        history = await agent.run(max_steps=max_steps)

        # Extract final result — handle both string and history-object APIs
        if hasattr(history, "final_result"):
            final = history.final_result() or ""
        else:
            final = str(history)

        # Check if the agent flagged a verification stop in its output
        lower = final.lower()
        verification_phrases = [
            "verification_required", "verification required",
            "phone verification", "email verification",
            "enter the code", "confirm your email",
            "captcha", "are you a robot",
        ]
        if any(p in lower for p in verification_phrases):
            status = "needs_verification"
        else:
            status = "success"

        return json.dumps({"status": status, "result": final})

    except Exception as exc:
        err = str(exc)
        # Treat browser-close / interrupted as a soft stop
        if any(kw in err.lower() for kw in ("interrupt", "closed", "disconnect")):
            return json.dumps({"status": "needs_verification", "result": err})
        return json.dumps({"status": "error", "result": err})

    finally:
        # Always close the browser to avoid zombie Chromium processes
        if browser is not None:
            try:
                close = getattr(browser, "stop", None) or getattr(browser, "close", None)
                if close:
                    import asyncio, inspect
                    if inspect.iscoroutinefunction(close):
                        await close()
                    else:
                        close()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_browser_model() -> str:
    """Return the configured sub-agent model, falling back to sonnet."""
    try:
        from agents.runner import _get_subagent_model
        return _get_subagent_model()
    except Exception:
        return "claude-sonnet-4-6"


def _make_llm(api_key: str):
    """Try browser-use's built-in Anthropic wrapper first, then langchain."""
    model = _get_browser_model()
    # Attempt 1: browser-use internal (0.12.x+)
    for path in (
        "browser_use.llm.anthropic.chat.ChatAnthropic",
        "browser_use.agent.views.ChatAnthropic",
    ):
        try:
            module_path, cls_name = path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            return cls(model=model, api_key=api_key)
        except Exception:
            pass

    # Attempt 2: langchain-anthropic
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key)
    except ImportError:
        pass

    return None


def _make_browser():
    """Build a headed browser session, tolerating API differences across versions."""
    # Attempt 1: BrowserSession (newer API)
    try:
        from browser_use import BrowserSession
        return BrowserSession(headless=False)
    except (ImportError, TypeError):
        pass

    # Attempt 2: Browser + BrowserConfig (older API)
    try:
        from browser_use.browser.browser import Browser, BrowserConfig
        return Browser(config=BrowserConfig(headless=False))
    except (ImportError, TypeError):
        pass

    # Fall back to default (may be headless, but won't crash)
    return None
