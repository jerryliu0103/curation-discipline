---
name: provenance-and-dedup
description: How to record where curated data came from and how to detect that a source was already imported — provenance coordinates instead of text comparison, bidirectional reconciliation of what an agent extracted, and the deliberate-discard list that makes an agent's judgment reviewable. Use when the same source may be submitted twice, when an agent's output must be checked for omissions, when deciding what provenance fields a schema needs, or when a curated dataset has developed duplicates.
---

# Provenance and deduplication

Two problems that look like one:

- **Did I already import this?** — answered by provenance coordinates
- **Did the agent drop something?** — answered by bidirectional reconciliation

## Part 1: comparing text does not detect re-imports

When the same source is submitted twice — the same page photographed again, the same
URL researched a second time, the same interview re-processed — **the text will differ
every time**. An LLM re-wording the same passage produces different words. Similarity
scoring is a losing game: set the threshold high and you miss re-imports, set it low
and you block legitimately distinct records.

**Compare where it came from, not what it says.**

### Provenance coordinates

Every table that can receive the same source twice needs a coordinate that identifies
the source location, and a unique constraint on it:

| Content type | Coordinate |
|---|---|
| Excerpt from a document | `(document_id, location)` |
| Reference from a document to an entity | `(document_id, entity_type, entity_id, location)` |
| Description of an entity from a source | `(entity_type, entity_id, source)` |
| A worked example | `(entity_type, entity_id, title)` |
| A relation between two entities | the **normalized, undirected** pair |

Three things this table teaches that are easy to get wrong:

**Symmetric relations must be normalized.** If `(a, b)` and `(b, a)` mean the same
thing, sort the pair before storing it, or the same relation gets written twice. And
when you *query* for an existing relation, **check both directions** — the constraint
normalizes, your `WHERE` clause does not.

**Some coordinates deliberately include a discriminator.** A recipe that uses salt in
the marinade and again in the sauce is not a duplicate. If the coordinate includes the
step, both rows are legitimate. Getting this wrong in the strict direction is worse
than in the loose direction: you will silently refuse correct data.

**Sometimes the right key is content, not source.** One project keyed descriptions on
`(entity, source)` and it was too strict — the same source legitimately produces a
main description and a supplementary one, and revisiting a source a year later
produces a legitimately different row. Switching the constraint to "block only byte-
identical content" fixed it, but note the trade: **the database no longer tells you
whether a source was already imported.** You must check that yourself.

### The constraint is the second line, never the first

**Always check before you write, even when a constraint exists.**

When you hit a constraint you get `duplicate key` and nothing more. You do not learn
what the existing row says, whether it is better or worse than yours, or whether the
right move is to skip, update, or add a parallel row. All the constraint bought you
was that the damage did not happen.

So the flow is:

1. Look up the coordinate.
2. If it exists, **stop**. Put the existing row and the incoming row side by side.
3. A **human** picks: skip / update the existing row / add as an independent source.

All three outcomes are legitimate in different situations, which is exactly why the
agent does not get to choose.

### Record two coordinates, not one

- `source` — who said it
- `retrieved_at` — when you got it

The second is not bookkeeping. Once you accept that multiple sources coexist, "which
of these is current" becomes a real question, and without a date it is unanswerable.
The same applies to measurements: record **under what conditions** the measurement was
taken. Two sources that appear to contradict each other may have measured different
things, and "resolving" that contradiction destroys real information.

## Part 2: bidirectional reconciliation

An agent processing a batch can lose an item in two different places, and only one of
them is easy to catch.

**Direction A — did everything get looked at?** Every input item appears in the
agent's routing table. This is the check people write.

**Direction B — did everything that was found get written down?** For every tag in the
routing table, is there a corresponding entry in the output?

**Direction B is the one that catches real losses.** A passage was tagged as
containing three kinds of content; two were produced and the third was not. The
routing table was complete. The output was internally consistent. Nothing was missing
from any list you would think to check. The loss was found only when a human asked
directly what had happened to that specific passage.

**Recognized during analysis, dropped while writing the output** — this is harder to
catch than never having seen the item at all, because every partial check passes.

### How to implement it

Require the agent to emit a routing table alongside its output:

```json
{
  "routing_table": [
    { "item": "p.58 / speaker X", "categories": ["1", "2", "4"] },
    { "item": "p.61 / speaker Y", "categories": ["5"] }
  ]
}
```

Then, before delivery, for **every** `(item, category)` pair, find the corresponding
entry in the output arrays by item identity. Anything not found is a miss.

Do the whole batch first, then reconcile, then deliver. Reconciling per item as you go
gives you no way to notice that the totals do not add up.

**Counts that do not match are the only mechanical way to detect an omission.** If your
pipeline produces no number that can fail to match, it cannot detect this class of
error at all.

## Part 3: the deliberate-discard list

Require every extraction agent to output what it **threw away**, and why.

```json
"deliberately_discarded": [
  { "content": "<short summary>", "location": "<where>", "reason": "<why>" }
]
```

This feels like busywork until you realize what it is for: **it is the only place a
reviewer can catch a judgment error.**

If an agent misfiles a transferable method as personal preference, the output looks
perfect. The principle is simply not there, and nothing indicates it ever was. The
discard list is the sole record of a decision that would otherwise be invisible.

Two rules that make it work:

- **An empty discard list is a red flag, not a clean bill of health.** A batch from
  which nothing was discarded almost certainly means the agent did not consider
  discarding anything.
- **Discards carry a location.** "Some autobiographical material" is not reviewable.
  "p.61, speaker Y, career history" is.

## Part 4: entity resolution before creating anything new

The most common way a curated dataset splits in half: the same real thing arriving
under two names.

- **Resolve through the full alias chain** before creating an entry: primary names,
  aliases, and — if your model allows it — aliases pointing at other entity types
  entirely, not just the main one.
- **When the primary name misses, try the secondary axis.** Translated name,
  scientific name, canonical identifier. An entry that exists under a different
  display name but the same underlying key will collide — sometimes loudly at a
  unique constraint, and sometimes silently in a join. See
  `silent-failure-hunting` entry 1.
- **An unresolved name is never auto-created.** Write it to
  `data/staging/unresolved.json` and let a human decide. This rule exists because a
  resolver that auto-created on miss produced eight cross-table duplicates of very
  ordinary things, each of which then had to be found and merged by hand.
- **Route every ad-hoc import through the same resolver.** The one-off import done in
  conversation, with no script, is exactly the one that will create the duplicates.

## Related

- `curation-pipeline` — the staging gate this discipline runs inside
- `silent-failure-hunting` — why the checks here are all about counts and coordinates
