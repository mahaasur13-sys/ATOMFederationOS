"""
ATOM OS — Ollama Runtime Client
Binds to local Ollama for LLM inference.
"""

from __future__ import annotations
import logging
import os
import urllib.request
import urllib.error
import json
import time
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.ollama")


class OllamaClient:
    """HTTP client for Ollama REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder-7b",
        timeout: int = 120,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._available = None  # lazy check

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
        return self._available

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 512,
        stop: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a generate request to Ollama."""
        if not self.is_available():
            raise RuntimeError(
                "Ollama not available. Start with: ollama serve"
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "num_predict": num_predict,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if stop:
            payload["stop"] = stop

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama request failed: {e}")

        result["_latency_ms"] = (time.time() - start) * 1000
        return result

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Send a chat request to Ollama."""
        if not self.is_available():
            raise RuntimeError(
                "Ollama not available. Start with: ollama serve"
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())

        result["_latency_ms"] = (time.time() - start) * 1000
        return result

    def list_models(self) -> list[str]:
        """List available models."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []

    def health(self) -> dict:
        avail = self.is_available()
        return {
            "available": avail,
            "url": self.base_url,
            "model": self.model,
            "models": self.list_models() if avail else [],
        }


@register(
    "ollama_client",
    dependencies=[],
    module_type="runtime",
    init_order=55,
)
class OllamaClientWrapper:
    """
    Wraps OllamaClient with ATOM OS conventions.
    Falls back gracefully if Ollama not running.
    """

    def __init__(self):
        self.client = OllamaClient(
            base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder-7b"),
        )
        self._ready = False

    def init(self) -> None:
        if self.client.is_available():
            self._ready = True
            logger.info(f"  Ollama ready: {self.client.model}")
        else:
            logger.warning("  Ollama not available — LLM features disabled")
            logger.warning("  Start with: ollama serve")

    def health(self) -> dict:
        return self.client.health()

    def generate(self, **kwargs) -> dict:
        return self.client.generate(**kwargs)

    def chat(self, **kwargs) -> dict:
        return self.client.chat(**kwargs)

    def is_ready(self) -> bool:
        return self._ready
