"""
TAAR — Tool-Augmented Agent Runtime
LangGraph Core: planner → executor → reviewer
"""

from __future__ import annotations

import json
import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

# ─────────────────────────────────────────
# STATE SCHEMA
# ─────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    DONE = "done"
    FAILED = "failed"

class ReviewVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION = "revision"

@dataclass
class ToolCall:
    """Single tool invocation record."""
    tool_name: str
    args: dict[str, Any]
    result: Any | None = None
    error: str | None = None
    latency_ms: float | None = None

@dataclass
class AgentMessage:
    """Single message in conversation."""
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    tool_calls: list[ToolCall] | None = None

@dataclass
class PlanStep:
    """Single step in the plan."""
    step_id: int
    description: str
    tool_name: str | None = None
    args: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: str | None = None

@dataclass
class TAARState:
    """Root state passed through all nodes."""
    task: str
    messages: list[AgentMessage] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    max_iterations: int = 20
    iteration: int = 0
    verdict: ReviewVerdict | None = None
    revision_notes: str | None = None
    final_result: Any | None = None
    error: str | None = None

# LangGraph uses TypedDict for state
class GraphState(TypedDict):
    task: str
    messages: list[dict]
    plan: list[dict]
    current_step: int
    max_iterations: int
    iteration: int
    verdict: str | None
    revision_notes: str | None
    final_result: Any | None
    error: str | None

# ─────────────────────────────────────────
# STATE SERIALIZATION HELPERS
# ─────────────────────────────────────────

def _serialize_state(state: TAARState) -> GraphState:
    """Convert TAARState dataclass to LangGraph-compatible dict."""
    return GraphState(
        task=state.task,
        messages=[{"role": m.role, "content": m.content, "tool_calls": [(tc.tool_name, tc.args, tc.result) for tc in (m.tool_calls or [])]} for m in state.messages],
        plan=[{"step_id": s.step_id, "description": s.description, "tool_name": s.tool_name, "args": s.args, "status": s.status.value, "result": s.result, "error": s.error} for s in state.plan],
        current_step=state.current_step,
        max_iterations=state.max_iterations,
        iteration=state.iteration,
        verdict=state.verdict.value if state.verdict else None,
        revision_notes=state.revision_notes,
        final_result=state.final_result,
        error=state.error,
    )

def _deserialize_state(graph_state: GraphState) -> TAARState:
    """Convert LangGraph dict back to TAARState."""
    messages = [AgentMessage(role=m["role"], content=m["content"], tool_calls=[ToolCall(tool_name=tc[0], args=tc[1], result=tc[2]) for tc in (m.get("tool_calls") or [])]) for m in graph_state["messages"]]
    plan = [PlanStep(step_id=s["step_id"], description=s["description"], tool_name=s.get("tool_name"), args=s.get("args"), status=TaskStatus(s["status"]), result=s.get("result"), error=s.get("error")) for s in graph_state["plan"]]
    return TAARState(
        task=graph_state["task"],
        messages=messages,
        plan=plan,
        current_step=graph_state["current_step"],
        max_iterations=graph_state["max_iterations"],
        iteration=graph_state["iteration"],
        verdict=ReviewVerdict(graph_state["verdict"]) if graph_state.get("verdict") else None,
        revision_notes=graph_state.get("revision_notes"),
        final_result=graph_state.get("final_result"),
        error=graph_state.get("error"),
    )

# ─────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────

class ToolRegistry:
    """Maps tool names to actual Zo/native callables."""

    def __init__(self):
        self._tools: dict[str, callable] = {}

    def register(self, name: str, fn: callable):
        self._tools[name] = fn

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {self.list_tools()}")
        fn = self._tools[tool_name]
        return fn(**args)

# Global registry (singleton)
TOOL_REGISTRY = ToolRegistry()

# ─────────────────────────────────────────
# GRAPH NODES
# ─────────────────────────────────────────

