# Wildfire Appropriations Tracker

An automated dashboard tracking federal wildfire suppression/preparedness
funding — obligations, budget authority, the suppression cap-adjustment
mechanism, and CR/appropriations status — for USFS and DOI wildland fire
accounts.

**No AI runs automatically anywhere in this repo.** The live data (Tier 1)
updates itself for free from public government APIs. The structural
picture (Tier 2 — base vs. cap-adjustment funding, sourced from PDFs) is
refreshed manually, by you, whenever you choose: this repo just tells you
*when* a refresh is due — it never calls an AI model on its own, and no AI
API key is stored anywhere in this repo.

## How it's structured

**Tier 1 — fully automated, free, no AI.** A monthly GitHub Actions job
pulls live data from the USASpending.gov API (obligations by account) and
the Congress.gov API (CR/appropriations bill status), writes it to
`docs/data/*.json`, and GitHub Pages redeploys the static dashboard
automatically. Runs forever at no cost.

**Tier 2 — manual, offline, zero ongoing AI cost.** A free monthly check
(plain HTTP requests, no AI) looks for a new fiscal year's budget
justification PDF. If it finds one, it opens a **GitHub issue** telling
you a refresh is due — nothing more. When you're ready, you run one script
to generate a ready-to-paste prompt, paste it (with the PDF) into your own
Claude conversation by hand, save the reply, and run a second script to
validate and merge it in. This costs whatever your own Claude usage
already covers — nothing recurring, nothing automated, no API key in this
repo at all.

```
docs/index.html                    ← the dashboard (no build step, no framework)
docs/data/*.json                   ← data the dashboard reads (committed, versioned)
scripts/fetch_usaspending.py       ← Tier 1, no auth
scripts/fetch_congress.py          ← Tier 1, needs a free Congress.gov key
scripts/canary_check.py            ← free, no-AI check for new source PDFs
scripts/build_extraction_prompt.py ← writes a prompt you paste into Claude yourself
scripts/merge_manual_extraction.py ← validates + merges what you paste back
.github/workflows/update-data.yml     ← monthly Tier 1 cron (free)
.github/workflows/canary-issue.yml    ← monthly check → opens an issue if due (free, no AI)
.github/workflows/deploy-pages.yml    ← redeploys the site on data changes
```

## One-time setup

1. **Push this repo to GitHub** as a new **public** repository (public
   repos get unlimited free Actions minutes on standard runners and free
   Pages hosting).

2. **Enable GitHub Pages**: repo Settings → Pages → Source → "GitHub
   Actions". The `deploy-pages.yml` workflow handles the rest.

3. **Get a free Congress.gov API key**: https://api.congress.gov/sign-up/
   (instant, no cost, no credit card). If you already generated one and
   shared it anywhere outside this repo's secret storage, regenerate it —
   treat any key you've pasted elsewhere as compromised, even a free one.

4. **Add it as a repo secret**: Settings → Secrets and variables →
   Actions → New repository secret → name it `CONGRESS_API_KEY`.
   That's the only secret this repo needs. There is no Anthropic/AI key
   to add anywhere.

5. **Run the Tier 1 workflow once manually** to seed real data instead of
   waiting for the first scheduled run: Actions tab → "Update Tier 1 data"
   → "Run workflow".

That's it. After this:
- Tier 1 refreshes monthly, forever, for free, untouched by you.
- Tier 2 checks monthly for free and opens a GitHub issue when a refresh
  is due. You do the actual refresh by hand, on your own schedule, using
  your own Claude account — it is never triggered automatically.

## Doing a manual (Tier 2) refresh

When you get the GitHub issue (or just decide it's time):

```bash
python scripts/build_extraction_prompt.py --target-fy 2028 \
  --urls "https://www.fs.usda.gov/.../fs-fy28-....pdf,https://www.doi.gov/.../fy2028....pdf"
```

This writes `extraction_prompt_fy2028.txt` with full instructions. Open
it, follow the steps: paste the prompt and the source PDF(s) into any
Claude conversation, save the JSON reply to `data/pending_extraction.json`,
then:

```bash
python scripts/merge_manual_extraction.py --target-fy 2028
```

This validates the figures (checks categories, checks amounts aren't
implausibly large/small — likely a units error — and flags anything odd
into `data/extraction_warnings_fy2028.json` instead of merging it
silently), merges the clean records into `data/structural.json` and
`docs/data/structural.json`, and tells you what's left to review before
you commit.

## Known limitations / things to revisit

- **Account continuity risk**: DOI is standing up a U.S. Wildland Fire
  Service that may eventually consolidate USFS wildfire funding into DOI.
  If that happens, the account codes this tracker watches
  (`012-1115`, `012-1121`, `014-1125`, `014-0130`) may be retired or
  restructured. If the USASpending fetch starts returning empty results
  for an account that used to have data, check whether it's been renamed
  or merged before assuming the pipeline is broken.
- **USASpending API field names**: `scripts/fetch_usaspending.py` was
  written against the documented schema at scoping time. If the API
  changes field names, the script logs unmatched samples to
  `_debug_unmatched_samples` in the output JSON rather than failing
  silently — check there first if obligations data looks empty.
- **The canary check is deliberately conservative** (see comments in
  `canary_check.py`). If an agency redesigns its website, the canary may
  need its URL patterns updated by hand — this is the one piece of the
  pipeline that isn't guaranteed to be maintenance-free forever, though it
  costs nothing to sit idle if it starts missing things. You can always
  just check the FS/DOI budget pages yourself once a year regardless.
- `data/structural.json` ships seeded with only well-sourced, citable
  figures (the statutory cap-adjustment schedule and the FY2015 base
  freeze amounts) — not a full historical time series. Manual extraction
  fills this in going forward; backfilling prior years is a one-time task
  if you want it (see the scoping brief for source PDFs).
