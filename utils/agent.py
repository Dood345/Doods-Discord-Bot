"""Tool-calling agent loop for Cave Johnson (Ollama /api/chat)"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from utils.auth import is_authorized

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
TOOL_TIMEOUT = 15        # seconds per tool call
AGENT_TIMEOUT = 120      # seconds for the whole loop


@dataclass
class ToolContext:
    """Who triggered the agent and where. `user` is always the real Discord author."""
    bot: Any
    user: Any
    guild: Any = None
    channel: Any = None
    pending: set = field(default_factory=set)  # confirmation cards already posted this turn
    blocked: set = field(default_factory=set)  # tools not offered this turn (e.g. stale catch-up replies)


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Awaitable[str]]   # async (ctx, **args) -> str
    parameters: Dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    requires_auth: bool = False    # homelab/owner-only; checked against ctx.user in code
    requires_guild: bool = False   # needs a server (not available in DMs)
    timeout: float = TOOL_TIMEOUT

    def schema(self) -> Dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


class ToolRegistry:
    def __init__(self, tools: Optional[List[Tool]] = None):
        self.tools: Dict[str, Tool] = {t.name: t for t in (tools or [])}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def _allowed(self, tool: Tool, ctx: ToolContext) -> bool:
        if tool.requires_auth and not is_authorized(ctx.user):
            return False
        if tool.requires_guild and ctx.guild is None:
            return False
        return tool.name not in ctx.blocked

    def schemas_for(self, ctx: ToolContext) -> List[Dict]:
        """Only offer the model tools this caller may actually use."""
        return [t.schema() for t in self.tools.values() if self._allowed(t, ctx)]

    async def dispatch(self, name: str, raw_args: Any, ctx: ToolContext) -> str:
        """Run a tool call from the model. Never raises; errors go back to the model as text."""
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool '{name}'."
        # Re-check here: the model may name a tool it was never offered.
        if tool.requires_auth and not is_authorized(ctx.user):
            logger.warning(f"Agent: denied tool {name} for user {ctx.user.id if ctx.user else None}")
            return "ERROR: access denied. This user is not authorized for facility systems."
        if tool.requires_guild and ctx.guild is None:
            return "ERROR: this tool only works inside a server, not in DMs."
        if name in ctx.blocked:
            return f"ERROR: {name} isn't available for this message."

        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError:
                return "ERROR: tool arguments were not valid JSON."
        args = raw_args if isinstance(raw_args, dict) else {}
        allowed = set(tool.parameters.get("properties", {}))
        args = {k: v for k, v in args.items() if k in allowed}

        logger.info(f"Agent tool call: {name} args={args} user={ctx.user.id if ctx.user else None}")
        try:
            return str(await asyncio.wait_for(tool.handler(ctx, **args), timeout=tool.timeout))
        except asyncio.TimeoutError:
            return f"ERROR: {name} timed out."
        except Exception as e:
            logger.exception(f"Agent tool {name} failed")
            return f"ERROR: {name} failed ({type(e).__name__})."


async def run_agent(chat: Callable[[List[Dict], Optional[List[Dict]]], Awaitable[Dict]],
                    messages: List[Dict], registry: ToolRegistry, ctx: ToolContext) -> str:
    """Call the model, execute requested tools, feed results back, repeat until a final answer.

    `chat(messages, tools)` returns an Ollama assistant message dict.
    """
    async def loop() -> str:
        tools = registry.schemas_for(ctx) or None
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await chat(messages, tools)
            calls = reply.get("tool_calls") or []
            if not calls:
                return (reply.get("content") or "").strip()
            messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                result = await registry.dispatch(fn.get("name", ""), fn.get("arguments", {}), ctx)
                messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": result})
        # Out of tool rounds: force a final answer from what it has
        reply = await chat(messages, None)
        return (reply.get("content") or "").strip()

    return await asyncio.wait_for(loop(), timeout=AGENT_TIMEOUT)
