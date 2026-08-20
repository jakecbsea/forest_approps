"""
Tier 1 — fully automated, no-AI data pull.

Pulls account-level budgetary resources / obligations for the four wildfire
accounts from the USASpending.gov public API (no auth, no key) and writes
JSON that the static dashboard (docs/data/) reads directly.

Run by .github/workflows/update-data.yml on a monthly schedule. Safe to run
locally too: `python scripts/fetch_usaspending.py`

USASpending API docs: https://github.com/fedspendingtransparency/usaspending-api
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

API_ROOT = "https://api.usaspending.gov/api/v2"

# toptier_code -> agency name, for the /agency/{toptier}/federal_account/ endpoint
AGENCIES = {
    "012": "Department of Agriculture (Forest Service)",
    "014": "Department of the Interior",
}

# The four accounts this project tracks, keyed by federal account symbol (AID-MAC).
# See the scoping brief for how these were confirmed (OMB apportionment + USASpending).
ACCOUNTS = {
    "012-1115": {
        "toptier": "012",
        "name": "Forest Service — Wildland Fire Management",
    },
    "012-1121": {
        "toptier": "012",
        "name": "Forest Service — Wildfire Suppression Operations Reserve Fund",
    },
    "014-1125": {
        "toptier": "014",
        "name": "Department of the Interior — Wildland Fire Management",
    },
    "014-0130": {
        "toptier": "014",
        "name": "Department of the Interior — Wildfire Suppression Operations Reserve Fund",
    },
}

# USASpending fiscal years run Oct 1 - Sep 30. Federal account-level reporting
# in the API is reliable from about FY2017 forward; start there.
START_FY = 2017


def current_fiscal_year() -> int:
    today = date.today()
    return today.year + 1 if today.month >= 10 else today.year


def fetch_federal_accounts_for_year(toptier_code: str, fiscal_year: int) -> list[dict]:
    """
    GET /api/v2/agency/{toptier_code}/federal_account/?fiscal_year=YYYY

    Returns the list of federal accounts under an agency for a fiscal year,
    each with obligated_amount / budgetary_resources (schema per USASpending
    docs as of the 2026 API version — verify against a live response the
    first time this runs, since public APIs occasionally add/rename fields).
    """
    url = f"{API_ROOT}/agency/{toptier_code}/federal_account/"
    params = {"fiscal_year": fiscal_year}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    # Defensive: the results list key has been "results" in documented versions.
    return payload.get("results", payload if isinstance(payload, list) else [])


def build_dataset() -> dict:
    end_fy = current_fiscal_year()
    records = []
    raw_debug = []  # keeps a sample of raw API responses for troubleshooting

    for account_code, meta in ACCOUNTS.items():
        toptier = meta["toptier"]
        for fy in range(START_FY, end_fy + 1):
            try:
                accounts = fetch_federal_accounts_for_year(toptier, fy)
            except requests.RequestException as exc:
                print(f"[warn] fetch failed for {account_code} FY{fy}: {exc}", file=sys.stderr)
                continue

            match = next(
                (a for a in accounts if a.get("federal_account_code") == account_code),
                None,
            )
            if match is None:
                # Account may not have existed yet (e.g., Reserve Funds pre-2020)
                # or the field name differs from what we expect — log once.
                if len(raw_debug) < 4 and accounts:
                    raw_debug.append({"account_code": account_code, "fy": fy, "sample": accounts[0]})
                continue

            records.append(
                {
                    "account_code": account_code,
                    "account_name": meta["name"],
                    "fiscal_year": fy,
                    "budgetary_resources": match.get("budgetary_resources"),
                    "obligations": match.get("obligated_amount"),
                    "outlays": match.get("gross_outlay_amount"),
                }
            )
            time.sleep(0.2)  # be polite to the public API

    return {
        "generated": date.today().isoformat(),
        "source": "USASpending.gov API (api.usaspending.gov), no auth",
        "accounts": ACCOUNTS,
        "records": records,
        "_debug_unmatched_samples": raw_debug,
    }


def main():
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_dataset()

    out_path = out_dir / "obligations.json"
    out_path.write_text(json.dumps(dataset, indent=2))
    print(f"Wrote {len(dataset['records'])} records to {out_path}")

    if dataset["_debug_unmatched_samples"]:
        print(
            "[warn] Some account/year combos returned no match — "
            "check _debug_unmatched_samples in the output JSON. "
            "This usually means the API field names shifted; update this "
            "script's field lookups accordingly.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
