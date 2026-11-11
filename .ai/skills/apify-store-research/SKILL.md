---
name: apify-store-research
description: "Research the Apify Store to find high-stats/high-ROI actor ideas and check them against an existing account's published actors so you never propose a duplicate. Use when the user asks for new actor ideas, market research, competitor scans, or 'what should we build next'."
---

# Skill: Apify Store Market Research

Two small public-API scripts do this end to end, no Apify token needed:

| Script | Hits | Purpose | Default output |
|---|---|---|---|
| `api-search-actors.py` | Algolia `prod_PUBLIC_STORE` index (same one apify.com/store's browser UI calls) | Browse/search the whole store, ranked roughly by popularity, filterable by category | `output/search-<CATEGORY>.json` (overwritten each run) |
| `apify-my-store.py` | `https://api.apify.com/v2/store?username=<x>` | List every actor a given account has already published, so you can dedupe against it | `output/<CATEGORY>.json`, one file per category |

Both live at the repo root, are self-contained (`requests` is the only
dependency), and **write JSON files by default instead of printing** — pass
`--json` or `--table` to either script if you want stdout instead (e.g. for
piping into another command). The `search-` prefix on the search script's
files is deliberate: both scripts share the same `output/` folder, and
without the prefix a `--category TRAVEL` search run would overwrite
`apify-my-store.py`'s `TRAVEL.json` (the account's *own* actors) with market
search results — two different things that must not collide.

## Workflow

### 1. Pull the account's existing inventory first
```bash
python apify-my-store.py <username>
```
Do this **before** looking at the market — you need the full list in hand to
recognize a duplicate later. Default behavior writes one JSON file per
category into `output/` (e.g. `output/ECOMMERCE.json`, `output/TRAVEL.json`)
instead of printing — an actor with multiple categories appears in each of
its category files. Use `--output mine.json` for a single combined file, or
`--json`/`--table` to print to stdout instead of writing anything. Each
record has `name`, `title`, `categories`, and `stats` (totalRuns, totalUsers)
per actor. For >100 actors the script already paginates for you.

### 2. Sanity-check the category list (it can drift)
```bash
python api-search-actors.py --list-categories
```
Prints the live `categories` facet with actor counts per category. As of
2026-08-08 the store has ~57.8k actors across: AUTOMATION, LEAD_GENERATION,
DEVELOPER_TOOLS, ECOMMERCE, SOCIAL_MEDIA, AI, OTHER, JOBS, BUSINESS,
REAL_ESTATE, SEO_TOOLS, NEWS, AGENTS, VIDEOS, INTEGRATIONS, TRAVEL,
MCP_SERVERS, MARKETING, OPEN_SOURCE, EDUCATION, SPORTS, FOR_CREATORS, GAMES,
COVID_19, DEVELOPER_EXAMPLES. Skip the generic tooling ones (AUTOMATION,
DEVELOPER_TOOLS, AI, AGENTS, MCP_SERVERS, OPEN_SOURCE) when the account's
business is scraping actors, not dev tooling — they're dominated by
unrelated SaaS/integration listings.

### 3. Scan each relevant category — aim for "underrated", not "popular"

The instinct is to sort by `totalUsers` descending and pick the top of each
category. **Don't** — the top of every category is an entrenched incumbent
(Instagram Scraper at 355k users, Google Maps Scraper at 549k) that a new
actor realistically cannot dislodge. High stats on someone else's actor is
proof the *category* has demand, not proof that *you* can win it.

The pattern actually worth hunting for looks like this account's own
`nytimes-scraper`: **51 users but 198,154 runs.** Almost nobody has
discovered it, but the handful of customers who did run it constantly — real
recurring business value, not a one-off try. That ratio (`totalRuns /
totalUsers`, exposed as `--sort runs_per_user`) is the actual signal.

```bash
# the research budget knob is --length; the "not-dominated" band is --min-users/--max-users
python api-search-actors.py --category TRAVEL --min-users 15 --max-users 5000 --length 15 --sort runs_per_user
# -> overwrites output/search-TRAVEL.json with these 15 hits, sorted by runs_per_user
```
- `--min-users` / `--max-users` apply **server-side** (Algolia `numericFilters`
  on `stats.totalUsers`) before `length`/`offset` truncate the page — so a
  small `--length` still returns the top N *within the band*, not just the
  first N of the whole unfiltered category.
- `--max-users` is the "skip if dominated" knob the whole workflow hinges on.
  Start around 5000; drop it to ~1000 for a more conservative "genuinely
  sleepy niche only" scan, or raise it if the account can credibly compete
  with a mid-size incumbent (e.g. it already has a working anti-bot bypass
  for that exact platform).
- `--sort runs_per_user` surfaces the recurring-usage signal described above.
  Treat a huge ratio from a *very* low user count (single digits to ~30)
  with some skepticism — it can mean "one enterprise customer runs this
  obsessively," not "broad demand." Cross-check with `actorReviewCount` (a
  handful of independent reviews is a better breadth signal than raw runs).