def planner_node(state: GraphState) -> GraphState:
    """
    PLANNER: analyze task → produce execution plan (list of steps).
    Uses LLM to decompose the task into tool-call steps.
    """
    from tools_adapter import get_llm

    task = state["task"]
    messages = state["messages"]

    # Build prompt for LLM
    available_tools = TOOL_REGISTRY.list_tools()
    system_prompt = (
        "You are TAAR Planner. Decompose the task into concrete steps.\n"
        f"Available tools: {available_tools}\n"
        "Respond ONLY with JSON: {\"steps\": [{\"description\": \"...\", \"tool_name\": \"...\" | null, \"args\": {{...}} | null}]}\n"
        "If no tool needed, set tool_name=null. Max 10 steps."
    )

    llm = get_llm()
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        *[{"role": m["role"], "content": m["content"]} for m in messages],
        {"role": "user", "content": f"Task: {task}"},
    ])

    try:
        parsed = json.loads(response.content)
        steps = parsed.get("steps", [])
    except Exception:
        # Fallback: single-step text plan
        steps = [{"description": response.content, "tool_name": None, "args": None}]

    plan = [
        {
            "step_id": i,
            "description": s["description"],
            "tool_name": s.get("tool_name"),
            "args": s.get("args") or {},
            "status": "pending",
            "result": None,
            "error": None,
        }
        for i, s in enumerate(steps)
    ]

    state["plan"] = plan
    state["current_step"] = 0
    state["messages"] = messages + [{"role": "assistant", "content": f"Plan: {json.dumps(plan, indent=2)}", "tool_calls": None}]

    return state


def executor_node(state: GraphState) -> GraphState:
    """
    EXECUTOR: run current step's tool, store result.
    """
    import time

    task = state["task"]
    plan = state["plan"]
    current_step = state["current_step"]
    messages = state["messages"]

    if current_step >= len(plan):
        # No more steps
        return state

    step = plan[current_step]
    step["status"] = "in_progress"

    result = None
    error = None
    tool_calls_result = None

    if step.get("tool_name"):
        tool_name = step["tool_name"]
        args = step.get("args") or {}

        start = time.time()
        try:
            raw_result = TOOL_REGISTRY.execute(tool_name, args)
            # Serialize result for dict state
            if hasattr(raw_result, "__dict__"):
                result = str(raw_result)
            elif isinstance(raw_result, (dict, list, str, int, float, bool, type(None))):
                result = raw_result
            else:
                result = str(raw_result)
            step["result"] = result
            step["status"] = "pending"  # awaiting review will mark done
            tool_calls_result = [(tool_name, args, result)]
        except Exception as e:
            error = str(e)
            step["error"] = error
            step["status"] = "failed"
    else:
        # No tool — LLM synthesizes intermediate result
        from tools_adapter import get_llm
        llm = get_llm()
        response = llm.invoke([
            {"role": "system", "content": "You are TAAR Executor. Based on the current step description, provide the result."},
            {"role": "user", "content": f"Step: {step['description']}\nTask: {task}"}
        ])
        result = response.content
        step["result"] = result
        tool_calls_result = None

    elapsed_ms = int((time.time() - start) * 1000) if step.get("tool_name") else None

    messages = messages + [
        {"role": "assistant", "content": f"Step {current_step}: {step['description']}", "tool_calls": tool_calls_result},
    ]

    state["plan"] = plan
    state["messages"] = messages

    return state


def reviewer_node(state: GraphState) -> GraphState:
    """
    REVIEWER: approve/reject/revise current step result.
    """
    from tools_adapter import get_llm

    task = state["task"]
    plan = state["plan"]
    current_step = state["current_step"]
    messages = state["messages"]

    if current_step >= len(plan):
        state["verdict"] = "approved"
        return state

    step = plan[current_step]

    system_prompt = (
        "You are TAAR Reviewer. Evaluate if the step result is satisfactory.\n"
        "Respond ONLY with JSON: {\"verdict\": \"approved\" | \"rejected\" | \"revision\", \"notes\": \"...\"}\n"
        "approved = step is done, move to next.\n"
        "rejected = step failed critically, abort.\n"
        "revision = step partially done, needs rework."
    )

    llm = get_llm()
    step_description = step["description"]
    step_result = step.get("result") or step.get("error") or "No result"

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task}\nStep: {step_description}\nResult: {step_result}"}
    ])

    try:
        parsed = json.loads(response.content)
        verdict = parsed.get("verdict", "approved")
        notes = parsed.get("notes", "")
    except Exception:
        verdict = "approved"
        notes = ""

    state["verdict"] = verdict
    state["revision_notes"] = notes

    if verdict == "approved":
        step["status"] = "done"
        state["current_step"] = current_step + 1
    elif verdict == "rejected":
        step["status"] = "failed"
        state["error"] = f"Step {current_step} rejected: {notes}"
    else:  # revision
        step["status"] = "revision"
        # Re-execute same step
        pass

    return state


