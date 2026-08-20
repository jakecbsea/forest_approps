"""
Merges a manually-pasted Claude extraction (data/pending_extraction.json)
into the versioned data/structural.json dataset. Run this locally after
you've followed the steps in an extraction_prompt_fy*.txt file.

Makes NO API calls — this is pure validation and file-merging.

Usage:
    python scripts/merge_manual_extraction.py --target-fy 2028
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STRUCTURAL_PATH = DATA_DIR / "structural.json"
PENDING_PATH = DATA_DIR / "pending_extraction.json"
DOCS_DATA_DIR = ROOT / "docs" / "data"

VALID_CATEGORIES = {"base_discretionary", "cap_adjustment", "supplemental"}
VALID_ACTIVITIES = {"suppression", "preparedness", "fuels_management", "other"}


def validate_records(records: list, target_fy: int) -> tuple[list, list]:
    clean, warnings = [], []

    for i, r in enumerate(records):
        problems = []
        if r.get("agency") not in {"USFS", "DOI"}:
            problems.append("agency not USFS/DOI")
        if r.get("category") not in VALID_CATEGORIES:
            problems.append("category not in allowed set")
        if r.get("program_activity") not in VALID_ACTIVITIES:
            problems.append("program_activity not in allowed set")
        amount = r.get("amount_usd")
        if not isinstance(amount, (int, float)) or amount <= 0:
            problems.append("amount_usd missing/non-positive")
        elif amount > 10_000_000_000:
            problems.append(f"amount_usd implausibly large ({amount}) — check units")
        elif amount < 1000:
            problems.append(f"amount_usd implausibly small ({amount}) — check units")
        if r.get("fiscal_year") != target_fy:
            problems.append(f"fiscal_year {r.get('fiscal_year')} != target {target_fy}")

        if problems:
            warnings.append({"index": i, "record": r, "problems": problems})
        else:
            clean.append(r)

    return clean, warnings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-fy", required=True, type=int)
    args = parser.parse_args()

    if not PENDING_PATH.exists():
        print(f"[error] {PENDING_PATH} not found. Save Claude's JSON response there first.")
        return

    try:
        records = json.loads(PENDING_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[error] {PENDING_PATH} isn't valid JSON: {exc}")
        print("Check for stray markdown fences or trailing commas and try again.")
        return

    if not isinstance(records, list):
        print("[error] Expected a JSON array at the top level.")
        return

    clean, warnings = validate_records(records, args.target_fy)

    print(f"{len(clean)} record(s) passed validation.")
    if warnings:
        print(f"{len(warnings)} record(s) flagged — NOT merged, review these manually:")
        for w in warnings:
            print(f"  [{w['index']}] {w['problems']}")
        warn_path = DATA_DIR / f"extraction_warnings_fy{args.target_fy}.json"
        warn_path.write_text(json.dumps(warnings, indent=2))
        print(f"Full detail written to {warn_path}")

    if not clean:
        print("Nothing clean to merge. Fix the flagged records and re-run.")
        return

    existing = json.loads(STRUCTURAL_PATH.read_text()) if STRUCTURAL_PATH.exists() else {"records": []}
    existing["generated"] = date.today().isoformat()
    existing["records"] = existing.get("records", []) + clean
    STRUCTURAL_PATH.write_text(json.dumps(existing, indent=2))

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(STRUCTURAL_PATH, DOCS_DATA_DIR / "structural.json")

    print(f"Merged {len(clean)} record(s) into {STRUCTURAL_PATH} and copied to docs/data/.")
    print(f"You can now delete {PENDING_PATH} and commit the changes.")


if __name__ == "__main__":
    main()
