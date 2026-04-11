"""
ATOM OS — MCP Gateway (Model Context Protocol)
Routes service requests to MCP-compatible servers.
"""

from __future__ import annotations
import logging
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.mcp")


@register("mcp_gateway", module_type="mcp", init_order=70)
class MCPGateway:
    """
    MCP Router — routes requests to MCP servers.
    Supports: vision, stt, tts, search, memory services.
    """

    def __init__(self):
        self.routes: dict[str, str] = {}  # service → endpoint
        self._server_stubs = {
            "vision": "atomos.vision.vision_agent",
            "stt": "atomos.voice.stt_engine",
            "tts": "atomos.voice.tts_engine",
        }

    def init(self) -> None:
        logger.info(f"  MCP Gateway stub — routes: {list(self.routes.keys())}")

    def register_route(self, service: str, endpoint: str) -> None:
        self.routes[service] = endpoint
        logger.info(f"  MCP route registered: {service} → {endpoint}")

    def call(self, service: str, method: str, params: dict) -> Any:
        """Call an MCP service method."""
        if service not in self.routes:
            return {"error": f"Unknown service: {service}"}
        return {"stub": f"{service}.{method}({params})", "result": None}

    def health(self) -> dict:
        return {"routes": list(self.routes.keys()), "stub_mode": True}


@register("mcp_protocol", module_type="mcp", init_order=71)
class MCPProtocol:
    """
    MCP Request/Response schema definitions.
    JSON-RPC 2.0 based.
    """

    @staticmethod
    def make_request(method: str, params: dict) -> dict:
        return {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

    @staticmethod
    def make_response(result: Any, error: str | None = None) -> dict:
        if error:
            return {"jsonrpc": "2.0", "error": {"code": -32600, "message": error}, "id": None}
        return {"jsonrpc": "2.0", "result": result, "id": 1}
