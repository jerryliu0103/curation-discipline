# Ten data-pipeline failures that report success

Most writing about bugs is about crashes. This is about the other category: the run
finishes, the exit code is zero, the log looks normal, and the data is wrong.

These are worse than crashes in every way. A crash tells you where and when. A join that
matched nothing tells you nothing at all, and by the time you notice, the bad rows are
indistinguishable from the good ones and you have built things on top of them.

Everything below actually happened on one curated dataset — a few thousand entries with
per-source attribution, built over several months by one person with an LLM agent doing
most of the collection. I have kept what each one cost and what catches it now.

An agent in the loop sharpens all of this in three specific ways, which is worth stating
before the list:

- **It produces plausible output on missing input.** Ask a database for a row that does not
  exist and you get zero rows. Ask an agent and you may get a confident, well-formed,
  entirely invented answer that then sits in your dataset looking like every other row.
- **It re-words rather than repeats.** Submit the same source twice and a deterministic
  importer produces byte-identical text you can hash. An agent produces different words
  every time, so every text-similarity approach to deduplication fails — not occasionally,
  structurally.
- **It follows instructions well enough that you stop checking.** An agent that has followed
  a rule correctly forty times has trained you not to verify the forty-first, and nothing
  about the forty-first looks different.

---

## 1. A join that matches nothing raises nothing

You import a batch keyed on a display name. Some rows already exist under a *different*
display name but the same underlying key. Every statement runs. Every
`INSERT ... SELECT ... JOIN` that failed to match simply inserts fewer rows.

What it looked like: the same real thing existed as "root celery" and as "celeriac",
identical underlying key. The new insert hit the unique constraint — that part was loud.
But the *dependent* statements that joined on the display name matched nothing, wrote
nothing, and reported nothing. Category memberships and cross-references were simply
absent.

It was found by comparing member counts per category during a dry run. Not by an error.

**The check:** after any batch, compare counts against what you expected. "No errors" is
not a result. `n rows affected` is a result, and you should have predicted it before you
ran it.

## 2. A failed `BEGIN` turns a dry run into a real write

A generated SQL file was supposed to open a transaction, apply 22 statements, and roll
back. A backslash was lost while the file passed through a chain of shell and script
transformations, turning the abort-on-error directive into a bare word with no semicolon.
The parser joined it to the following `BEGIN;` into one malformed statement.

In order:

1. abort-on-error was never set, so errors did not stop the run
2. there was no transaction, so all 22 statements **autocommitted one at a time**
3. the closing `ROLLBACK` had nothing to roll back

The only warning was one line saying there was no transaction in progress, buried among
normal-looking verification output at the end.

That particular run happened to be harmless — the content had already been approved. But
the process was out of control: had a constraint fired mid-batch, half the batch would have
been committed while the operator believed nothing had been written.

**The checks:** set abort-on-error on the command line, not with a directive inside the
file — escaping gets mangled in transit and a mangled directive is silent. Then go and
query the store afterwards to confirm nothing was written. And treat "no transaction in
progress" as an error, not a warning.

## 3. `ROLLBACK` printing does not mean anything rolled back

Corollary to the above, stated separately because it is the specific thing people believe.
The word prints whether or not there was a transaction. It is output, not evidence.

## 4. A missing filter fans rows out, and nothing complains

A store moved from one-row-per-entity to multiple-rows-per-entity so several sources could
coexist. Sync scripts doing `LEFT JOIN` expecting one row now got several. Row count went
from 528 to 550.

Nothing errored. The downstream system dutifully created duplicate pages. The number is
small enough to pass a glance and large enough to matter.

The store had a partial unique index guaranteeing at most one primary row per entity —
which is a real guarantee, and completely irrelevant, because it does not stop a query that
forgot to filter on it.

**The check:** after any schema change from one-to-one to one-to-many, grep every query
that joins the changed table and compare row counts before and after. A constraint protects
the data; it does not protect the queries.

## 5. Your guard can die of an encoding error and take the guard rail with it

A `PreToolUse` hook was written to block dangerous commands. On a console whose codepage
was not UTF-8, printing a non-ASCII character in the rejection message threw. The hook
exited non-zero **with no decision output** — so the tool call went through.

The defence had failed open, and it looked exactly like a defence that was working.

