# Why this exists

## The shape of the problem

Most writing about AI-assisted data work is about getting the agent to produce good
output. This plugin is about the other half: **knowing whether it did.**

Those are not the same problem, and the second one is harder, because a data pipeline
has a property that most software does not. When ordinary code is wrong, it usually
crashes. When a data pipeline is wrong, it usually **finishes**, reports success, and
hands you a dataset that is subtly incomplete — and the incomplete rows look exactly
like the complete ones.

An LLM agent makes this sharper in three specific ways:

**It produces plausible output on missing input.** Ask a database for a row that does
not exist and you get zero rows. Ask an agent and you may get a confident, well-formed,
entirely invented answer that sits in your dataset looking like every other row.

**It re-words rather than repeats.** Submit the same source twice and a deterministic
importer produces byte-identical text you can detect with a hash. An agent produces
different words every time. Every text-similarity approach to deduplication fails
here — not occasionally, but structurally.

**It follows instructions well enough that you stop checking.** This is the dangerous
one. An agent that has followed a rule correctly forty times has trained you not to
verify the forty-first, and nothing about the forty-first will look different.

## Where the material came from

A Traditional Chinese ingredient and flavour-pairing database. One person, Claude Code,
several months, a few thousand curated entries with per-source attribution. A Postgres
canonical store on a home server, a read-only public view with three layers of access
control, and a one-way mirror into a notes app so the data could be browsed by a human.

The domain does not matter and has been removed. What survives is the machinery, and
more importantly the incidents.

## Why the incidents are the valuable part

The pipeline shape — collect, validate, approve, write — is not a discovery. Anyone
who thinks about the problem for ten minutes arrives at it. You could have written it
yourself and probably have.

What you cannot derive from first principles is the list of ways it silently fails.
Those come from running it for months and finding out. A sample:

- A dry run that **was not a dry run**, because a backslash was lost while a SQL file
  passed through a chain of tools, and the transaction never opened. Twenty-two
  statements autocommitted one at a time. The only warning was one line saying there
  was no transaction in progress, buried in normal-looking output at the end.
- A `ROLLBACK` that printed and rolled back nothing. The word always prints.
- A schema change from one row per entity to several so that multiple sources could
  coexist. Every downstream query that did `LEFT JOIN` expecting one row started
  getting several. 528 rows became 550. Nothing errored; a mirror quietly grew
  duplicates.
- A `PreToolUse` guard that died of a `UnicodeEncodeError` on a non-UTF-8 console,
  exited non-zero with no decision output, and stopped blocking anything — while
  looking exactly like a guard that was working.
- A resolver written specifically to prevent a class of duplicate, which sat on an
  unmerged branch for three weeks. The rule that named it was, during those weeks, not
  a rule. When it was finally merged it referenced a column that no longer existed.
- An extraction agent that recognized a passage contained three kinds of content,
  produced two of them, and dropped the third. Every list was internally consistent.
  It was found when a human asked what had happened to one specific passage.

Full catalogue with the fix for each: the `silent-failure-hunting` skill.

## The three ideas worth taking even if you install nothing

### 1. Enforce structurally, not by asking

A written rule that agents must never touch a particular datastore was ignored for a
month — an audit found all five agent files violating it. Nobody was careless.
**Nothing failed when the rule was broken**, so there was no feedback of any kind.

A rule with no failure mode is a preference. If you want it obeyed, attach it to
something that stops.

And when you build the guard: **test it adversarially.** Feed it what it is supposed to
block and assert that it blocked. The `test_hooks.py` in this plugin caught a real bug
on its first run — quoted-string stripping was removing the SQL itself, so the guard
allowed every write while reporting success. That bug was live for one test run, which
is the entire argument for shipping the test.

### 2. Compare provenance, not text

You cannot detect a re-import by comparing text, because the text differs every time.
Record where something came from — document and location, entity and source — and
compare that. This one change removes an entire category of duplicate.

Two coordinates, not one: **who said it**, and **when you got it**. Once you accept
that several sources coexist rather than overwrite, "which of these is current" becomes
a real question and is unanswerable without a date.

### 3. Require the discard list

Make every extraction agent report what it **threw away**, and why, and where.

This feels like busywork until you see what it is for. If an agent misclassifies
something valuable as noise, the output looks perfect — the missing item is simply not
there, and nothing indicates it ever was. The discard list is the only record of a
decision that would otherwise be invisible.

**An empty discard list is a red flag, not a clean result.** A batch from which nothing
was discarded almost certainly means the agent never considered discarding anything.

## What is deliberately not here

**Anything domain-specific.** The taxonomy decisions — which category a borderline
entity belongs in, how to handle a name that means two different things in two
different sources — do not generalize. They were the expensive part of the original
project and they are worth nothing to you, because your domain's hard cases are
different.

**A rights-management layer.** `principle-extractor` covers separating method from
expression, which is a method problem. Building an auditable pipeline for material you
do not own — tiering content by what may be published, storing paraphrase and original
as a pair, enforcing access at the database, application and API layers — is a
different and much larger design problem, and it is not solved by an agent definition.
Do not read this plugin as making your corpus safe to publish.

**Infrastructure.** Backup schedules, sync scripts, scheduled jobs. Those were the bulk
of the original project's automation and none of it transfers — it is all paths and
machine names.

## Contributing

The catalogue grows from reports. If you hit a failure that produced no error message,
open an issue with what happened, what made it silent, and what catches it now. That
third part is what makes it worth adding.
