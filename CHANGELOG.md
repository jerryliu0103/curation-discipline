# Changelog

## 0.1.0 — 2026-09-07

First release.

Extracted from a Traditional Chinese ingredient and flavour-pairing database built by
one person with Claude Code over several months. The domain has been removed; the
incidents have not.

**Agents** — `curator`, `validator`, `reader`, `mirror-writer`, `principle-extractor`.

**Skills** — `curation-pipeline` (the staging gate), `silent-failure-hunting` (ten
failures that produced no error message), `provenance-and-dedup` (source coordinates,
bidirectional reconciliation, the deliberate-discard list).

**Hooks** — `readonly-guard.py`, `canonical-store-guard.py`, and `test_hooks.py` with
13 adversarial cases.

**Templates** — `CLAUDE.md.template`, `settings.json.example`,
`staging-record.schema.json`.

Both an English and a Traditional Chinese edition, as separate plugins in one
marketplace.

### Notes

- `test_hooks.py` caught a real bug in `readonly-guard.py` on its first run:
  quoted-string stripping removed the SQL itself, because `psql -c "INSERT ..."` puts
  the statement inside quotes. Four write commands were allowed while the guard
  reported success. The guard now matches the raw command and over-blocks instead —
  the deliberate false positive is covered by a test case.
- `principle-extractor` ships the extraction method only. The rights-management layer
  that belongs around it — publishability tiering, paired paraphrase storage,
  three-layer access control — is deliberately out of scope and is not solved by an
  agent definition.
