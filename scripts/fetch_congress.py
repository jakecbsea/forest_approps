"""
Tier 1 — fully automated, no-AI data pull.

Pulls a lightweight funding-status signal from the Congress.gov API:
recent Interior/Environment appropriations bills and continuing-resolution
(CR) bills, with their latest action and date. This powers the "funding
status" strip on the dashboard (part of PIR-4/PIR-6 — CR exposure).

Requires a free api.data.gov key: https://api.congress.gov/sign-up/
Read from the CONGRESS_API_KEY environment variable (set as a GitHub
Actions repo secret — never commit the key itself).

Run by .github/workflows/update-data.yml on a monthly schedule.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

API_ROOT = "https://api.congress.gov/v3"

# Keyword filters applied client-side to bill titles, since the v3 API
# doesn't support full-text keyword search on /bill list endpoints.
INTEREST_KEYWORDS = [
    "continuing appropriations",
    "continuing resolution",
    "interior, environment",
    "further consolidated appropriations",
    "wildfire",
    "wildland fire",
]


def current_congress_number() -> int:
    # Congress N covers Jan of an odd year through Dec of the following even
    # year. 119th Congress = 2025-2026. Formula: ((year - 1789) // 2) + 1
    year = date.today().year
    return ((year - 1789) // 2) + 1


def fetch_recent_bills(congress: int, api_key: str, limit: int = 100) -> list[dict]:
    url = f"{API_ROOT}/bill/{congress}"
    params = {
        "api_key": api_key,
        "format": "json",
        "sort": "updateDate+desc",
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("bills", [])


def is_relevant(bill: dict) -> bool:
    title = (bill.get("title") or "").lower()
    return any(kw in title for kw in INTEREST_KEYWORDS)


def build_dataset(api_key: str) -> dict:
    congress = current_congress_number()
    try:
        bills = fetch_recent_bills(congress, api_key)
    except requests.RequestException as exc:
        print(f"[error] Congress.gov fetch failed: {exc}", file=sys.stderr)
        bills = []

    relevant = [
        {
            "congress": b.get("congress"),
            "type": b.get("type"),
            "number": b.get("number"),
            "title": b.get("title"),
            "latest_action_date": (b.get("latestAction") or {}).get("actionDate"),
            "latest_action_text": (b.get("latestAction") or {}).get("text"),
            "url": b.get("url"),
        }
        for b in bills
        if is_relevant(b)
    ]

    return {
        "generated": date.today().isoformat(),
        "source": "Congress.gov API (api.congress.gov), requires free api.data.gov key",
        "congress": congress,
        "bills": relevant,
    }


def main():
    api_key = os.environ.get("CONGRESS_API_KEY")
    if not api_key:
        print(
            "[error] CONGRESS_API_KEY not set. Get a free key at "
            "https://api.congress.gov/sign-up/ and add it as a GitHub Actions "
            "repo secret named CONGRESS_API_KEY. Writing an empty dataset so "
            "the pipeline doesn't crash.",
            file=sys.stderr,
        )
        dataset = {
            "generated": date.today().isoformat(),
            "source": "Congress.gov API — NOT CONFIGURED (missing CONGRESS_API_KEY)",
            "congress": current_congress_number(),
            "bills": [],
        }
    else:
        dataset = build_dataset(api_key)

    out_dir = Path(__file__).resolve().parent.parent / "docs" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "congress_status.json"
    out_path.write_text(json.dumps(dataset, indent=2))
    print(f"Wrote {len(dataset['bills'])} relevant bills to {out_path}")


if __name__ == "__main__":
    main()
