#!/usr/bin/env python3
"""Snapshot GitHub traffic into CSV files that outlive GitHub's 14-day window.

WHY THIS EXISTS

    GitHub keeps repository traffic (clones, views, referrers) for 14 DAYS ONLY.
    After that it is gone permanently, with no warning and no way to recover it.
    A repo can be quietly losing its entire early-adoption record while every part
    of the system reports success -- which is precisely the class of failure this
    repository's own skills are about.

    So: snapshot daily, and keep the snapshots.

WHY UPSERT AND NOT APPEND

    Each endpoint returns the last 14 days as daily rows, not a running total.
    Appending would double-count every day 14 times over. Instead each run merges
    the returned rows into the CSV keyed by date, overwriting what is there.

    Two things fall out of that for free:
      - a missed run loses nothing, as long as the gap is under 14 days
      - today's partial count is corrected by tomorrow's run, which sees the
        finished figure for that date

WHY IT EXITS NON-ZERO ON AN AUTH FAILURE

    The traffic endpoints need push access. A token without it returns 403 -- and
    the tempting thing to do is carry on and record zeros. That would write a
    plausible, well-formed, permanently wrong history. Failing the job instead
    means GitHub emails you, which is the only feedback loop that works for a job
    nobody watches.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
REPO = os.environ.get("SNAPSHOT_REPO") or os.environ.get("GITHUB_REPOSITORY") or ""
TOKEN = os.environ.get("TRAFFIC_TOKEN") or os.environ.get("GH_TOKEN") or ""
OUT = Path(os.environ.get("SNAPSHOT_DIR", "metrics"))

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def die(message: str) -> None:
    # ::error:: makes it show up on the workflow summary page, not just in the log.
    print(f"::error::{message}", file=sys.stderr)
    sys.exit(1)


def get(path: str):
    # rstrip("/") matters: get("") must hit /repos/owner/name, not /repos/owner/name/
    # -- the trailing slash 404s. Caught on the first local run.
    url = f"{API}/repos/{REPO}/{path}".rstrip("/")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "traffic-snapshot",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            die(
                f"{path} returned {error.code}. The traffic endpoints require push "
                "access, which the default GITHUB_TOKEN does not have. Set the "
                "TRAFFIC_TOKEN secret to a token with repo scope (classic) or "
                "Administration: read (fine-grained). Refusing to record zeros."
            )
        if error.code == 404:
            die(f"{url} returned 404. Check SNAPSHOT_REPO ({REPO!r}).")
        die(f"{url} returned HTTP {error.code}: {error.reason}")
    except Exception as error:  # network, DNS, timeout
        die(f"{url} failed: {error}")


def upsert(filename: str, fieldnames: list[str], rows: list[dict], key: str) -> int:
    """Merge rows into a CSV keyed by `key`, overwriting matching keys."""
    path = OUT / filename
    existing: dict[str, dict] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                existing[row[key]] = row

    changed = 0
    for row in rows:
        stringified = {k: str(v) for k, v in row.items()}
        if existing.get(row[key]) != stringified:
            changed += 1
        existing[row[key]] = stringified

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for k in sorted(existing):
            writer.writerow(existing[k])
    return changed


def append(filename: str, fieldnames: list[str], rows: list[dict]) -> None:
    """Append rows. Used for referrers, which are a rolling window, not a series."""
    path = OUT / filename
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not REPO:
        die("SNAPSHOT_REPO / GITHUB_REPOSITORY is empty.")
    if not TOKEN:
        die(
            "No token. Set the TRAFFIC_TOKEN secret (Settings -> Secrets and "
            "variables -> Actions). Refusing to record zeros."
        )

    OUT.mkdir(parents=True, exist_ok=True)

    clones = get("traffic/clones")
    views = get("traffic/views")
    referrers = get("traffic/popular/referrers")
    repo = get("")

    # clones and views are two independent 14-day series; merge them by date.
    daily: dict[str, dict] = {}
    for item in views.get("views", []):
        date = item["timestamp"][:10]
        daily.setdefault(date, {"date": date, "views": 0, "views_uniques": 0,
                                "clones": 0, "clones_uniques": 0})
        daily[date]["views"] = item["count"]
        daily[date]["views_uniques"] = item["uniques"]
    for item in clones.get("clones", []):
        date = item["timestamp"][:10]
        daily.setdefault(date, {"date": date, "views": 0, "views_uniques": 0,
                                "clones": 0, "clones_uniques": 0})
        daily[date]["clones"] = item["count"]
        daily[date]["clones_uniques"] = item["uniques"]

    changed = upsert(
        "traffic.csv",
        ["date", "views", "views_uniques", "clones", "clones_uniques"],
        list(daily.values()),
        key="date",
    )

    upsert(
        "repo.csv",
        ["date", "stars", "forks", "watchers", "open_issues"],
        [{
            "date": TODAY,
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "watchers": repo.get("subscribers_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
        }],
        key="date",
    )

    if referrers:
        append(
            "referrers.csv",
            ["snapshot_date", "referrer", "count", "uniques"],
            [{
                "snapshot_date": TODAY,
                "referrer": r.get("referrer", ""),
                "count": r.get("count", 0),
                "uniques": r.get("uniques", 0),
            } for r in referrers],
        )

    print(
        f"{TODAY}  clones14d={clones.get('count', 0)} "
        f"(uniq {clones.get('uniques', 0)})  "
        f"views14d={views.get('count', 0)} (uniq {views.get('uniques', 0)})  "
        f"stars={repo.get('stargazers_count', 0)}  "
        f"referrers={len(referrers)}  rows_changed={changed}"
    )


if __name__ == "__main__":
    main()