- `query=""` (the default, no `--sort`) is the Algolia index's own
  relevance/quality ranking, not a numeric sort — fine for a quick browse,
  but for the underrated-scan workflow always pass an explicit `--sort`.
- One actor can carry multiple categories, so hits collected across several
  `--category` calls will overlap. Dedupe by `objectID` (or `name`) before
  ranking a combined list — see the merge pattern below.
- Useful `stats` fields per hit: `totalUsers`, `totalRuns`, `actorReviewRating`,
  `actorReviewCount`, `bookmarkCount`. `currentPricingInfo.pricingModel`
  tells you PAY_PER_EVENT vs FLAT_PRICE_PER_MONTH vs FREE.

**Critical follow-up — re-check outside the band.** A candidate that looks
clean inside `--max-users 5000` can still be a bad idea if a giant for that
*exact same niche* just happens to sit above your ceiling and got filtered
out. Before shortlisting anything, re-run the same category **without** the
`--max-users` cap (or grep the earlier unfiltered pull) and confirm nothing
huge is hiding for that specific keyword/data-type. This is not optional —
a first pass on this account's own research missed that "LinkedIn Company
Employees Scraper" looked like a 850-user hidden gem inside the band, while
`harvestapi`'s version of the exact same niche had 21,684 users sitting just
above the cutoff. Always sanity-check the *number of distinct sellers* for
the precise data-type too, not just whether one of them individually clears
your ceiling — a niche with 15 different sellers each under 5,000 users is
still a crowded, saturated niche (LinkedIn and TikTok both look "open" per-actor
and are anything but, once you count sellers).

### 4. Merge + rank across categories (Python, not by eye)
For anything beyond a couple of categories, don't eyeball raw JSON. Run the
scan per category (each call overwrites its own `output/search-<CATEGORY>.json`,
so do this in a loop that reads the file back right after writing it, or pass
`--output` with a unique filename per category if you want to keep every
category's file around simultaneously instead of the single shared default),
then merge into a dict keyed by `objectID`:
```python
import json, subprocess

all_hits = {}
for cat in ["ECOMMERCE", "SOCIAL_MEDIA", "REAL_ESTATE", "TRAVEL", "JOBS"]:
    subprocess.run(
        ["python", "api-search-actors.py", "--category", cat, "--length", "40",
         "--output", f"output/search-{cat}.json"],
        check=True,
    )
    with open(f"output/search-{cat}.json", encoding="utf-8") as f:
        for h in json.load(f):
            all_hits[h["objectID"]] = h

ranked = sorted(all_hits.values(), key=lambda h: h["stats"].get("totalUsers", 0), reverse=True)
```
(`--json` to stdout still works too if you'd rather pipe than touch disk.)

### 5. Cross-reference against the account's own inventory (the dedupe step)
Match by **concept**, not just exact name — a competitor's "LinkedIn Profile
Scraper" and the account's "linkedin-company-profile" scraper are different
concepts (person vs company) and both can be worth building, whereas
"Zillow Detail Scraper" vs the account's existing "zillow-all-in-one-scraper"
is the same concept split differently and should count as already covered.
Practically: extract the platform/domain keyword from each candidate's
`name`/`title` (e.g. `booking`, `google-maps`, `linkedin`) and grep it
against `mine.json`'s `name` + `title` fields; anything with no match at all
is a clean candidate, anything with a match needs a manual look at *which*
data-type is covered vs missing (e.g. "Google Maps" is covered for places
search but not for reviews — still a gap).

### 6. Write up findings as sudah / belum / skip
Classify every candidate into three buckets and say why:
- **Sudah dibangun** (already covered) — same platform + same data-type
  already exists in the account, even under a different actor name.
- **Kandidat baru** (new candidate) — no existing actor covers this
  platform+data-type combination. Rank by a mix of stats (proof of demand)
  and moat reuse (do we already have working anti-bot/auth code for this
  platform from another actor?).
- **Di-skip** (explicitly rejected) — considered but rejected; always give a
  concrete reason (dominated by the platform's own first-party actor,
  ToS/legal risk, login-gated with no public path, or true duplicate of an
  existing actor). A skip without a reason is indistinguishable from "forgot
  to check it" next time this research is repeated.

## Gotchas
- **Windows console crash**: `print()`-ing a hit with emoji in its title
  (very common — sellers use ✅📩🔥 etc. to stand out) raises
  `UnicodeEncodeError` under the default `cp1252` Windows console. Both
  scripts call `sys.stdout.reconfigure(encoding="utf-8")` on startup to fix
  this — keep that if you fork them.
- The Algolia key/app-id in `api-search-actors.py` are public search-only
  credentials embedded in apify.com's own frontend bundle (not a secret,
  fine to keep committed) — they cannot write, only query the public index.
- `apify-my-store.py` only sees an account's **public** store listings. If an
  actor exists but is unpublished/private, it won't show up — if in doubt,
  ask the user to confirm rather than assuming absence means "not built."