It was found only by piping crafted inputs through the hook by hand and checking the
output: three commands that should have been blocked were not.

**The checks:** force UTF-8 output explicitly in anything that prints and can be non-ASCII.
Test the guard by feeding it what it is supposed to block and asserting that it blocked.
And know your platform's failure mode — a guard that errors may fail open or closed, and
"fails open" is the dangerous one.

## 6. A tool that was never merged is a tool that does not exist

A resolver script was written specifically to stop a class of duplicate-entry bug. It sat
on an unmerged branch for three weeks. During those three weeks the rule that said "always
use the resolver" was, in practice, not a rule — nothing used it.

Worse: when it was finally merged, it no longer worked. The schema had moved on underneath
it and it referenced a column that had been removed. It would have crashed on first use.

**The checks:** a rule that names a tool must name a tool that is on the main branch. When
a branch has been open a while, ask not only "does it merge" but "does it still match the
schema". If you write a guard, land it — an unmerged guard has all of the cost and none of
the benefit.

## 7. A one-way sync leaves orphans forever

Delete or re-key an entity and a one-way sync will never remove its mirror. There is no
error, because from the sync's point of view nothing is wrong: it publishes what exists,
and it publishes it correctly.

**The check:** a periodic two-way reconciliation whose only job is to list things present
in the mirror but absent from the store, exiting non-zero when that list is non-empty.

## 8. Syncs keyed on a parent timestamp miss child-only changes

If your sync selects work by `parent.updated_at`, a batch that only wrote child rows
changes nothing the sync can see. The sync runs, reports success, publishes nothing, and
the mirror is quietly one version behind.

**The check:** after any batch that touches only child tables, touch the parents, or run an
explicit staleness audit.

## 9. An unknown flag can be ignored instead of rejected

`--dry-run` passed to a script that does not implement it means the script does the real
thing while the operator believes they are testing.

**The check:** every script asserts its known flags at startup and exits on anything
unrecognised. Five lines, one whole category prevented.

## 10. An automation can quietly shred your audit trail

An idle-timeout hook that commits the working tree will, mid-task, sweep half-finished work
into a commit with a generic message. Nothing is lost — but the careful commit message you
write later describes changes that are now sitting in an earlier commit that explains
nothing.

Not a data-safety problem, an audit problem, and specifically a problem for projects that
are otherwise careful about provenance. Later, "where did this rule come from" leads to a
commit that says nothing.

**The check:** commit deliberately before you stop; raise the automation's threshold so it
fires only when you have genuinely left.

---

## The shape they share

In every one of these:

> **The system did exactly what it was told, and what it was told was wrong in a way that
> produced no output.**

That gives you the general defence, which is worth more than any individual entry:

1. **Predict the number before you run it,** then compare. "No errors" is not a result.
2. **Verify state, not output.** Query the store. Do not trust the log — the log is produced
   by the thing you are checking.
3. **Test your guards adversarially.** Feed them what they should block and assert they
   blocked it. Untested guards fail open.
4. **After a schema change, grep the queries.** Constraints protect data, not queries.
5. **Anything silent gets an explicit audit.** One-way syncs, joins on display names, flags,
   encodings — if it cannot report its own failure, write something that asks it.

## A postscript that makes the point better than the list does

While packaging these lessons into something shareable, I wrote a 13-case adversarial test
for the two guards that ship with it. It caught a real bug on its first run.

The guard rejects non-read-only SQL. To avoid false positives, it stripped quoted string
literals before matching — so that `WHERE note LIKE '%DELETE%'` would not read as a write.
But SQL reaches `psql` *inside* quotes: `psql -c "INSERT INTO ..."`. Stripping quoted
regions stripped the statement itself. Four write commands were allowed through while the
guard reported success.

It was live for exactly one test run. The fix was to match the raw command and accept the
occasional false positive instead — when a guard has to be wrong, it should be wrong in the
loud direction.

I had just finished writing the entry about guards that fail open while looking like they
work. That is how this category gets you.

---

*The pipeline discipline these came out of — a staging gate agents cannot write past,
read-only enforced by hook rather than by prompt, provenance-coordinate deduplication, and
this catalogue in full — is packaged as a Claude Code plugin at
[github.com/jerryliu0103/curation-discipline](https://github.com/jerryliu0103/curation-discipline).
MIT.*
