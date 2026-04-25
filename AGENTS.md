# ATOMFederationOS — Agent Memory

## Current Version: v10.0.0

## Architecture Map

### v10.0.0 — NEW: GoA + REDEREF Integration

#### atom-router (NEW — v10.0.0)
- `pkg/router/router.go` — **REDEREF router** with Thompson sampling
  - `Router.Dispatch()` — deterministic agent selection via belief-guided delegation
  - `DeterministicSampler` (from atom-kernel) for all random draws
  - Thompson sampling via Box-Muller with deterministic RNG
  - All routing decisions logged to DESC EventStore for reflection
- `pkg/router/budget.go` — BudgetEnforcer (per-task + global token budgets)
- `pkg/reflection/re_router.go` — reflection-driven re-routing (REDEREF core)
  - `ReflectionTrigger.ShouldReroute()` — quality + consecutive-fail gating
  - `ReRouter.AnalyzeAndReroute()` — reads EventStore for outcome history

#### atom-federation/pkg/goa (NEW — v10.0.0)
- `pkg/goa/graph.go` — GoA AgentGraph (nodes + directed edges + MessageBus)
- `pkg/goa/sampling.go` — DeterministicSampler (training-free type relevance scoring)
  - Node sampling: exact match=1.0, adjacent=0.5, cross-domain=0.1
  - Deterministic shuffle-tiebreak via GlobalExecutionSequencer RNG
- `pkg/goa/engine.go` — ExecutionEngine (sample → dispatch → message pass → aggregate)
- `pkg/goa/aggregator.go` — WeightedAggregator (softmax quality-weighted pooling)

### v10 Architecture (all modules)

#### atom-kernel (v10.0.0)
- `pkg/deterministic/deterministic.go` — DeterministicClock, DeterministicRNG, GlobalExecutionSequencer, GlobalTieBreaker
- Deterministic RNGs: seed from tick + agentID, reproducible across nodes
- **Key dependency**: `GetRNG(name)` — used by atom-router Thompson sampling + GoA sampling

#### atom-operator (v10.0.0)
- Kubernetes operator with ATOMCluster, Workflow, Task CRDs
- Reconciliation loops with deterministic scheduling
- SBS enforcement gate in reconciler

#### atom-agent (v10.0.0)
- Agent runner: executes tasks via binary sandbox
- Registers with atom-router on startup
- Reports execution outcomes for belief updates

#### atom-federation (v10.0.0)
- LogicalClock (Lamport-style), ReplayableMessageQueue, DeterministicFanoutOrder
- `pkg/goa/` — NEW: Graph-of-Agents implementation

## GoA + REDEREF Integration Flow

```
Task Input
    ↓
[GoA: DeterministicSampler.sample()]  ← selects k best agents (training-free)
    ↓
[REDEREF: Router.Dispatch()]         ← Thompson sampling via deterministic RNG
    ↓
[atom-kernel: GlobalExecutionSequencer.Now()] ← tick logging
    ↓
[atom-agent: RunBatch()]            ← parallel execution
    ↓
[DESC: EventStore logging]           ← all routing decisions + outcomes
    ↓
[REDEREF: ReRouter.AnalyzeAndReroute()] ← reflection → belief update
    ↓
[atom-router: UpdateBelief()]        ← Bayesian belief update
    ↓
[GoA: WeightedAggregator.Aggregate()] ← quality-weighted pooling
    ↓
Final Output
```

## Key Invariants

- All Thompson sampling uses `DeterministicRNG.Float64Range()` — no `math/rand`
- All routing decisions logged to EventStore with tick = `GlobalExecutionSequencer.Now()`
- SBS verification gate called before dispatch (via atom-operator reconciler)
- `DeterministicSampler` is training-free (no ML model, no fine-tuning)
- BudgetEnforcer checked before every dispatch (global + per-task limits)

## Phase 1 Priority (Week 1-2)

1. **atom-router**: Complete Router + BudgetEnforcer + tests ✅ (this session)
2. **atom-federation/goa**: Complete graph + sampler + aggregator ✅ (this session)
3. **Integration**: wire GoA.ExecutionEngine → atom-router.Dispatch → DESC.EventStore
4. **SBS Gate**: Add `sbs.verify()` call in router.Dispatch before agent selection
5. **Integration tests**: GoA-selects → REDEREF-routes → belief-updates → reroutes correctly

## Phase 2 Priority (Week 3-4)

6. **atom-operator**: Add RouterConfig CRD + reconciliation
7. **atom-agent**: AgentRegistry population on startup
8. **Meta-RL adaptation**: Hook DecisionMemory outcomes into belief Mu/Sigma

## Phase 3 Priority (Week 5-8)

9. **AstroFinSentinelV5**: Replace ad-hoc routing with atom-router
10. **Cost dashboards**: Visualize token savings from REDEREF (expect 28% reduction)
11. **Lockstep mode**: Add GoA execution under GlobalExecutionBarrier

## Constraints (v10 HARD LIMITS)

| # | Constraint | Rationale |
|---|------------|-----------|
| C1 | No `math/rand` in routing/sampling | Breaks determinism |
| C2 | All routing decisions → EventStore | Enables reflection |
| C3 | SBS gate before dispatch | No unsafe execution |
| C4 | BudgetEnforcer checked before dispatch | Cost control |
| C5 | Training-free sampling only | No external ML dependency |

## Test Status (2026-04-25)

- atom-router: unit tests written, 4 test cases (determinism, registry, belief, budget)
- atom-federation/goa: unit tests written, 5 test cases (determinism, graph, bus, aggregator, concurrent)
- Both modules use `DeterministicRNG` — determinism is structurally enforced

## Pending

- Phase 2: atom-operator RouterConfig CRD + reconciliation
- Phase 2: atom-agent registration flow
- Phase 3: AstroFinSentinelV5 routing replacement
- Phase 3: Meta-RL belief adaptation
- Phase 4: Lockstep GoA execution
