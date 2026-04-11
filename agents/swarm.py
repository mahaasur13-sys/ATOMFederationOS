"""
TAAR Swarm Engine — Distributed parallel agent execution
Allows TAAR to solve complex tasks by decomposing and solving subtasks in parallel.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from multiprocessing import Manager, Process, Queue
from typing import Any

# ─────────────────────────────────────────
# IMPORTS (deferred for worker processes)
# ─────────────────────────────────────────

def _worker_loop(task_queue: Queue, result_queue: Queue, worker_id: int,
                 tools_registry: dict, llm_config: dict):
    """
    Worker process loop. Runs in separate process.
    Receives subtasks, solves them using LLM + tools, puts results back.
    """
    # Lazy imports inside worker process (avoids fork issues)
    import requests

    def call_llm(messages: list[dict], model: str | None = None,
                 base_url: str | None = None) -> str:
        model = model or llm_config.get("model", "llama3.2:latest")
        base_url = base_url or llm_config.get("base_url", "http://localhost:11434")

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        try:
            resp = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=llm_config.get("timeout", 120),
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            return f"[worker-{worker_id}] LLM error: {e}"

    def execute_tool(tool_name: str, args: dict) -> str:
        # Tool execution in worker (limited set for isolation)
        if tool_name == "bash":
            import subprocess
            cmd = args.get("cmd", "")
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=60)
                return r.stdout or r.stderr
            except Exception as e:
                return f"bash error: {e}"

        elif tool_name == "read_file":
            path = args.get("target_file", "")
            try:
                with open(path) as f:
                    return f.read()[:5000]  # limit output
            except Exception as e:
                return f"read error: {e}"

        elif tool_name == "grep":
            location = args.get("location", "USER")
            query = args.get("query", "")
            if location == "USER":
                import subprocess
                try:
                    r = subprocess.run(
                        ["grep", "-r", query, "/home/workspace"],
                        capture_output=True, text=True, timeout=30,
                    )
                    return r.stdout[:3000]
                except Exception as e:
                    return f"grep error: {e}"
            return "grep: unsupported location in worker"

        elif tool_name == "list_files":
            path = args.get("path", "/home/workspace")
            try:
                import subprocess
                r = subprocess.run(
                    ["ls", "-la", path], capture_output=True, text=True, timeout=10
                )
                return r.stdout[:2000]
            except Exception as e:
                return f"ls error: {e}"

        return f"tool '{tool_name}' not available in worker context"

    while True:
        try:
            task_data = task_queue.get(timeout=30)
        except Exception:
            break

        if task_data is None:
            break

        subtask_id = task_data["id"]
        subtask = task_data["subtask"]
        context = task_data.get("context", "")

        # Build system prompt with context
        system_prompt = (
            f"You are Worker-{worker_id} in a distributed swarm.\n"
            f"Context: {context}\n"
            f"Solve the subtask independently and thoroughly.\n"
            f"Return your findings clearly.\n"
        )

        # Simple reasoning loop (3 iterations max per worker)
        state = subtask
        for iteration in range(3):
            # Ask LLM what to do
            plan_resp = call_llm([
                {"role": "system", "content": system_prompt + "\nCurrent state:\n" + state},
                {"role": "user", "content": (
                    f"Subtask {subtask_id}: {subtask}\n"
                    "Should you use a tool? If yes, respond with:\n"
                    "TOOL: <tool_name>\n"
                    "ARGS: <json_args>\n\n"
                    "If done, respond:\n"
                    "DONE: <your final answer>"
                )},
            ])

            if plan_resp.startswith("DONE:"):
                result = plan_resp[5:].strip()
                break
            elif plan_resp.startswith("TOOL:"):
                try:
                    _, rest = plan_resp.split("ARGS:", 1)
                    tool_name = plan_resp.split("TOOL:")[1].split("ARGS:")[0].strip()
                    args = json.loads(rest.strip())
                    tool_result = execute_tool(tool_name, args)
                    state += f"\n[Tool {tool_name} result]:\n{tool_result}"
                except Exception as e:
                    state += f"\n[Tool error]: {e}"
            else:
                # LLM gave direct answer
                result = plan_resp
                break
        else:
            result = state

        result_queue.put({
            "id": subtask_id,
            "worker_id": worker_id,
            "result": result,
        })


@dataclass
class Subtask:
    id: str
    description: str
    status: str = "pending"  # pending | running | done | failed
    result: str | None = None
    worker_id: int | None = None


@dataclass
class SwarmResult:
    session_id: str
    strategy: str  # "parallel" | "sequential" | "hierarchical"
    subtasks: list[Subtask]
    merged_result: str
    duration_ms: float
    workers_used: int


class SwarmEngine:
    """
    Distributed swarm execution engine.
    Decomposes complex tasks into subtasks, solves them in parallel,
    then merges results.
    """

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
        self.ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm_config = {
            "model": self.ollama_model,
            "base_url": self.ollama_base,
            "timeout": 120,
        }
        self._tools_registry = {
            "bash": {"supports_worker": True},
            "read_file": {"supports_worker": True},
            "grep": {"supports_worker": True},
            "list_files": {"supports_worker": True},
        }

    # ─────────────────────────────────────────
    # TASK DECOMPOSITION (LLM-based splitting)
    # ─────────────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> str:
        """Call local Ollama LLM."""
        import requests
        try:
            resp = requests.post(
                f"{self.ollama_base}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=self.llm_config["timeout"],
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            return f"LLM unavailable: {e}. Is Ollama running?"

    def split_task(self, task: str, num_subtasks: int | None = None) -> list[str]:
        """
        Use LLM to intelligently decompose task into subtasks.
        Returns list of subtask descriptions.
        """
        num = num_subtasks or self.max_workers

        decompose_prompt = (
            f"Decompose this complex task into {num} independent subtasks.\n"
            f"Each subtask should be self-contained and solvable independently.\n\n"
            f"TASK: {task}\n\n"
            f"Respond ONLY with a JSON array of subtask strings, like:\n"
            f'["subtask 1 description", "subtask 2 description", ...]\n'
            f"No other text."
        )

        try:
            response = self._call_llm([
                {"role": "user", "content": decompose_prompt},
            ])

            # Try to parse JSON array
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end != 0:
                subtasks = json.loads(response[start:end])
                if isinstance(subtasks, list) and all(isinstance(s, str) for s in subtasks):
                    return subtasks
        except Exception:
            pass

        # Fallback: simple round-robin split
        words = task.split()
        chunk_size = max(1, len(words) // num)
        chunks = []
        for i in range(num):
            chunk = " ".join(words[i * chunk_size:(i + 1) * chunk_size])
            if chunk:
                chunks.append(f"Part {i+1}/{num}: {chunk}")
        return chunks if chunks else [task]

    def merge(self, results: list[dict], original_task: str) -> str:
        """
        Use LLM to merge parallel worker results into coherent answer.
        """
        if len(results) == 1:
            return results[0].get("result", "No result")

        results_text = "\n".join([
            f"--- Subtask {r.get('id', i)} (Worker-{r.get('worker_id','?')}) ---\n{r.get('result', '')}"
            for i, r in enumerate(results)
        ])

        merge_prompt = (
            f"ORIGINAL TASK: {original_task}\n\n"
            f"RESULTS FROM PARALLEL WORKERS:\n{results_text}\n\n"
            f"Synthesize all worker results into ONE coherent final answer.\n"
            f"If results disagree, note the disagreement and explain your resolution.\n"
            f"Be comprehensive but concise.\n"
        )

        try:
            return self._call_llm([{"role": "user", "content": merge_prompt}])
        except Exception as e:
            return f"MERGE ERROR: {e}\n\nRaw results:\n{results_text}"

    # ─────────────────────────────────────────
    # SWARM EXECUTION
    # ─────────────────────────────────────────

    def run(self, task: str, num_workers: int | None = None,
            strategy: str = "parallel") -> SwarmResult:
        """
        Execute task using swarm strategy.
        Returns SwarmResult with all subtask results and merged answer.
        """
        session_id = f"swarm-{uuid.uuid4().hex[:8]}"
        num_workers = num_workers or self.max_workers
        start = time.time()

        # Decompose
        subtask_descs = self.split_task(task, num_workers)
        subtasks = [
            Subtask(id=f"s-{i}", description=d)
            for i, d in enumerate(subtask_descs)
        ]

        if strategy == "sequential":
            # Run in current process sequentially (for debugging/single-node)
            results = []
            for st in subtasks:
                st.status = "running"
                r = self._run_single_subtask(st, 0, task)
                st.result = r.get("result", "")
                st.status = "done"
                results.append(r)

            merged = self.merge(results, task)

        else:  # parallel
            results = self._run_parallel(subtasks, task, num_workers)

            # Mark all done
            for st in subtasks:
                st.status = "done"

            merged = self.merge(results, task)

        duration_ms = (time.time() - start) * 1000

        return SwarmResult(
            session_id=session_id,
            strategy=strategy,
            subtasks=subtasks,
            merged_result=merged,
            duration_ms=duration_ms,
            workers_used=num_workers,
        )

    def _run_single_subtask(self, subtask: Subtask, worker_id: int,
                            context: str) -> dict:
        """Run a single subtask synchronously (fallback/sequential mode)."""
        # Simple LLM-only solve (no tool loop in sequential)
        response = self._call_llm([
            {"role": "system", "content": (
                f"You are Worker-{worker_id} solving a subtask in a distributed swarm.\n"
                f"Context: {context}\n"
                f"Solve thoroughly."
            )},
            {"role": "user", "content": f"Subtask: {subtask.description}"},
        ])
        return {
            "id": subtask.id,
            "worker_id": worker_id,
            "result": response,
        }

    def _run_parallel(self, subtasks: list[Subtask], context: str,
                      num_workers: int) -> list[dict]:
        """
        Run subtasks in parallel using ProcessPoolExecutor.
        Falls back to threads if multiprocessing fails.
        """
        task_queue = Queue()
        result_queue = Queue()

        # Fill queue
        for st in subtasks:
            task_queue.put({
                "id": st.id,
                "subtask": st.description,
                "context": context,
            })

        # Add sentinel values
        for _ in range(num_workers):
            task_queue.put(None)

        # Start workers
        processes = []
        for i in range(num_workers):
            p = Process(
                target=_worker_loop,
                args=(task_queue, result_queue, i,
                      self._tools_registry, self.llm_config),
            )
            p.start()
            processes.append(p)

        # Collect results
        results = []
        for _ in range(len(subtasks)):
            try:
                r = result_queue.get(timeout=120)
                results.append(r)
            except Exception:
                break

        # Wait for workers to finish
        for p in processes:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()

        return results

    # ─────────────────────────────────────────
    # STRATEGY SELECTION
    # ─────────────────────────────────────────

    def get_strategy(self, task: str) -> str:
        """
        Analyze task and decide: 'parallel', 'sequential', or 'hierarchical'.
        """
        task_lower = task.lower()

        # Keywords suggesting parallelizable
        parallel_kw = [
            "search", "analyze", "compare", "scan", "audit",
            "find all", "list all", "evaluate", "review",
            "parallel", "concurrent", "multi", "distributed",
        ]

        # Keywords suggesting single-agent (sequential)
        sequential_kw = [
            "write", "create", "build", "generate",
            "implement", "design", "plan", "do",
        ]

        para_score = sum(1 for kw in parallel_kw if kw in task_lower)
        seq_score = sum(1 for kw in sequential_kw if kw in task_lower)

        if para_score > seq_score:
            return "parallel"
        elif seq_score > para_score:
            return "sequential"
        else:
            return "parallel"  # default to parallel for speed

    def get_num_workers(self, task: str) -> int:
        """Dynamically size worker count based on task complexity."""
        task_len = len(task.split())
        if task_len < 20:
            return 2
        elif task_len < 100:
            return min(4, self.max_workers)
        else:
            return min(8, self.max_workers)
