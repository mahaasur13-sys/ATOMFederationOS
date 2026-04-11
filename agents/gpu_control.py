"""
TAAR v2.1 — GPU Control Layer (GreenWithEnvy Abstraction)
Manages RTX 3060 (12GB VRAM) power, thermal, and frequency.
"""

from __future__ import annotations

import subprocess
import re
import time
from dataclasses import dataclass, field
from typing import Literal
from enum import Flag, auto


# ─────────────────────────────────────────
# GPU Status & Enums
# ─────────────────────────────────────────

class ThermalState(Flag):
    COLD = 0
    NOMINAL = auto()
    WARM = auto()
    HOT = auto()
    CRITICAL = auto()


class PowerProfile(Flag):
    DEFAULT = 0
    PERFORMANCE = auto()
    BALANCED = auto()
    ECO = auto()


@dataclass
class GPUStatus:
    vram_used_mb: int = 0
    vram_total_mb: int = 12288      # RTX 3060 = 12GB
    temperature_c: int = 0
    power_draw_w: int = 0
    gpu_util_pct: int = 0
    thermal_state: ThermalState = ThermalState.NOMINAL
    power_profile: PowerProfile = PowerProfile.BALANCED
    compute_mode: str = "default"  # default / compute / low_power
    timestamp: float = field(default_factory=time.time)

    @property
    def vram_free_mb(self) -> int:
        return self.vram_total_mb - self.vram_used_mb

    @property
    def vram_util_pct(self) -> int:
        return int(100 * self.vram_used_mb / self.vram_total_mb)

    @property
    def is_overheating(self) -> bool:
        return self.thermal_state in (ThermalState.HOT, ThermalState.CRITICAL)

    @property
    def is_vram_pressure(self) -> bool:
        return self.vram_util_pct >= 85

    def pressure_level(self) -> Literal["low", "medium", "high", "critical"]:
        pct = self.vram_util_pct
        if pct < 50:
            return "low"
        elif pct < 75:
            return "medium"
        elif pct < 90:
            return "high"
        else:
            return "critical"

    def thermal_level(self) -> Literal["low", "medium", "high", "critical"]:
        t = self.temperature_c
        if t < 50:
            return "low"
        elif t < 70:
            return "medium"
        elif t < 83:
            return "high"
        else:
            return "critical"


# ─────────────────────────────────────────
# nvidia-smi wrapper
# ─────────────────────────────────────────

