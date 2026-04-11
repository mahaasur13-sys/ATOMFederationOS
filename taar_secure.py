#!/usr/bin/env python3
"""
TAAR v14-secure — SECURE AI EXECUTION ENGINE
Human-in-the-loop. User approves every action.

Commands:
  /plan <task>   - Show plan only
  /run <task>    - Execute with user approval
  /fix <ci_log>  - DevOps mode
  /audit         - Show history
  /mode <mode>   - Set mode (read/plan/safe_exec/write)
"""
import sys
import uuid
sys.path.insert(0, "agents")
sys.path.insert(0, ".")

from user_gateway import gateway, ExecutionMode
from secure_execution_engine import SecureExecutionEngine
from devops_agent import DevOpsAgent


def cmd_plan(task: str) -> str:
    """Parse intent, show plan, ask for approval."""
    engine = SecureExecutionEngine(gateway)
    steps, impact = engine.parse_intent(task)
    simulation = engine.simulate(steps)

    plan = gateway.build_plan(task, steps, impact, simulation)
    request = plan.to_approval_request()

    return (
        f"\n{'='*60}\n"
        f"TAAR v14-secure | MODE: {gateway.session_mode.value}\n"
        f"{'='*60}\n"
        f"{request}\n"
        f"\n[ACTION_ID: {plan.action_id}]\n"
        f"[STATUS: PENDING APPROVAL]\n"
    )


def cmd_run(task: str, user_response: str = None) -> str:
    """
    Execute task. Requires explicit user approval.
    user_response: "yes", "no", or edited command
    """
    engine = SecureExecutionEngine(gateway)
    steps, impact = engine.parse_intent(task)
    simulation = engine.simulate(steps)
    plan = gateway.build_plan(task, steps, impact, simulation)

    if not user_response:
        return plan.to_approval_request()

    response = user_response.strip().lower()

    # Handle "no"
    if response == "no" or response == "n":
        gateway.deny(plan.action_id, "user_denied")
        return f"[DENIED] Action {plan.action_id} rejected by user."

    # Handle "yes" or edited command
    if response == "yes" or response == "y" or response.startswith("edit:"):
        edited_cmd = user_response[5:].strip() if user_response.startswith("edit:") else None
        gateway.approve(plan.action_id, edited_cmd)

        # Execute approved steps
        def executor(cmd):
            import subprocess
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.stdout[:200] if r.stdout else r.stderr[:200] if r.stderr else "OK"

        results = engine.execute_approved(steps, executor)

        output = [f"\n{'='*60}",
                  f"EXECUTION LOG | {plan.action_id}",
                  f"{'='*60}"]
        for r in results:
            status_icon = "✅" if r["status"] == "executed" else "❌" if r["status"] == "blocked" else "⚠️"
            output.append(f"{status_icon} step_{r['step']}: {r['command'][:50]}")
            output.append(f"     status: {r['status']}")
            if "result" in r:
                output.append(f"     result: {str(r['result'])[:100]}")
            if "reason" in r:
                output.append(f"     reason: {r['reason']}")

        # Audit log
        audit_entry = gateway.log_execution(
            plan.action_id,
            "; ".join(s["command"] for s in steps),
            f"{len([r for r in results if r['status']=='executed'])}/{len(results)} executed",
            True
        )
        output.append(f"\nAUDIT: {audit_entry['hash']}")

        return "\n".join(output)

    return "Unknown response. Use: yes/no/edit:<command>"


def cmd_fix(ci_log: str) -> str:
    """DevOps mode - analyze CI failure."""
    agent = DevOpsAgent()
    result = agent.run(ci_logs=ci_log, repo_path=".")

    return (
        f"\n{'='*60}\n"
        f"DEV OPS MODE | CI Analysis\n"
        f"{'='*60}\n"
        f"Status: {result.get('status', 'unknown')}\n"
        f"Root cause: {result.get('analysis', {}).get('root_cause', 'unknown')}\n"
        f"Suggestion: {result.get('analysis', {}).get('suggestion', 'N/A')}\n"
    )


def cmd_audit() -> str:
    """Show audit history."""
    entries = gateway.get_audit_log(20)
    if not entries:
        return "[AUDIT] No entries yet."

    output = [f"\n{'='*60}",
              f"AUDIT LOG | {len(entries)} entries",
              f"{'='*60}"]
    for e in entries:
        approved = "✅" if e.get("user_approved") else "❌"
        cmd_preview = e.get("command", "")[:50]
        hash_val = e.get("hash", "")
        ts = e.get("timestamp", "")[:19]
        output.append(f"{approved} [{ts}] {cmd_preview}... [{hash_val}]")

    return "\n".join(output)


def cmd_mode(mode_str: str) -> str:
    """Set execution mode."""
    try:
        mode = ExecutionMode(mode_str.lower())
        gateway.set_mode(mode)
        return f"[MODE] Set to: {mode.value}"
    except:
        valid = [m.value for m in ExecutionMode]
        return f"[MODE] Unknown. Valid: {valid}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="TAAR v14-secure CLI")
    parser.add_argument("command", nargs="?", help="/plan, /run, /fix, /audit, /mode")
    parser.add_argument("args", nargs="*", help="Task or mode value")
    parser.add_argument("--response", "-r", default=None, help="User response (yes/no)")
    args = parser.parse_args()

    if not args.command:
        print(__doc__)
        print("\nTAAR v14-secure READY")
        print("Human-in-the-loop: ON")
        print("Autonomy: DISABLED")
        print("\nWaiting for command...")
        return

    task = " ".join(args.args)

    if args.command == "/plan":
        print(cmd_plan(task))
    elif args.command == "/run":
        print(cmd_run(task, args.response))
    elif args.command == "/fix":
        print(cmd_fix(task))
    elif args.command == "/audit":
        print(cmd_audit())
    elif args.command == "/mode":
        print(cmd_mode(task))
    else:
        print(f"Unknown command: {args.command}")
        print("Use: /plan, /run, /fix, /audit, /mode")


if __name__ == "__main__":
    main()
