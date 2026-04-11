"""
ATOM OS — Service Registry (Dependency Injection Container)
All modules register here. No module may access another without registration.
"""

from __future__ import annotations
import logging
import threading
from typing import Any, Callable, Type
from dataclasses import dataclass, field

logger = logging.getLogger("atomos.registry")


@dataclass
class ServiceMetadata:
    name: str
    cls: Type
    instance: Any = None
    dependencies: list[str] = field(default_factory=list)
    health_status: str = "uninitialized"
    version: str = "1.0.0"
    init_order: int = 0
    module_type: str = "generic"


class ServiceRegistry:
    """
    Single source of truth for all ATOM OS modules.
    Modules register via @registry.register decorator.
    """

    _instance: ServiceRegistry | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ServiceRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._services: dict[str, ServiceMetadata] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._pending_deps: dict[str, list[str]] = {}
        self._boot_order: list[str] = []
        self._initialized = False

    # ── Registration ─────────────────────────────────────────

    def register(
        self,
        name: str,
        cls: Type,
        *,
        dependencies: list[str] | None = None,
        factory: Callable[[], Any] | None = None,
        version: str = "1.0.0",
        module_type: str = "generic",
        init_order: int = 50,
    ) -> None:
        if name in self._services:
            logger.warning(f"Service '{name}' already registered, skipping")
            return

        self._services[name] = ServiceMetadata(
            name=name,
            cls=cls,
            dependencies=dependencies or [],
            version=version,
            module_type=module_type,
            init_order=init_order,
        )
        if factory:
            self._factories[name] = factory

        logger.debug(f"Registered: {name} (type={module_type}, deps={dependencies})")

    def register_singleton(
        self, name: str, instance: Any, *, module_type: str = "generic"
    ) -> None:
        meta = ServiceMetadata(
            name=name, cls=type(instance), instance=instance, module_type=module_type
        )
        self._services[name] = meta
        logger.debug(f"Registered singleton: {name}")

    # ── Resolution ──────────────────────────────────────────

    def get(self, name: str) -> Any:
        meta = self._services.get(name)
        if not meta:
            raise KeyError(f"No service registered: '{name}'")
        if meta.instance is None:
            raise RuntimeError(
                f"Service '{name}' not initialized. Call registry.boot() first."
            )
        return meta.instance

    def get_meta(self, name: str) -> ServiceMetadata:
        return self._services[name]

    def list_services(self, module_type: str | None = None) -> list[str]:
        if module_type:
            return [
                n for n, m in self._services.items() if m.module_type == module_type
            ]
        return list(self._services.keys())

    def list_by_type(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for name, meta in self._services.items():
            result.setdefault(meta.module_type, []).append(name)
        return result

    # ── Boot ────────────────────────────────────────────────

    def boot(self) -> None:
        """Initialize all services in dependency order."""
        if self._initialized:
            logger.warning("Already booted")
            return

        self._build_boot_order()
        logger.info(f"Boot order: {' → '.join(self._boot_order)}")

        for name in self._boot_order:
            self._init_service(name)

        self._initialized = True
        logger.info("ATOM OS fully booted")

    def _build_boot_order(self) -> None:
        """Topological sort respecting dependencies."""
        visited: set[str] = set()
        order: list[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            meta = self._services[name]
            for dep in meta.dependencies:
                if dep not in self._services:
                    raise ValueError(
                        f"Service '{name}' depends on unregistered service: '{dep}'"
                    )
                visit(dep)
            order.append(name)

        for name in self._services:
            visit(name)

        self._boot_order = order

    def _init_service(self, name: str) -> None:
        meta = self._services[name]
        logger.info(f"  Booting {name}...")

        try:
            if name in self._factories:
                instance = self._factories[name]()
            elif hasattr(meta.cls, "get_instance"):
                instance = meta.cls.get_instance()
            else:
                deps = {
                    dep: self.get(dep) for dep in meta.dependencies
                }
                instance = meta.cls(**deps)

            meta.instance = instance

            if hasattr(instance, "init"):
                instance.init()

            if hasattr(instance, "health"):
                meta.health_status = "healthy"
            else:
                meta.health_status = "initialized"

            logger.info(f"    ✅ {name} ({meta.health_status})")

        except Exception as e:
            meta.health_status = f"failed: {e}"
            logger.error(f"    ❌ {name} failed to boot: {e}")
            raise

    # ── Health ──────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, meta in self._services.items():
            status = meta.health_status
            if hasattr(meta.instance, "health"):
                try:
                    h = meta.instance.health()
                    status = h if isinstance(h, str) else h.get("status", h)
                except Exception as e:
                    status = f"unhealthy: {e}"
            results[name] = {
                "type": meta.module_type,
                "status": status,
                "version": meta.version,
            }
        return results

    def get_boot_stats(self) -> dict[str, Any]:
        healthy = sum(
            1 for m in self._services.values() if "healthy" in m.health_status or m.health_status == "initialized"
        )
        return {
            "total": len(self._services),
            "healthy": healthy,
            "failed": len(self._services) - healthy,
            "boot_order": self._boot_order,
        }

    # ── Shutdown ────────────────────────────────────────────

    def shutdown(self) -> None:
        """Shutdown in reverse boot order."""
        for name in reversed(self._boot_order):
            meta = self._services.get(name)
            if meta and meta.instance and hasattr(meta.instance, "shutdown"):
                try:
                    meta.instance.shutdown()
                    logger.info(f"  Shut down: {name}")
                except Exception as e:
                    logger.error(f"  Failed to shut down {name}: {e}")
        self._initialized = False
        logger.info("ATOM OS shut down")


# ── Decorator ─────────────────────────────────────────────────────

_registry = ServiceRegistry()


def register(
    name: str | None = None,
    *,
    dependencies: list[str] | None = None,
    factory: Callable[[], Any] | None = None,
    version: str = "1.0.0",
    module_type: str = "generic",
    init_order: int = 50,
) -> Callable[[Type], Type]:
    def decorator(cls: Type) -> Type:
        svc_name = name or cls.__name__
        _registry.register(
            svc_name,
            cls,
            dependencies=dependencies,
            factory=factory,
            version=version,
            module_type=module_type,
            init_order=init_order,
        )
        return cls

    return decorator


# ── Singleton accessor ────────────────────────────────────────────

def get_registry() -> ServiceRegistry:
    return _registry


def get_service(name: str) -> Any:
    """Convenience: registry.get()"""
    return _registry.get(name)

# ── Module-level alias ────────────────────────────────────────────
registry = _registry  # singleton instance
