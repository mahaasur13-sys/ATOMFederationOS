# ATOMFederationOS — Agent Memory

## Current Version: v10.2.0

## Architecture: Two Stacks

```
ATOMFederationOS v10
├── Python stack (monorepo /this repo)
│   ├── GoA implementation (pkg/goa/)
│   ├── REDEREF router bindings (pkg/router/)
│   ├── DESC event-sourcing (pkg/desc/)
│   ├── atomos_pkg (agent runtime)
│   └── agents/ (high-level agents)
│
└── Go stack (separate repos)
    ├── atom-kernel         — deterministic kernel (RL-019/020/021/022)
    ├── atom-federation     — federation + messaging
    ├── atom-agent          — deterministic agent executor
    ├── atom-router         — REDEREF router (Thompson sampling)
    ├── atom-operator       — K8s CRD operator
    └── atom-federation-core — K8s control plane (controllers + eventstore)
```

---

## Python Stack (This Repo)

### GoA — Graph of Agents (pkg/goa/)

| Module | Responsibility |
|--------|----------------|
| `graph.go` | AgentGraph, Node, Edge, PathResult, CycleDetection |
| `scheduler.go` | GoAScheduler, priority queues, cycle-safe DFS |
| `evaluator.go` | GoAEvaluator, coherence dynamics, gain amplification |
| `signal.go` | GoASignal, CoherenceResult |

**Coherence formula:**
```
coherence(t) = α · Σ(g_i(t)) + β · E[cycle_i(t)] + γ · diversity(env)
```
**Gain formula:**
```
Δw_i = κ · (coherence_gain) · |∇w_i| · exp(λ · cycle_detected)
```

### REDEREF Router (pkg/router/)

| Module | Responsibility |
|--------|----------------|
| `router.go` | REDEREFRouter, Thompson sampling, cost-aware routing |
| `budget.go` | TokenBudget, adaptive limits, observation tracking |

### DESC — Distributed Event Sourcing Component (pkg/desc/)

| Module | Responsibility |
|--------|----------------|
| `event_store.go` | EventStore, append-only log, WAL |
| `replayer.go` | EventReplayer, deterministic replay, state reconstitution |

### Integration (pkg/integration/)

| Module | Responsibility |
|--------|----------------|
| `bridge.go` | GoABridge, deterministic coordination layer |

---

## Go Stack (Separate Repos)

### atom-kernel v10.0.0
- **GlobalExecutionBarrier (GEB)** — node sync before tick execution
- **DeterministicClock / DeterministicRNG / DeterministicUUIDFactory**
- **LockstepMode** — strict multi-node execution
- **NetworkDeterminism** — Lamport clock, ReplayableMessageQueue, LogicalClock
- Constraints: no time.time(), no uuid4, no random in control flow

### atom-federation-core v10.1.0 (K8s control plane)
- **DeterministicControllers**: traceID from sorted spec fields (SHA256), no map iteration
- **EventStore**: type-safe GetString/GetInt64/GetBool, nil-safe operations
- **IsDuplicate() guard**: safe to retry reconcile infinitely (K4)
- **Phase-based backoff**: Pending→200ms, Running→1–2s, Stable→5s, Blocked→5s
- **Status only from EventStore**: ReconstituteWorkflowStatus(events) — no in-memory drift
- **Idempotent event emission**: key = traceID + eventType + nodeID

### atom-router v10.0.0
- Thompson sampling for cost-aware adaptive routing
- Budget enforcement with adaptive limits
- Reflection layer for observation-based adaptation

### atom-operator v10.0.0
- CRDs: ATOMCluster, Workflow, Task, Policy
- Deterministic reconciliation with event-sourcing

---

## Determinism Invariants (K2)

All implementations MUST satisfy:
1. `same spec → same traceID` — sort before hash, no map iteration
2. `same trace → same execution order` — deterministic scheduling
3. `same replay → bitwise-identical output` — replay certification
4. No `time.time()` / `uuid4()` / `random.*` in control flow paths

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| v10.2.0 | 2026-04-25 | Go stack: K8s control plane + GoA bridge |
| v10.1.0 | 2026-04-25 | Go stack: GoA + REDEREF + DESC integration |
| v10.0.0 | 2026-04-25 | Python GoA + REDEREF + Deterministic kernel |
| v9.x | 2026-04-16 | Persistence + Observability layers |
| v8.x | 2026-04-15 | Safety foundations + Circuit breaker |
| v7.x | 2026-04-14 | Federation + Kubernetes operator |