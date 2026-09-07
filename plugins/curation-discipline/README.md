# curation-discipline

Keep an AI agent from silently corrupting your dataset.

Full documentation: the [repository README](../../README.md) and
[docs/why.md](../../docs/why.md).

## One rule

> **No agent writes to the canonical store. Agents write to staging. A human moves
> staging into the store.**

## Contents

| | |
|---|---|
| **Agents** | `curator`, `validator`, `reader`, `mirror-writer`, `principle-extractor` |
| **Skills** | `curation-pipeline`, `silent-failure-hunting`, `provenance-and-dedup` |
| **Hooks** | `readonly-guard.py`, `canonical-store-guard.py`, `test_hooks.py` |
| **Templates** | `CLAUDE.md.template`, `settings.json.example`, `staging-record.schema.json` |

## After installing

**1. Run the guard tests.**

```bash
python hooks/test_hooks.py
```

**2. Point `canonical-store-guard.py` at your own traps.** As shipped, its `PATTERNS`
match example strings and will fire on nothing in your project. Edit them to name the
commands and variables that reach the wrong datastore *without erroring* — those are
the ones worth guarding.

**3. Copy `templates/CLAUDE.md.template`** into your project and fill in the store,
the staging location, and the traps. Leave the incidents section empty; it fills
itself in.

## Traditional Chinese

Same content in Traditional Chinese: `curation-discipline-zh`. Install one, not both.
