"""Stdio MCP server wiring: tool schemas plus request handlers."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from . import run_tool

SERVER_NAME = "gridmarket-mcp"


def _schema(
    properties: dict[str, dict[str, str]], required: list[str] | None = None
) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


_ORDER_PROPS = {
    "product_id": {"type": "string", "description": "Product id from market()."},
    "quantity": {"type": "integer", "description": "Lots; at most 50 per order."},
    "price_cents": {"type": "integer", "description": "Limit price in cents."},
    "idempotency_key": {"type": "string", "description": "Caller-chosen dedupe key."},
}

TOOLS: list[Tool] = [
    Tool(name="market", description="List market products.", inputSchema=_schema({})),
    Tool(
        name="order_book",
        description="Read one product book.",
        inputSchema=_schema({"symbol": {"type": "string"}}, ["symbol"]),
    ),
    Tool(
        name="predictions",
        description="Read zone scores; pass zone for one zone.",
        inputSchema=_schema({"zone": {"type": "string"}}),
    ),
    Tool(
        name="router_checks",
        description="Read decision-router checks; pass family to filter.",
        inputSchema=_schema({"family": {"type": "string"}}),
    ),
    Tool(
        name="provider_health",
        description="Read provider heartbeat and outage state.",
        inputSchema=_schema({}),
    ),
    Tool(
        name="bot_population",
        description="Read the bot population; pass bot_type to filter.",
        inputSchema=_schema({"bot_type": {"type": "string"}}),
    ),
    Tool(
        name="my_orders",
        description="List the caller's own orders.",
        inputSchema=_schema({}),
    ),
    Tool(
        name="my_positions",
        description="List the caller's own open positions.",
        inputSchema=_schema({}),
    ),
    Tool(
        name="my_pnl",
        description="Read the caller's own balances and holdings.",
        inputSchema=_schema({}),
    ),
    Tool(
        name="my_losses",
        description="Read the caller's own settled losses.",
        inputSchema=_schema({}),
    ),
    Tool(
        name="buy",
        description="Place a buy order through the public risk-checked API.",
        inputSchema=_schema(
            _ORDER_PROPS, ["product_id", "quantity", "price_cents", "idempotency_key"]
        ),
    ),
    Tool(
        name="sell",
        description="Place a sell order through the public risk-checked API.",
        inputSchema=_schema(
            _ORDER_PROPS, ["product_id", "quantity", "price_cents", "idempotency_key"]
        ),
    ),
    Tool(
        name="cancel",
        description="Cancel one of the caller's own orders.",
        inputSchema=_schema({"order_id": {"type": "string"}}, ["order_id"]),
    ),
]


def create_server(base_url: str, api_key: str) -> Server:
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        is_error, payload = await asyncio.to_thread(
            run_tool, name, dict(arguments or {}), base_url=base_url, api_key=api_key
        )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload))],
            isError=is_error,
        )

    return server


async def main() -> None:
    base_url = os.environ.get("GRIDMARKET_URL")
    api_key = os.environ.get("GRIDMARKET_API_KEY")
    if not base_url or not api_key:
        raise SystemExit("GRIDMARKET_URL and GRIDMARKET_API_KEY must both be set")
    server = create_server(base_url, api_key)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
