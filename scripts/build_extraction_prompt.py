"""
Builds a ready-to-paste prompt for the manual (offline) structural-data
refresh. Run this locally whenever you want to update data/structural.json
— typically once a year, whenever the canary check (or your own eyeballing
of the FS/DOI budget office pages) turns up a new fiscal year's budget
justification.

This makes NO API calls. It just writes a .txt file you copy into any
Claude conversation (claude.ai, the app, whatever) alongside the PDF(s) you
want parsed. Paste Claude's JSON reply into data/pending_extraction.json,
then run scripts/merge_manual_extraction.py to fold it into the dataset.

Usage:
    python scripts/build_extraction_prompt.py --target-fy 2028 \
        --urls "https://www.fs.usda.gov/.../fs-fy28-....pdf,https://www.doi.gov/.../fy2028....pdf"
"""

import argparse
from pathlib import Path

PROMPT_TEMPLATE = """You are extracting structured budget figures from a federal wildfire \
budget justification document (Forest Service or Department of the Interior), for fiscal year {target_fy}.

Source document(s) for reference (attach the PDF(s) to this message):
{urls_block}

Extract ALL enacted/requested funding lines relevant to wildland fire management. \
For each line, return an object with exactly these fields:

- "agency": "USFS" or "DOI"
- "account": the account name as written (e.g. "Wildland Fire Management", \
"Wildfire Suppression Operations Reserve Fund")
- "program_activity": one of "suppression", "preparedness", "fuels_management", "other" \
(choose the closest match; use "other" for state/volunteer fire assistance, tribal fire, \
burned area rehab, research, facilities)
- "category": one of "base_discretionary", "cap_adjustment", "supplemental" \
(cap_adjustment = funding drawn from/attributed to the Wildfire Suppression Operations \
Reserve Fund; supplemental = IIJA/IRA/disaster-relief-act funding if mentioned; \
otherwise base_discretionary)
- "fiscal_year": {target_fy}
- "amount_usd": the dollar amount as a plain integer (no commas, no $ sign; convert from \
thousands/millions if the table is scaled — state the true dollar amount)
- "notes": one short sentence of context, or null

Respond with ONLY a JSON array of these objects, wrapped in a markdown code block. \
No preamble or explanation outside the code block.
"""

INSTRUCTIONS = """
────────────────────────────────────────────────────────────────
HOW TO USE THIS (fully manual, no AI credits spent by this repo)
────────────────────────────────────────────────────────────────
1. Download the source PDF(s) listed above.
2. Open a Claude conversation (claude.ai or the app — your own account,
   your own usage, nothing automated).
3. Attach the PDF(s) and paste the prompt below.
4. Copy Claude's JSON array response.
5. Save it to: data/pending_extraction.json
6. Run: python scripts/merge_manual_extraction.py --target-fy {target_fy}
7. Review the diff, then commit data/structural.json and
   docs/data/structural.json as normal.

This whole flow costs nothing beyond whatever your own Claude usage plan
already includes — no API key lives in this repo, and no CI job calls any
AI model.
────────────────────────────────────────────────────────────────

PROMPT TO PASTE:

"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-fy", required=True, type=int)
    parser.add_argument("--urls", required=True, help="comma-separated source PDF URLs")
    args = parser.parse_args()

    urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    urls_block = "\n".join(f"- {u}" for u in urls) if urls else "- (add source URL(s) here)"

    prompt = PROMPT_TEMPLATE.format(target_fy=args.target_fy, urls_block=urls_block)
    full_text = INSTRUCTIONS.format(target_fy=args.target_fy) + prompt

    out_path = Path(__file__).resolve().parent.parent / f"extraction_prompt_fy{args.target_fy}.txt"
    out_path.write_text(full_text)
    print(f"Wrote {out_path}")
    print("Open it, follow the instructions at the top, and paste the prompt into a Claude conversation.")


if __name__ == "__main__":
    main()
