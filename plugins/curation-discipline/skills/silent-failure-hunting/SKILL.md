---
name: silent-failure-hunting
description: A catalogue of data-pipeline failures that produce no error message — joins that match nothing, dry runs that were real writes, fan-out that duplicates rows, guards that die on an encoding error, and tools that were written but never merged. Use when a pipeline reports success but the data is wrong, when reviewing an import or sync script, when deciding what to verify after a batch write, or when designing a check that has to catch something the runtime will not.
---

# Failures that succeed

Most pipeline advice is about handling errors. This is about the other category: the
run finishes, the exit code is zero, the log looks normal, and the data is wrong.

These are worse than crashes in every way. A crash tells you where it happened and
when. A silent failure tells you nothing, and by the time you notice, the bad data is
indistinguishable from the good data and you have built things on top of it.

Every entry below is something that actually happened on a real curated dataset, with
what it cost and how to catch it.

## The catalogue

### 1. A join that matches nothing does not raise anything

You import a batch keyed on a display name. Some rows exist in the store under a
different display name but the same underlying key. Every statement runs. Every
`INSERT ... SELECT ... JOIN` that failed to match simply inserts fewer rows.

**What it looked like**: two entries for the same real thing, one written as "root
celery" and one as "celeriac", identical underlying key. The new insert was blocked by
the unique constraint — that part was loud. But the *dependent* statements that joined
on the display name matched nothing, wrote nothing, and reported nothing. Category
memberships and cross-references were simply absent.

**How it was found**: by comparing member counts per category during a dry run. Not by
an error.

**The check**: after any batch, **compare counts against what you expected**. "No
errors" is not a result. `n rows affected` is a result, and you should have predicted
it before you ran it.

### 2. A failed `BEGIN` turns a dry run into a real write

A generated SQL file was supposed to open a transaction, apply 22 statements, and roll
back. A backslash was lost while the file passed through a chain of shell and script
transformations, turning the abort-on-error directive into a bare word with no
semicolon. The parser joined it to the following `BEGIN;` into one malformed
statement.

Consequences, in order:

1. abort-on-error was never set, so errors did not stop the run
2. there was no transaction, so all 22 statements **autocommitted one at a time**
3. the closing `ROLLBACK` had nothing to roll back

**The only warning** was a line saying there was no transaction in progress, buried
among normal-looking verification output at the end.

That run happened to be harmless — the content had already been approved. **But the
process was out of control**: had a constraint fired mid-batch, half the batch would
have been committed while the operator believed nothing had been written.

**Three defenses:**

- Set abort-on-error **on the command line**, not with a directive inside the file.
  Escaping gets mangled in transit, and a mangled directive is silent.
- **Query the store afterwards to confirm nothing was written.** Do not trust the
  output.
- Treat "no transaction in progress" as an error, not a warning. It is the pipeline
  telling you this was not a dry run.

### 3. `ROLLBACK` printing does not mean anything rolled back

Corollary to the above, stated separately because it is the specific thing people
believe. The word prints whether or not there was a transaction. It is output, not
evidence.

### 4. A missing filter fans rows out, and nothing complains

A store moved from one-row-per-entity to multiple-rows-per-entity so that several
sources could coexist. Sync scripts that did `LEFT JOIN` expecting one row now got
several. Row count went from 528 to 550.

**Nothing errored.** The downstream system dutifully created duplicate pages. The
number is small enough to pass a glance and large enough to matter.

The store had a partial unique index guaranteeing at most one primary row per
entity — which is a real guarantee, and completely irrelevant, because **it does not
stop a query that forgot to filter on it**.

**The check**: after any schema change from one-to-one to one-to-many, grep every
query that joins the changed table. Compare row counts before and after. A constraint
protects the data; it does not protect the queries.

### 5. Your guard can die of an encoding error and take the guard rail with it

A `PreToolUse` hook was written to block dangerous commands. On a console whose
codepage was not UTF-8, printing a non-ASCII character in the rejection message threw.
The hook exited non-zero **with no decision output** — so the tool call went through.

**The defense had failed open, and it looked exactly like a defense that was working.**

Found only by piping crafted inputs through the hook directly and checking the output:
three commands that should have been blocked were not.

**The checks:**

- Force UTF-8 output explicitly in any hook that prints anything but ASCII.
- **Test the hook by feeding it input directly** and asserting on its output. A hook
  you have not tested is a hook you are guessing about.
- Know your platform's failure mode: a hook that errors may fail open or closed
  depending on the event, and "fails open" is the dangerous one.

### 6. A tool that was never merged is a tool that does not exist

A resolver script was written specifically to stop a class of duplicate-entry bug. It
sat on an unmerged branch for three weeks. During those three weeks the rule that
said "always use the resolver" was, in practice, not a rule — nothing used it.

Worse: when it was finally merged, it no longer worked. The schema had moved on
underneath it, and it referenced a column that had been removed. **It would have
crashed on first use.**

**The checks:**

- A rule that names a tool must name a tool that is on the main branch.
- When a branch has been open a while, the question is not only "does it merge" but
  "does it still match the schema".
- If you write a guard, land it. An unmerged guard has all of the cost of writing it
  and none of the benefit.

### 7. A one-way sync leaves orphans forever

Delete or re-key an entity in the store and a one-way sync will never remove its
mirror. There is no error because from the sync's point of view nothing is wrong: it
publishes what exists, and it publishes it correctly.

**The check**: a periodic two-way reconciliation whose only job is to list things
present in the mirror but absent from the store. Exit non-zero when the list is
non-empty.

### 8. Syncs keyed on a parent timestamp miss child-only changes

If your sync selects work by `parent.updated_at`, a batch that only wrote child rows
changes nothing the sync can see. The sync runs, reports success, publishes nothing,
and the mirror is quietly one version behind.

**The check**: after any batch that touches only child tables, touch the parents, or
run an explicit staleness audit.

### 9. An unknown flag can be ignored instead of rejected

`--dry-run` passed to a script that does not implement it means the script does the
real thing while the operator believes they are testing.

**The check**: every script asserts its known flags at startup and exits on anything
unrecognized. This is five lines and it prevents a whole category.

### 10. An automation can quietly shred your audit trail

An idle-timeout hook that commits the working tree will, mid-task, sweep up
half-finished work into a commit with a generic message. Nothing is lost — but the
careful commit message you write later describes changes that are now sitting in an
earlier commit that explains nothing.

**Not a data-safety problem, an audit problem**, and specifically a problem for
projects that are otherwise careful about provenance. Later, "where did this rule come
from" leads to a commit that says nothing.

**The check**: commit deliberately before you stop for the day; raise the automation's
threshold so it fires only when you have genuinely left.

## The general shape

Look at the pattern across all ten. In every case:

> **The system did exactly what it was told, and what it was told was wrong in a way
> that produced no output.**

That gives you the general defense, which is worth more than any individual entry:

1. **Predict the number before you run it.** Then compare. "No errors" is not a
   result; `n rows` is.
2. **Verify state, not output.** Query the store. Do not trust the log — the log is
   produced by the thing you are checking.
3. **Test your guards adversarially.** Feed them what they are supposed to block and
   assert they blocked it. Untested guards fail open.
4. **After a schema change, grep the queries.** Constraints protect data; they do not
   protect queries that forgot about them.
5. **Anything silent gets an explicit audit.** One-way syncs, joins on display names,
   flags, encodings — if it cannot report its own failure, write something that asks
   it.

## Related

- `curation-pipeline` — the staging gate these checks protect
- `provenance-and-dedup` — the silent failures specific to deduplication
