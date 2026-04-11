"""
TAAR v5 — System Observer
Monitors GPU/RAM/CPU pressure, failure rates, stability.
Produces system_state snapshot every tick.
"""

from __future__ import annotations

import time
import psutil
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


@dataclass
class SystemState:
    gpu_pressure: float = 0.0     # 0.0-1.0
    memory_pressure: float = 0.0   # 0.0-1.0
    cpu_load: float = 0.0           # 0.0-1.0
    task_failure_rate: float = 0.0  # 0.0-1.0
    mission_success_rate: float = 1.0  # 0.0-1.0
    policy_drift: float = 0.0       # 0.0-1.0
    system_stability: float = 1.0  # 0.0-1.0
    anomaly_count: int = 0
    uptime_seconds: float = 0.0
    timestamp: str = ""
    anomalies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "gpu_pressure": round(self.gpu_pressure, 3),
            "memory_pressure": round(self.memory_pressure, 3),
            "cpu_load": round(self.cpu_load, 3),
            "task_failure_rate": round(self.task_failure_rate, 3),
            "mission_success_rate": round(self.mission_success_rate, 3),
            "policy_drift": round(self.policy_drift, 3),
            "system_stability": round(self.system_stability, 3),
            "anomaly_count": self.anomaly_count,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "timestamp": self.timestamp,
            "anomalies": self.anomalies,
        }


class SystemObserver:
    def __init__(self):
        self._start_time = time.time()
        self._failure_history: list[int] = []  # rolling window
        self._mission_history: list[bool] = []  # success/failure
        self._last_state: Optional[SystemState] = None
        self._anomaly_threshold = 0.15  # task_failure_rate > this → anomaly

    def observe(self, failure_count: int = 0, mission_outcomes: Optional[list[bool]] = None) -> SystemState:
        now = time.time()
        uptime = now - self._start_time

        # Track rolling failure rate (last 20 tasks)
        if failure_count >= 0:
            self._failure_history.append(failure_count)
            if len(self._failure_history) > 20:
                self._failure_history.pop(0)

        # Track mission outcomes
        if mission_outcomes:
            self._mission_history.extend(mission_outcomes)
            if len(self._mission_history) > 50:
                self._mission_history = self._mission_history[-50:]

        # System metrics
        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1) / 100.0
        memory_pressure = mem.percent / 100.0

        # GPU: try nvidia-smi, fallback to memory heuristic
        gpu_pressure = self._get_gpu_pressure()

        # Compute derived metrics
        task_failure_rate = sum(self._failure_history) / max(len(self._failure_history), 1)
        mission_success_rate = (
            sum(self._mission_history) / max(len(self._mission_history), 1)
            if self._mission_history else 1.0
        )

        # Stability = weighted combination (lower is worse)
        system_stability = (
            mission_success_rate * 0.4
            + (1.0 - task_failure_rate) * 0.3
            + (1.0 - memory_pressure) * 0.2
            + (1.0 - gpu_pressure) * 0.1
        )

        # Policy drift (placeholder — updated by control_plane_evolver)
        policy_drift = getattr(self, '_policy_drift', 0.0)

        # Anomaly detection
        anomalies = []
        if task_failure_rate > self._anomaly_threshold:
            anomalies.append(f"high_failure_rate:{task_failure_rate:.2f}")
        if memory_pressure > 0.85:
            anomalies.append(f"high_memory_pressure:{memory_pressure:.2f}")
        if gpu_pressure > 0.90:
            anomalies.append(f"high_gpu_pressure:{gpu_pressure:.2f}")
        if mission_success_rate < 0.70:
            anomalies.append(f"low_mission_success:{mission_success_rate:.2f}")

        state = SystemState(
            gpu_pressure=gpu_pressure,
            memory_pressure=memory_pressure,
            cpu_load=cpu_percent,
            task_failure_rate=task_failure_rate,
            mission_success_rate=mission_success_rate,
            policy_drift=policy_drift,
            system_stability=system_stability,
            anomaly_count=len(anomalies),
            uptime_seconds=uptime,
            timestamp=datetime.now(timezone.utc).isoformat(),
            anomalies=anomalies,
        )

        self._last_state = state
        return state

    def _get_gpu_pressure(self) -> float:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                util_str, mem_used, mem_total = result.stdout.strip().split(",")
                gpu_util = float(util_str.strip()) / 100.0
                mem_used_mb = float(mem_used.strip())
                mem_total_mb = float(mem_total.strip())
                mem_frac = mem_used_mb / mem_total_mb if mem_total_mb > 0 else 0.0
                return max(gpu_util, mem_frac)
        except Exception:
            pass
        # Fallback: rough estimate from VRAM usage patterns
        try:
            with open("/proc/driver/nvidia/gpu/0ram", "r") as f:
                used = int(f.read().strip())
                total = 12 * 1024  # 12GB for RTX 3060
                return min(used / (total * 1024 * 1024), 1.0)
        except Exception:
            return 0.0

    def get_health_report(self) -> dict:
        state = self._last_state or self.observe()
        health = "healthy" if state.system_stability > 0.80 else "degraded" if state.system_stability > 0.50 else "critical"
        return {
            "health": health,
            "stability": round(state.system_stability, 3),
            "mission_success_rate": round(state.mission_success_rate, 3),
            "anomalies": state.anomalies,
            "uptime": round(state.uptime_seconds, 1),
        }


if __name__ == "__main__":
    obs = SystemObserver()
    state = obs.observe()
    print("System state:", state.to_dict())
    print("Health report:", obs.get_health_report())
