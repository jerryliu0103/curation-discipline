# curation-discipline

**Keep an AI agent from silently corrupting your dataset.**

繁體中文版：[README.zh-TW.md](README.zh-TW.md)

A Claude Code plugin: five agents, three skills, two tested hooks, and a catalogue of
data-pipeline failures that produce no error message.

---

## The problem

You point an agent at a database and ask it to help you build a dataset. It works. The
rows appear. Some months later you discover that the same entity exists twice under two
names, a batch of rows has no attribution, and a sync has been publishing a stale
mirror since a schema change nobody connected to it.

None of that produced an error. That is the actual problem — **not that agents make
mistakes, but that the mistakes they make are the quiet kind.** A crash tells you where
and when. A join that matched nothing tells you nothing at all, and by the time you
notice, the bad rows are indistinguishable from the good ones.

## What this is

One rule, and the machinery that keeps people from working around it:

> **No agent writes to the canonical store. Agents write to staging. A human moves
> staging into the store.**

```
  collect            check              approve           write
  ────────           ─────              ───────           ─────
  curator     →     validator     →     human      →     human
  (writes           (read-only,         (reads the       (runs the
   staging)          hook-enforced)      diff)            SQL)
```

The staging file is the review artifact. It is the difference between "the agent added
40 rows" and "here are 40 rows, 3 need your attention, and here is why".

## Install

```bash
/plugin marketplace add jerryliu0103/curation-discipline
```

```bash
/plugin install curation-discipline@curation-discipline
```

Traditional Chinese edition: `curation-discipline-zh@curation-discipline`. Same
content, same structure — install one, not both.

## What you get

### Agents

| Agent | Job | Can write |
|---|---|---|
| `curator` | Collects and normalizes source material | staging only |
| `validator` | Checks a batch before it reaches the store | **nothing** |
| `reader` | Answers questions from the store | **nothing** |
| `mirror-writer` | Publishes to a human-readable mirror, one-way | mirror only |
| `principle-extractor` | Separates method from preference in interview material | staging only |

### Skills

- **`curation-pipeline`** — the staging gate, the four stages, why enforcement has to
  be structural, and the two non-obvious things about dry runs.
- **`silent-failure-hunting`** — ten real failures that produced no error message, what
  each cost, and what catches it. This is the one worth reading even if you never
  install the plugin.
- **`provenance-and-dedup`** — why comparing text does not detect re-imports, the
  coordinate table that does, bidirectional reconciliation, and the deliberate-discard
  list.

### Hooks

- `readonly-guard.py` — rejects non-read-only commands for agents that must never
  write. `disallowedTools` does not cover `Bash`, and `Bash` is how a database actually
  gets written to.
- `canonical-store-guard.py` — asks before a command reaches a superseded datastore.
  Edit its `PATTERNS` for your own traps.
- `test_hooks.py` — **run it.** Both guards, thirteen adversarial cases, no
  dependencies.

```bash
python hooks/test_hooks.py
```

That test file caught a real bug in `readonly-guard.py` on its first run: quoted-string
stripping was removing the SQL itself, because `psql -c "INSERT ..."` puts the
statement inside quotes. Four commands that should have been blocked were allowed. The
guard looked like it was working. That is exactly the failure mode this plugin is
about, and it happened while writing the plugin.

### Templates

`CLAUDE.md.template`, `settings.json.example`, `staging-record.schema.json`.

## Enforce it structurally, not by asking

**A rule that produces no error will be broken, and you will not find out.**

A project ran for a month with a written rule that agents must never touch a particular
datastore. An audit found all five agent definition files doing exactly that. Nobody was
being careless — nothing failed when the rule was violated, so there was no feedback of
any kind.

| Layer | Mechanism | Strength |
|---|---|---|
| Prompt | "do not write to the store" | Weakest — advisory |
| Toolset | `disallowedTools: Write, Edit` | Removes the capability |
| Hook | `PreToolUse` rejects the command | Catches what leaks through Bash |

Use all three.

## Where this comes from

Everything here was extracted from a real project: a Traditional Chinese ingredient and
flavour-pairing database of a few thousand curated entries, built by one person with
Claude Code over several months, with a Postgres canonical store, a read-only public
view, and a one-way mirror into a notes app.

The domain has been removed; **the incidents have not.** Every entry in
`silent-failure-hunting` is something that actually happened there, with what it cost.
That is the part that is hard to get from a blog post — not the pipeline shape, which is
obvious once stated, but the specific ways it fails while reporting success.

See [docs/why.md](docs/why.md) for the longer version.

## License

MIT. Use it, fork it, strip the parts you disagree with.

If it saves you an afternoon, a note saying which entry did it would be genuinely
useful — the catalogue only grows from reports.
