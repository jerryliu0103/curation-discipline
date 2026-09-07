#!/usr/bin/env python3
"""PreToolUse/Bash hook: reject anything that is not a read-only database command.

Attach this to agents that must never write (validator, reader). Their frontmatter
already drops Write and Edit, but that does not cover Bash — and Bash is how a
database actually gets written to. This closes that gap.

Deny, not ask: an agent whose entire job is verification has no legitimate reason to
write, so there is nothing to negotiate. Use canonical-store-guard.py for the paths
that do have legitimate uses.

WHY PYTHON AND NOT A SHELL ONE-LINER
    The obvious version is three lines of bash with jq. It works until it runs on a
    machine without jq -- and then it exits non-zero with no decision output, which
    on PreToolUse means the command goes through. A guard that fails open looks
    exactly like a guard that is working. Python 3 is already required by Claude
    Code tooling on every platform; jq is not.

WHY THE EXPLICIT UTF-8 RECONFIGURE BELOW
    Not decoration. A hook that printed a non-ASCII character on a console whose
    codepage was not UTF-8 raised UnicodeEncodeError, exited non-zero with nothing on
    stdout, and silently stopped blocking anything. It was found by piping crafted
    input through it by hand -- three commands that should have been blocked were
    not. If you edit the messages below, keep this line.
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Statements that modify data or schema. Word-bounded so that column names like
# `created_at` or `updated_at` do not trip it.
WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER)\b",
    re.IGNORECASE,
)

# Shell redirection into a file. A read-only agent should report findings in its
# response, not write them somewhere.
WRITE_SHELL = re.compile(r"(^|\s)(>|>>)\s*\S", re.MULTILINE)

# NO STRING STRIPPING -- AND THAT IS DELIBERATE.
#
# The obvious refinement is to strip quoted literals first, so that
#     SELECT * FROM logs WHERE note LIKE '%DELETE%'
# is not read as a write. The self-test caught why that is wrong: SQL reaches psql
# INSIDE quotes -- `psql -c "INSERT INTO ..."` -- so stripping quoted regions strips
# the statement itself, and the guard allows every write while reporting success.
# That bug was live for exactly one test run, which is the entire argument for
# shipping test_hooks.py alongside this file.
#
# So the guard matches the raw command and over-blocks instead. A read-only agent
# occasionally refused a SELECT whose literal contains the word DELETE is a small
# annoyance; a read-only agent that silently permits writes is the failure this file
# exists to prevent. When a guard has to be wrong, it should be wrong in the loud
# direction.


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Unreadable input must not break normal work. Note the trade-off: this is a
        # fail-open path. It is acceptable only because a malformed payload means the
        # hook was not invoked with a real tool call.
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        sys.exit(0)

    hit = WRITE_SQL.search(command)
    if hit:
        print(
            "Blocked: this agent is read-only. Found the statement "
            f"'{hit.group(0).upper()}'. Read-only agents may run SELECT only; a write "
            "belongs in the human-approved step of the pipeline.",
            file=sys.stderr,
        )
        sys.exit(2)

    if WRITE_SHELL.search(command):
        print(
            "Blocked: this agent is read-only, and this command redirects output into "
            "a file. Report findings in your response instead of writing them.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
