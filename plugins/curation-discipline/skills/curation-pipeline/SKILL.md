---
name: curation-pipeline
description: The staging-gate discipline for AI-assisted data curation — agents collect into staging, a read-only validator checks, a human approves, and only then does anything reach the canonical store. Use when building or reviewing a pipeline where an LLM agent contributes data to a database, knowledge base, or curated dataset, when deciding which agent may write where, or when a curated dataset has developed duplicates, unattributed rows, or silent gaps.
---

# The staging gate

One rule holds the whole thing up:

> **No agent writes to the canonical store. Agents write to staging. A human moves
> staging into the store.**

Everything else in this skill exists because of that rule, or to stop people from
quietly working around it.

## Why not just let the agent write?

Because you cannot review what has already happened. An agent that writes directly
gives you two bad options: trust it, or audit the database afterwards — and auditing
afterwards is far harder than reviewing a batch, because by then the bad row looks
exactly like the good rows.

The staging file is the review artifact. It is the difference between "the agent added
40 rows" and "here are 40 rows, 3 need your attention, and here is why".

## The four stages

```
  collect            check              approve           write
  ────────           ─────              ───────           ─────
  curator     →     validator     →     human      →     human
  (writes           (read-only,         (reads the       (runs the
   staging)          hook-enforced)      diff)            SQL)
```

1. **Collect** — `curator` writes `data/staging/<batch>.json`. Never the store.
2. **Check** — `validator` reads staging, queries the store read-only, reports
   passed / needs-review / rejected. Never writes anything, including staging.
3. **Approve** — a human reads the report. Rejections go back to step 1.
4. **Write** — a human runs the write. This is the only step with write access.

Steps 3 and 4 being human is the point. If you automate them you have rebuilt the
thing this skill exists to prevent, and the staging file has become decoration.

## Enforce it structurally, not by asking

**A rule that produces no error will be broken, and you will not find out.**

Concretely: a project ran for a month with a written rule that agents must never touch
a particular datastore. An audit found all five agent definition files doing exactly
that. Nobody was being careless. The rule simply had no teeth — **nothing failed when
it was violated**, so there was no feedback of any kind.

Three layers, in increasing order of reliability:

| Layer | Mechanism | Strength |
|---|---|---|
| Prompt | "do not write to the store" in the agent file | Weakest — advisory |
| Toolset | `disallowedTools: Write, Edit` in frontmatter | Removes the capability |
| Hook | `PreToolUse` rejects the command | Catches what leaks through Bash |

Use all three. The toolset layer does not cover `Bash`, and `Bash` is how a database
gets written to. That is what the hook is for.

This plugin ships `hooks/readonly-guard.py` (rejects non-read-only SQL) and
`hooks/canonical-store-guard.py` (asks before commands that touch the wrong store).
Wire them up with `templates/settings.json.example`.

**Prefer `ask` over `deny` for paths that have legitimate uses.** A hard block on a
command people genuinely need gets routed around, and then you have no visibility at
all. What you want is "you cannot walk into this by accident", not "you cannot get
here".

## Give each agent the narrowest role that works

| Agent | Reads | Writes | Enforced by |
|---|---|---|---|
| `curator` | web, files | staging only | no DB tool at all |
| `validator` | staging, store | nothing | `disallowedTools` + hook |
| `reader` | store | nothing | `disallowedTools` + hook |
| `mirror-writer` | store | mirror only | one-way by design |
| `principle-extractor` | files | staging only | no network, no DB |

The narrowness is not bureaucracy. When something goes wrong, a narrow role means the
list of things that could have caused it is short.

## Dry-run before a batch write

Run the batch against a disposable copy of the store inside a transaction that rolls
back. It catches syntax errors, constraint violations, and — most valuable — joins
that match nothing.

**Two things about dry runs that are not obvious:**

1. **A failed `BEGIN` silently downgrades your dry run into a real write.** If the
   transaction never started, every statement autocommits one at a time, and the
   `ROLLBACK` at the end has nothing to roll back. Set the abort-on-error flag **on
   the command line**, not inside the script file — escaping gets mangled as text
   passes through shells and generators, and a mangled directive does not error, it
   just does nothing.
2. **`ROLLBACK` printing in the output does not mean anything was rolled back.** The
   word always prints. **Go and query the store afterwards to confirm nothing was
   written.** If you see a warning that there was no transaction in progress, that is
   not noise — that is your dry run telling you it was a real write.

**Verify a dry run by comparing counts, not by the absence of errors.** A join that
matched nothing does not raise anything. See the `silent-failure-hunting` skill.

## Accumulation, not completion

A curated store is never "done". Two consequences that surprise people:

- **"This entry already has data" is not a reason to skip it.** A second source does
  not overwrite the first; it becomes another row. Sources accumulate.
- **Therefore distinguish two kinds of field**, because they behave differently:

  | Kind | Example | Rule |
  |---|---|---|
  | Single-valued attribute | category, region, type | Sources compete. Fill empties, only a better source overwrites. |
  | Descriptive content | description, notes | Multiple sources coexist as separate rows. Never "full". |
  | Measurements | ratings, scores | Coexist **with the measurement conditions recorded**. |

  That last row is the one people get wrong. Two sources disagreeing about a
  measurement may not disagree at all — they may have measured under different
  conditions. Record what the conditions were, or you will "resolve" a contradiction
  that was never there.

## What belongs in your project's CLAUDE.md

Not this skill — link to it. Put in CLAUDE.md only what causes damage if unread:

- which store is canonical, and what everything else is
- where staging lives, and that nothing else may be written
- the specific commands for reaching the store, and which ones are traps
- the incidents that have already happened in **this** project

`templates/CLAUDE.md.template` has the skeleton.

## Related

- `silent-failure-hunting` — the failures that produce no error message
- `provenance-and-dedup` — source coordinates, bidirectional reconciliation, and the
  deliberate-discard list
