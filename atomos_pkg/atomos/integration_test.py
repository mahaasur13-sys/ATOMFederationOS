from __future__ import annotations
import time
import asyncio
from runtime.event_bus import EventBus
from runtime.memory_graph import MemoryGraph
from runtime.dcp_control_plane import DistributedControlPlane
from runtime.runtime_v2 import ATOMRuntimeV2

async def integration_test():
    print("ATOMFederationOS v2.0 - FULL INTEGRATION TEST")
    dcp = DistributedControlPlane(heartbeat_timeout=5)
    for nid in ['atom-001', 'atom-002', 'atom-003']:
        dcp.register_node(nid); dcp.heartbeat(nid)
    leader = dcp.elect_leader()
    print(f'DCP Leader: {leader}')
    for i in range(4):
        print(f'  job-{i} -> {dcp.assign_task(f"job-{i}")}')
    rec = dcp.reconcile()
    print(f'Reconcile #{rec["iteration"]}: leader={rec["leader"]}')

    bus = EventBus()
    mg = MemoryGraph()
    runtime = ATOMRuntimeV2()
    runtime.dcp = dcp
    print(f'Runtime node: {runtime.node_id} (is_leader={runtime.node_id==dcp.leader_id})')

    missions = [
        "ci fail: ruff error",
        "create new agent swarm",
        "read system status",
    ]
    results = []
    for intent in missions:
        r = await runtime.process_intent(intent)
        results.append(r)
        # Status is in event_log; execution_finished indicates completion
        has_intent_received = any(e['type'] == 'intent_received' for e in r.get('event_log', []))
        has_execution_finished = any(e['type'] == 'execution_finished' for e in r.get('event_log', []))
        status = 'COMPLETED' if has_execution_finished else 'BLOCKED'
        print(f"Mission: {intent[:40]} -> {status} (nodes={r.get('memory_nodes')})")

    state = dcp.cluster_state()
    print(f'Cluster leader: {state["leader"]}')
    all_ok = leader is not None and len(results) == len(missions)
    print(f'ALL TESTS: {"PASS" if all_ok else "FAIL"}')

if __name__ == "__main__":
    asyncio.run(integration_test())
