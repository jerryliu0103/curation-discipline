#!/usr/bin/env python3
"""PreToolUse/Bash hook: stop and ask before a command reaches the wrong datastore.

THE PROBLEM THIS SOLVES

    A project moved its canonical database to a server and left a stale local copy
    behind. The rule "never use the local copy" was written down and, for a month,
    quietly ignored -- an audit found every one of five agent definition files still
    pointing at it.

    Nobody was careless. The rule had no teeth: reading the stale copy returns plausible
    old data, writing to it succeeds, and NEITHER PRODUCES AN ERROR. A rule that
    produces no feedback when broken is not a rule.

    This hook turns it into something that stops and asks.

ASK, NOT DENY

    Every path below has a legitimate use -- offline lookup, dry-running a batch against
    a disposable copy. Blocking outright gets routed around, and then you have no
    visibility at all. The goal is "you cannot walk into this by accident", not "you
    cannot get here".

WHY A HOOK AND NOT A PERMISSION RULE

    Bash permission rules match on a command prefix. Real commands are compound --
    `cd x && psql ...` -- so the prefix never matches and the rule never fires. Settings
    rules are a useful backstop for the simple cases; the actual interception is here.

CONFIGURE ME

    Edit PATTERNS below to name your own traps. Shipping with placeholder patterns that
    match nothing would make this file decoration -- so the examples are real, and the
    point is the shape, not the specific strings.

    Keep the sys.stdout.reconfigure line. A hook that raises UnicodeEncodeError on a
    non-UTF-8 console exits non-zero with no decision output, and PreToolUse treats that
    as "no opinion" -- the guard fails open while looking like it works.
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# (compiled pattern, reason shown to the human)
#
# Replace these with your project's own traps. The three shapes below cover most of
# what goes wrong in practice:
#   1. an environment variable that still points at a superseded datastore
#   2. an escape-hatch flag that lets a script fall back to a local copy
#   3. an environment override that disables a connection check
PATTERNS = [
    (
        re.compile(r'(psql|pg_dump|pg_restore|mysql|sqlite3)\b[^|;&]*"?\$STALE_DB_URL"?'),
        "uses $STALE_DB_URL directly. That variable points at a superseded local copy: "
        "reads return an old snapshot and writes never reach the canonical store, and "
        "neither reports an error. Resolve the canonical URL instead.",
    ),
    (
        re.compile(r"--allow-local\b"),
        "passes --allow-local, which lets the script fall back to a local copy when it "
        "cannot reach the canonical store.",
    ),
    (
        re.compile(r"\bDB_ALLOW_LOCAL\s*=\s*1\b"),
        "sets DB_ALLOW_LOCAL=1, which disables the connection check and permits the "
        "local fallback.",
    ),
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""

    for pattern, reason in PATTERNS:
        if pattern.search(command):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": (
                                "This command touches the wrong datastore: " + reason
                            ),
                        }
                    },
                    ensure_ascii=False,
                )
            )
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
