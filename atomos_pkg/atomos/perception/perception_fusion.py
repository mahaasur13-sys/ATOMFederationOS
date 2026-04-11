"""
ATOM OS — Perception Fusion Layer
Fuses: text + vision + voice → unified world model state.
"""

from __future__ import annotations
import logging
import time
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.perception")


@register("perception_fusion", module_type="perception", init_order=58)
class PerceptionFusion:
    """
    Multimodal fusion — combines text, vision, voice into one context.
    Routes attention to highest-priority modality.
    """

    def __init__(self):
        self.last_text = ""
        self.last_vision = {}
        self.last_voice = ""
        self.fusion_buffer: list[dict] = []

    def init(self) -> None:
        logger.info("  Perception fusion ready (text+vision+voice)")

    def ingest_text(self, text: str) -> None:
        self.last_text = text
        self.fusion_buffer.append({"modality": "text", "content": text, "ts": time.time()})

    def ingest_vision(self, description: dict) -> None:
        self.last_vision = description
        self.fusion_buffer.append({"modality": "vision", "content": description, "ts": time.time()})

    def ingest_voice(self, transcript: str) -> None:
        self.last_voice = transcript
        self.fusion_buffer.append({"modality": "voice", "content": transcript, "ts": time.time()})

    def get_fused_context(self) -> dict:
        """Returns unified context with modality priority."""
        priority = []
        if self.last_voice:
            priority.append({"modality": "voice", "content": self.last_voice})
        if self.last_vision:
            priority.append({"modality": "vision", "content": self.last_vision})
        if self.last_text:
            priority.append({"modality": "text", "content": self.last_text})

        return {
            "context": priority,
            "last_text": self.last_text,
            "last_vision": self.last_vision,
            "last_voice": self.last_voice,
            "buffer_size": len(self.fusion_buffer),
        }

    def health(self) -> dict:
        return {"buffer_size": len(self.fusion_buffer), "modalities": 3}


@register("world_model", module_type="perception", init_order=59)
class WorldModel:
    """
    Persistent environment state.
    Maintains a model of: files, services, agents, resources.
    """

    def __init__(self):
        self.state: dict[str, Any] = {}

    def init(self) -> None:
        logger.info("  World model initialized")
        self.state = {
            "files": {},
            "services": {},
            "agents": {},
            "resources": {"cpu": 0, "ram": 0, "gpu": 0},
        }

    def update(self, key: str, value: Any) -> None:
        self.state[key] = value

    def query(self, key: str) -> Any:
        return self.state.get(key)

    def health(self) -> dict:
        return {"state_keys": list(self.state.keys())}


@register("attention_router", module_type="perception", init_order=57)
class AttentionRouter:
    """
    Routes inputs to the right module based on priority.
    Voice > Vision > Text (default).
    """

    def __init__(self):
        self.priority_order = ["voice", "vision", "text"]

    def init(self) -> None:
        logger.info("  Attention router ready")

    def route(self, input_type: str, context: dict) -> str:
        return input_type  # stub: returns input type as route

    def health(self) -> dict:
        return {"priority": self.priority_order}
