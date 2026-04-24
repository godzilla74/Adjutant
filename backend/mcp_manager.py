# backend/mcp_manager.py
"""Manages persistent connections to local (stdio) MCP servers."""
import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self) -> None:
        # server_id → ClientSession (mcp library session object)
        self._sessions: dict[int, object] = {}
        # namespaced_tool_name → (server_id, original_tool_name)
        self._tool_to_server: dict[str, tuple[int, str]] = {}
        # namespaced_tool_name → Anthropic-format tool definition dict
        self._tool_defs: dict[str, dict] = {}
        # server_id → server_name (for reverse lookup)
        self._server_id_to_name: dict[int, str] = {}
        # server_id → asyncio.Task
        self._tasks: dict[int, asyncio.Task] = {}
        # server_id → asyncio.Event (set to signal shutdown)
        self._stop_events: dict[int, asyncio.Event] = {}
        self._running = False

    # ── Public interface ──────────────────────────────────────────────────────

    async def start(self, configs: list[dict]) -> None:
        """Start all enabled stdio MCP server connections from a list of DB rows."""
        self._running = True
        for config in configs:
            if config.get("type") == "stdio" and config.get("enabled"):
                await self._start_server(config)

    async def stop(self) -> None:
        """Gracefully stop all connections."""
        self._running = False
        for event in self._stop_events.values():
            event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def add_server(self, config: dict) -> None:
        """Start a new stdio server at runtime (called after Hannah adds one)."""
        if config.get("type") == "stdio" and config.get("enabled"):
            await self._start_server(config)

    async def remove_server(self, server_id: int) -> None:
        """Stop a server and remove its tools."""
        event = self._stop_events.pop(server_id, None)
        if event:
            event.set()
        task = self._tasks.pop(server_id, None)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._sessions.pop(server_id, None)
        self._clear_tools(server_id)

    def get_tools(self) -> list[dict]:
        """Return all discovered stdio tool definitions in Anthropic tool format."""
        return list(self._tool_defs.values())

    def get_connected_server_names(self) -> set[str]:
        """Return names of currently connected stdio MCP servers."""
        return {
            name
            for sid, name in self._server_id_to_name.items()
            if sid in self._sessions
        }

    def get_tools_for_server(self, server_name: str) -> list[dict]:
        """Return all tool definitions registered for a specific server name."""
        server_ids = {
            sid for sid, name in self._server_id_to_name.items()
            if name == server_name
        }
        return [
            defn
            for ns_name, defn in self._tool_defs.items()
            if self._tool_to_server.get(ns_name, (None,))[0] in server_ids
        ]

    async def execute_tool(self, namespaced_name: str, tool_input: dict) -> str:
        """Execute a stdio MCP tool. Called from the agent loop for mcp__ tool names."""
        if namespaced_name not in self._tool_to_server:
            return f"Unknown MCP tool: {namespaced_name}"
        server_id, original_name = self._tool_to_server[namespaced_name]
        session = self._sessions.get(server_id)
        if session is None:
            return "MCP server is not currently connected."
        try:
            result = await session.call_tool(original_name, tool_input)
            text = "\n".join(
                c.text for c in result.content if hasattr(c, "text")
            )
            return text or "(no output)"
        except Exception as e:
            logger.warning("MCP tool call failed for %s: %s", namespaced_name, e)
            return f"MCP tool error: {e}"

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _start_server(self, config: dict) -> None:
        server_id = config["id"]
        stop_event = asyncio.Event()
        self._stop_events[server_id] = stop_event
        task = asyncio.create_task(
            self._run_server(config, stop_event),
            name=f"mcp-{config['name']}",
        )
        self._tasks[server_id] = task

    async def _run_server(self, config: dict, stop_event: asyncio.Event) -> None:
        """Keep a single stdio MCP server running, reconnecting with backoff on failure."""
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession, StdioServerParameters

        server_id = config["id"]
        args_list: list[str] = json.loads(config["args"] or "[]")
        env_overlay: dict = json.loads(config["env"] or "{}")
        env_vars = {**os.environ, **env_overlay}
        delay = 1

        while not stop_event.is_set():
            try:
                params = StdioServerParameters(
                    command=config["command"],
                    args=args_list,
                    env=env_vars,
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        self._sessions[server_id] = session
                        self._register_tools(server_id, config["name"], result.tools)
                        delay = 1  # reset backoff after successful connection
                        logger.info(
                            "MCP server '%s' connected (%d tools)",
                            config["name"], len(result.tools),
                        )
                        await stop_event.wait()  # block until shutdown or error
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "MCP server '%s' error: %s — retrying in %ds",
                    config["name"], e, delay,
                )
                self._sessions.pop(server_id, None)
                self._clear_tools(server_id)
                if not stop_event.is_set():
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30)

        self._sessions.pop(server_id, None)
        self._clear_tools(server_id)

    def _register_tools(self, server_id: int, server_name: str, tools: list) -> None:
        prefix = server_name.replace(" ", "_").lower()
        self._server_id_to_name[server_id] = server_name
        for tool in tools:
            ns_name = f"mcp__{prefix}__{tool.name}"
            self._tool_to_server[ns_name] = (server_id, tool.name)
            self._tool_defs[ns_name] = {
                "name": ns_name,
                "description": tool.description or f"Tool from {server_name} MCP server",
                "input_schema": (
                    tool.inputSchema
                    if tool.inputSchema
                    else {"type": "object", "properties": {}}
                ),
            }

    def _clear_tools(self, server_id: int) -> None:
        to_remove = [k for k, (sid, _) in self._tool_to_server.items() if sid == server_id]
        for k in to_remove:
            self._tool_to_server.pop(k, None)
            self._tool_defs.pop(k, None)
        self._server_id_to_name.pop(server_id, None)


async def fetch_remote_tools(url: str, headers: dict) -> list[dict]:
    """Discover tools from a remote MCP server on demand.

    Tries Streamable HTTP first (MCP 2025-03-26+), falls back to legacy SSE.
    """
    from mcp import ClientSession

    def _parse_tools(result) -> list[dict]:
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema if tool.inputSchema else {
                    "type": "object", "properties": {}
                },
            }
            for tool in result.tools
        ]

    h = headers or None

    # Try Streamable HTTP first (newer transport)
    try:
        from mcp.client.streamable_http import streamable_http_client
        async with asyncio.timeout(15):
            async with streamable_http_client(url, headers=h) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return _parse_tools(await session.list_tools())
    except Exception as e:
        logger.debug("Streamable HTTP failed for %s (%s), trying SSE", url, e)

    # Fall back to legacy SSE transport
    try:
        from mcp.client.sse import sse_client
        async with asyncio.timeout(10):
            async with sse_client(url, headers=h) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return _parse_tools(await session.list_tools())
    except Exception as e:
        logger.warning("Remote MCP tool discovery failed for %s: %s", url, e)
        return []