def get_nvidia_smi() -> dict | None:
    """Query nvidia-smi. Returns None if no GPU."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu,"
             "power.draw,utilization.gpu", "--format=csv,noheader,nounits"],
            timeout=5, text=True
        )
        val = [int(x.strip()) for x in out.strip().split(",")]
        return {
            "vram_used_mb": val[0],
            "vram_total_mb": val[1],
            "temperature_c": val[2],
            "power_draw_w": val[3],
            "gpu_util_pct": val[4],
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
        return None


def set_power_profile(profile: PowerProfile) -> bool:
    """Set GPU power profile via nvidia-smi. Returns success."""
    profiles = {
        PowerProfile.PERFORMANCE: "maximum",
        PowerProfile.BALANCED: "adaptive",
        PowerProfile.ECO: "eco",
    }
    if profile not in profiles:
        return False
    try:
        subprocess.run(
            ["nvidia-smi", "-pm", "1"], check=True, timeout=5
        )
        return True
    except subprocess.CalledProcessError:
        return False


# ─────────────────────────────────────────
# GPU Control Layer
# ─────────────────────────────────────────

class GPUControlLayer:
    """
    GreenWithEnvy abstraction for RTX 3060.
    Tracks VRAM, temperature, power; applies compute policies.
    """

    DEFAULT_VRAM_THRESHOLD = 85       # % — disable swarm above this
    DEFAULT_TEMP_THRESHOLD = 83        # °C — throttle above this
    DEFAULT_EMERGENCY_TEMP = 86       # °C — force single-mode above this

    def __init__(
        self,
        vram_threshold_pct: int = DEFAULT_VRAM_THRESHOLD,
        temp_threshold_c: int = DEFAULT_TEMP_THRESHOLD,
        emergency_temp_c: int = DEFAULT_EMERGENCY_TEMP,
    ):
        self.vram_threshold_pct = vram_threshold_pct
        self.temp_threshold_c = temp_threshold_c
        self.emergency_temp_c = emergency_temp_c
        self._status_cache: GPUStatus | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 2.0   # seconds

    def get_status(self, force_refresh: bool = False) -> GPUStatus:
        """Get current GPU status (cached 2s)."""
        now = time.time()
        if not force_refresh and self._status_cache and (now - self._cache_time) < self._cache_ttl:
            return self._status_cache

        raw = get_nvidia_smi()
        if raw is None:
            # No GPU — return safe defaults
            return GPUStatus()

        state = GPUStatus(
            vram_used_mb=raw["vram_used_mb"],
            vram_total_mb=raw["vram_total_mb"],
            temperature_c=raw["temperature_c"],
            power_draw_w=raw["power_draw_w"],
            gpu_util_pct=raw["gpu_util_pct"],
            thermal_state=self._calc_thermal_state(raw["temperature_c"]),
            timestamp=now,
        )
        self._status_cache = state
        self._cache_time = now
        return state

    def _calc_thermal_state(self, temp_c: int) -> ThermalState:
        if temp_c < 40:
            return ThermalState.COLD
        elif temp_c < 60:
            return ThermalState.NOMINAL
        elif temp_c < 75:
            return ThermalState.WARM
        elif temp_c < self.emergency_temp_c:
            return ThermalState.HOT
        else:
            return ThermalState.CRITICAL

    # ── Policy Queries ─────────────────────

    def can_run_swarm(self) -> tuple[bool, str]:
        """Check if parallel LLM inference is safe on GPU."""
        status = self.get_status()

        if status.vram_util_pct >= self.vram_threshold_pct:
            return False, f"VRAM pressure: {status.vram_util_pct}% >= {self.vram_threshold_pct}%"

        if status.temperature_c >= self.emergency_temp_c:
            return False, f"Emergency thermal: {status.temperature_c}°C >= {self.emergency_temp_c}°C"

        if status.temperature_c >= self.temp_threshold_c:
            return False, f"High thermal: {status.temperature_c}°C >= {self.temp_threshold_c}°C"

        return True, "OK"

    def can_run_llm(self) -> tuple[bool, str]:
        """Check if single LLM inference is safe."""
        status = self.get_status()

        if status.is_overheating:
            return False, f"Overheating: {status.temperature_c}°C"

        if status.vram_util_pct >= 95:
            return False, f"VRAM critical: {status.vram_util_pct}%"

        return True, "OK"

    def get_safe_compute_mode(self) -> str:
        """Return safe compute mode based on current GPU state."""
        status = self.get_status()

        if status.temperature_c >= self.emergency_temp_c:
            return "low_power"
        elif status.temperature_c >= self.temp_threshold_c:
            return "balanced"
        elif status.vram_util_pct >= 75:
            return "balanced"
        else:
            return "default"

    def recommended_batch_size(self, model_size_mb: int) -> int:
        """Recommend batch size based on available VRAM."""
        status = self.get_status()
        free = status.vram_free_mb
        # Reserve 1GB headroom
        usable = free - 1024
        if usable <= 0:
            return 0
        return max(1, int(usable / model_size_mb))

    def get_allocation_hint(self, required_mb: int) -> Literal["immediate", "offload", "swap", "deny"]:
        """
        Ask: can we allocate 'required_mb' VRAM?
        Returns tier where allocation would happen.
        """
        status = self.get_status()
        free = status.vram_free_mb

        if free >= required_mb + 512:
            return "immediate"    # fits in VRAM
        elif free >= required_mb:
            return "immediate"    # fits with minimal headroom
        else:
            # VRAM overflow — would need offload
            return "offload"       # TODO: integrate with memory_hierarchy

    # ── Control Actions ───────────────────

    def apply_thermal_throttle(self) -> dict:
        """Reduce GPU intensity when hot."""
        status = self.get_status()
        actions = []

        if status.temperature_c >= self.emergency_temp_c:
            set_power_profile(PowerProfile.ECO)
            actions.append("eco_mode")
        elif status.temperature_c >= self.temp_threshold_c:
            set_power_profile(PowerProfile.BALANCED)
            actions.append("balanced_mode")

        return {
            "applied": actions,
            "temperature_c": status.temperature_c,
            "profile": str(status.power_profile),
        }

    def suggest_downgrade(self, current_mode: str) -> str | None:
        """
        Given current execution mode, suggest degraded mode if GPU pressure.
        Returns None if current mode is safe.
        """
        can_swarm, reason = self.can_run_swarm()
        status = self.get_status()

        if not can_swarm and current_mode == "SWARM":
            # Check if single LLM is safe
            if self.can_run_llm()[0]:
                return "SINGLE"
            else:
                return "TOOL"

        if not self.can_run_llm()[0] and current_mode in ("SINGLE", "SWARM"):
            return "TOOL"

        return None

    def monitor(self) -> dict:
        """Full GPU snapshot for logging/debugging."""
        s = self.get_status(force_refresh=True)
        can_swarm, swarm_reason = self.can_run_swarm()
        can_llm, llm_reason = self.can_run_llm()
        downgrade = self.suggest_downgrade("SWARM")

        return {
            "gpu_present": s.vram_total_mb > 0,
            "vram_used_mb": s.vram_used_mb,
            "vram_total_mb": s.vram_total_mb,
            "vram_util_pct": s.vram_util_pct,
            "temperature_c": s.temperature_c,
            "power_draw_w": s.power_draw_w,
            "gpu_util_pct": s.gpu_util_pct,
            "thermal_state": s.thermal_state.name,
            "pressure": s.pressure_level(),
            "can_run_swarm": can_swarm,
            "swarm_reason": swarm_reason,
            "can_run_llm": can_llm,
            "llm_reason": llm_reason,
            "suggested_downgrade": downgrade,
            "compute_mode": s.compute_mode,
        }
