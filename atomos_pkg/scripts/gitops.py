#!/usr/bin/env python3
"""
ATOM OS — GitOps Version Manager
Tag, rollback, and audit the repository state.
"""
import subprocess
import sys
import datetime as dt

CMDS = {
    "tag":    lambda a: _tag(a),
    "rollback": lambda a: _rollback(a),
    "history":  lambda _: _history(),
    "diff":    lambda a: _diff(a),
    "audit":   lambda _: _audit(),
}

def _tag(args):
    ver = args[0] if args else f"v{dt.date.today().isoformat().replace('-','.')}"
    msg = args[1] if len(args) > 1 else f"Auto-tag {ver}"
    r = subprocess.run(["git", "tag", "-a", ver, "-m", msg], capture_output=True, text=True)
    print(f"{'✅' if r.returncode == 0 else '❌'} Tag {ver}: {r.stderr.strip() or 'OK'}")
    return r.returncode == 0

def _rollback(tag):
    r = subprocess.run(["git", "checkout", tag], capture_output=True, text=True)
    print(f"{'✅' if r.returncode == 0 else '❌'} Rollback to {tag}: {r.stderr.strip() or 'OK'}")
    return r.returncode == 0

def _history():
    r = subprocess.run(["git", "log", "--oneline", "-20"], capture_output=True, text=True)
    print(r.stdout)

def _diff(tag):
    r = subprocess.run(["git", "diff", tag, "HEAD", "--stat"], capture_output=True, text=True)
    print(r.stdout or r.stderr)

def _audit():
    r = subprocess.run(["git", "log", "--format=%H %s", "--all"], capture_output=True, text=True)
    lines = r.stdout.strip().split("\n")
    tags_r = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True)
    tags = tags_r.stdout.strip().split("\n") if tags_r.returncode == 0 else []
    print(f"Commits: {len(lines)}")
    print(f"Tags: {tags}")
    return True

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "history"
    args = sys.argv[2:]
    ok = CMDS.get(cmd, lambda a: print(f"Unknown: {cmd}"))(args)
    sys.exit(0 if ok else 1)
