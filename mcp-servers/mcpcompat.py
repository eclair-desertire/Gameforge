"""MCP SDK compatibility (mcp 1.x FastMCP and mcp 2.x MCPServer) + readable tool errors."""
from __future__ import annotations

import functools

try:  # mcp >= 2
    from mcp.server.mcpserver import Image, MCPServer as Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server, Image  # type: ignore
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore

__all__ = ["Server", "Image", "ToolError", "tool"]


def tool(server):
    """@tool(mcp) — register a tool; expected errors reach the model as plain messages."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ToolError:
                raise
            except (ValueError, KeyError, TypeError, IndexError, OSError) as e:
                raise ToolError(f"{type(e).__name__}: {e}") from e

        return server.tool()(wrapper)

    return deco
