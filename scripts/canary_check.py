"""
Canary check for the manual (offline) structural-data refresh.

CRS/budget-justification PDFs only update once a year, on a schedule that
shifts with the appropriations calendar. This script probes a small set of
known/predictable document URLs for the *next* fiscal year beyond what's
already in data/structural.json.

This script makes NO AI calls and costs nothing to run. When it finds a new
document, the GitHub Actions workflow that calls this opens a GitHub issue
containing a ready-to-paste prompt (see scripts/build_extraction_prompt.py)
so a human can run the extraction manually, in their own Claude conversation,
whenever they choose — no API key lives in this repo at all.

Exits 0 always. Writes result to GITHUB_OUTPUT so the workflow can branch.
"""

import os
import re
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STRUCTURAL_PATH = DATA_DIR / "structural.json"

# {fy2}/{fy4} are replaced with the two-digit/four-digit fiscal year.
# These patterns are copied from confirmed URLs at scoping time — the year
# component is what changes annually. If an agency redesigns its site,
# these patterns need a manual update (see README "known limitations").
PROBE_URL_TEMPLATES = [
    "https://www.fs.usda.gov/sites/default/files/fs-fy{fy2}-congressional-budget-justification.pdf",
    "https://www.doi.gov/sites/default/files/documents/{fy4}-04/fy{fy4}greenbookuswfs.pdf",
]


def latest_fy_in_structural_data() -> int:
    if not STRUCTURAL_PATH.exists():
        return 0
    text = STRUCTURAL_PATH.read_text()
    years = [int(y) for y in re.findall(r'"fiscal_year":\s*(\d{4})', text)]
    return max(years) if years else 0


def probe(url: str) -> bool:
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        if resp.status_code == 405:  # some servers reject HEAD; fall back to GET
            resp = requests.get(url, timeout=15, stream=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def main():
    latest_known_fy = latest_fy_in_structural_data()
    target_fy = latest_known_fy + 1

    found_urls = []
    for template in PROBE_URL_TEMPLATES:
        url = template.format(fy2=str(target_fy)[-2:], fy4=target_fy)
        if probe(url):
            found_urls.append(url)

    new_source_found = "true" if found_urls else "false"

    print(f"Latest FY in structural.json: {latest_known_fy}")
    print(f"Probing for FY{target_fy} documents...")
    for url in found_urls:
        print(f"  found: {url}")
    if not found_urls:
        print(f"  nothing found yet for FY{target_fy} at known URL patterns.")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"new_source_found={new_source_found}\n")
            fh.write(f"target_fy={target_fy}\n")
            fh.write("found_urls=" + ",".join(found_urls) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
