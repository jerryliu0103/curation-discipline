#!/usr/bin/env python3
"""Adversarial self-test for the guards. Run it: python hooks/test_hooks.py

This file exists because of silent-failure-hunting entry 5: a guard that dies before
it prints a decision fails OPEN, and looks identical to a guard that is working. The
only way to know a guard blocks what it claims to block is to feed it those inputs and
assert on the result.

No pytest, no dependencies -- so there is no excuse not to run it.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
READONLY = HERE / "readonly-guard.py"
CANONICAL = HERE / "canonical-store-guard.py"

BLOCK = "block"      # exit 2, message on stderr
ASK = "ask"          # exit 0, permissionDecision=ask on stdout
ALLOW = "allow"      # exit 0, no output

CASES = [
    # (hook, command, expected)
    (READONLY, 'psql "$DB" -c "SELECT * FROM items LIMIT 5"', ALLOW),
    (READONLY, 'psql "$DB" -c "INSERT INTO items VALUES (1)"', BLOCK),
    (READONLY, 'psql "$DB" -c "delete from items"', BLOCK),
    (READONLY, 'cd /project && psql "$DB" -c "UPDATE items SET x=1"', BLOCK),
    (READONLY, 'psql "$DB" -c "DROP TABLE items"', BLOCK),
    (READONLY, 'psql "$DB" -c "SELECT created_at, updated_at FROM items"', ALLOW),
    # Deliberate false positive: a SELECT whose literal contains a write keyword is
    # blocked. Stripping quoted regions to avoid this breaks the guard entirely --
    # see the comment above WRITE_SQL in readonly-guard.py. Over-blocking is the
    # correct direction to be wrong in.
    (READONLY, "psql \"$DB\" -c \"SELECT * FROM logs WHERE note LIKE '%DELETE%'\"", BLOCK),
    (READONLY, 'psql "$DB" -c "SELECT 1" > /tmp/out.txt', BLOCK),
    (READONLY, "ls -la", ALLOW),
    (CANONICAL, 'psql "$STALE_DB_URL" -c "SELECT 1"', ASK),
    (CANONICAL, "node scripts/sync.js --allow-local", ASK),
    (CANONICAL, "DB_ALLOW_LOCAL=1 node server.js", ASK),
    (CANONICAL, 'psql "$DB_URL" -c "SELECT 1"', ALLOW),
]


def run(hook: Path, command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode == 2:
        return BLOCK, proc.stderr.strip()
    if proc.returncode != 0:
        return f"crashed({proc.returncode})", (proc.stderr or "").strip()
    out = proc.stdout.strip()
    if not out:
        return ALLOW, ""
    try:
        decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "malformed", out
    return decision, out


def main() -> int:
    failures = 0
    for hook, command, expected in CASES:
        got, detail = run(hook, command)
        ok = got == expected
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  {hook.name:26} expected={expected:6} got={got:10} {command}")
        if not ok and detail:
            print(f"      -> {detail}")
    print()
    if failures:
        print(f"{failures} of {len(CASES)} cases failed.")
        print("A guard that does not block what it claims to block is worse than no guard:")
        print("it is a guard everyone believes in.")
        return 1
    print(f"All {len(CASES)} cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