def aggregator_node(state: GraphState) -> GraphState:
    """
    AGGREGATOR: collect all results → final output.
    Called when all steps approved or max iterations reached.
    """
    from tools_adapter import get_llm

    task = state["task"]
    plan = state["plan"]
    messages = state["messages"]

    if state.get("error"):
        state["final_result"] = f"FAILED: {state['error']}"
        return state

    # Summarize results
    results = []
    for step in plan:
        if step.get("result"):
            results.append(f"Step {step['step_id']}: {step['description']} → {step['result']}")
        elif step.get("error"):
            results.append(f"Step {step['step_id']}: {step['description']} → ERROR: {step['error']}")

    results_text = "\n".join(results) if results else "No results"

    system_prompt = (
        "You are TAAR Aggregator. Synthesize step results into a final answer.\n"
        "Keep it concise and actionable."
    )

    llm = get_llm()
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {task}\n\nResults:\n{results_text}"}
    ])

    state["final_result"] = response.content
    return state


# ─────────────────────────────────────────
# ROUTING LOGIC
# ─────────────────────────────────────────

def should_continue(state: GraphState) -> str:
    """LangGraph conditional edge: next node selector."""
    current_step = state["current_step"]
    plan = state["plan"]
    iteration = state["iteration"]
    max_iter = state["max_iterations"]
    verdict = state.get("verdict")
    error = state.get("error")

    if error:
        return "aggregator"

    if iteration >= max_iter:
        return "aggregator"

    if current_step >= len(plan):
        return "aggregator"

    if verdict == "rejected":
        return "aggregator"

    if verdict == "approved":
        return "executor"

    if verdict == "revision":
        return "executor"

    return "executor"


def route_after_executor(state: GraphState) -> str:
    return "reviewer"


def route_after_reviewer(state: GraphState) -> str:
    return should_continue(state)


# ─────────────────────────────────────────
# GRAPH CONSTRUCTION
# ─────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and return the LangGraph StateGraph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("aggregator", aggregator_node)

    # Edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "executor": "executor",
            "aggregator": "aggregator",
        }
    )
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "reviewer": "reviewer",
        }
    )
    graph.add_edge("aggregator", END)

    return graph


# Lazy-compiled graph singleton
_compiled_graph = None

def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


# ─────────────────────────────────────────
# RUN ENTRYPOINT
# ─────────────────────────────────────────

def run_task(task: str, max_iterations: int = 20) -> dict[str, Any]:
    """
    Main entrypoint: TASK → GRAPH → EXEC → RESULT.
    Returns final state dict.
    """
    initial_state: GraphState = {
        "task": task,
        "messages": [],
        "plan": [],
        "current_step": 0,
        "max_iterations": max_iterations,
        "iteration": 0,
        "verdict": None,
        "revision_notes": None,
        "final_result": None,
        "error": None,
    }

    compiled = get_compiled_graph()

    # Run with iteration tracking via recursion
    result = _run_with_iterations(compiled, initial_state, max_iterations)
    return result


def _run_with_iterations(compiled, state: GraphState, remaining: int) -> dict[str, Any]:
    """Run graph, tracking iterations manually since LangGraph handles internal loops."""
    if remaining <= 0:
        state["final_result"] = state.get("final_result") or "Max iterations reached"
        return state

    # Run one pass through the graph
    result = compiled.invoke(state)

    # Check if done
    if result.get("error") or result.get("current_step", 0) >= len(result.get("plan", [])):
        return result

    # Increment iteration and continue
    result["iteration"] = state.get("iteration", 0) + 1
    return _run_with_iterations(compiled, result, remaining - 1)
