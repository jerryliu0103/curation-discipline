# metrics branch

Data only. No code here, and nothing on this branch is part of the plugin.

GitHub keeps repository traffic for **14 days** and then deletes it — silently, with
no warning and no way to recover it. The `traffic snapshot` workflow on `main` copies
that data here once a day so it survives.

| File | What it holds |
|---|---|
| `metrics/traffic.csv` | One row per day: views, unique visitors, clones, unique cloners. |
| `metrics/repo.csv` | One row per day: stars, forks, watchers, open issues. |
| `metrics/referrers.csv` | One block per snapshot: where visitors came from. This is a rolling 14-day rollup rather than a daily series, so rows are appended with the date they were taken. |

## Reading it

**Clones are the install signal.** `claude plugin marketplace add` clones the
repository, so `clones_uniques` is the closest thing GitHub gives to a download count
— there is no download counter for a repo, only for release assets.

Rows are keyed by date and rewritten on each run rather than appended. Two
consequences: a missed run loses nothing as long as the gap is under 14 days, and
today's partial count is corrected by tomorrow's run.

## If the workflow fails

It is supposed to. The traffic endpoints require push access, which the default
`GITHUB_TOKEN` does not have — it returns 403. The snapshot script exits non-zero
rather than recording zeros, because a job nobody watches that writes plausible wrong
numbers is worse than one that stops.

Fix: set the `TRAFFIC_TOKEN` secret to a token with `repo` scope (classic) or
`Administration: read` (fine-grained).
