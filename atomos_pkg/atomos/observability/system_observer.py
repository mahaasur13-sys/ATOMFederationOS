"""
ATOM OS — Observability Layer (Metrics + Anomaly Detection)
"""

from __future__ import annotations
import logging
import time
import psutil
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.observability")


@register("system_observer", module_type="observability", init_order=45)
class SystemObserver:
    """
    Monitors CPU / GPU / RAM / Disk / Network.
    Used by TAAR v5+ for resource-aware scheduling.
    """

    def __init__(self):
        self._start = time.time()
        self._samples: list[dict] = []
        self._max_samples = 1000

    def observe(self) -> dict:
        """Capture current system state."""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            state = {
                "timestamp": time.time(),
                "cpu_percent": cpu,
                "ram_used_gb": mem.used / (1024**3),
                "ram_percent": mem.percent,
                "disk_percent": disk.percent,
                "net_bytes_sent": net.bytes_sent,
                "net_bytes_recv": net.bytes_recv,
            }

            self._samples.append(state)
            if len(self._samples) > self._max_samples:
                self._samples.pop(0)

            return state
        except Exception as e:
            return {"error": str(e)}

    def health(self) -> dict:
        obs = self.observe()
        return {
            "cpu_percent": obs.get("cpu_percent", 0),
            "ram_percent": obs.get("ram_percent", 0),
            "uptime_s": time.time() - self._start,
        }


@register("metrics_collector", module_type="observability", init_order=46)
class MetricsCollector:
    """
    Collects task-level metrics: latency, success rate, cost.
    Used by Control Plane evolver (TAAR v5+).
    """

    def __init__(self):
        self.metrics: list[dict] = []

    def record(self, task_id: str, metric: dict) -> None:
        self.metrics.append({"task_id": task_id, **metric, "ts": time.time()})

    def get_summary(self, last_n: int = 100) -> dict:
        recent = self.metrics[-last_n:]
        if not recent:
            return {"count": 0}
        successes = sum(1 for m in recent if m.get("status") == "success")
        return {
            "count": len(recent),
            "success_rate": successes / len(recent),
            "avg_latency_ms": sum(m.get("latency_ms", 0) for m in recent) / len(recent),
        }

    def health(self) -> dict:
        return {"total_metrics": len(self.metrics)}


@register("anomaly_detector", module_type="observability", init_order=47)
class AnomalyDetector:
    """
    Detects abnormal patterns in execution.
    Triggers circuit breaker if anomaly detected.
    """

    def __init__(self, observer: SystemObserver | None = None):
        self.observer = observer
        self.baseline: dict = {}
        self._circuit_breaker_open = False

    def init(self) -> None:
        if self.observer:
            self.baseline = self.observer.observe()
        logger.info("  Anomaly detector calibrated")

    def is_anomalous(self, value: float, metric: str, threshold: float = 3.0) -> bool:
        """Z-score based anomaly detection."""
        return False  # stub

    def health(self) -> dict:
        return {
            "circuit_breaker": "open" if self._circuit_breaker_open else "closed",
            "baseline_loaded": bool(self.baseline),
        }
