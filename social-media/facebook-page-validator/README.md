# Facebook Page Validator & Brand Slug Checker

Check a list of Facebook slugs and get back, for each one, whether it resolves to a real page — and whether that page actually belongs to the brand you expected.

**Facebook answers HTTP 200 for pages that do not exist.** A slug you invented, a slug from a stale CRM export and a slug belonging to a real company all come back `200 OK`. Any checker built on status codes marks all three as valid. This actor distinguishes them.

## The problem it solves

Two different failures hide in a list of Facebook URLs, and both look fine from the outside:

**The slug is dead.** `facebook.com/some-company-that-rebranded` returns 200 with an empty shell. Your outreach tool records a valid link, your team clicks it in three weeks and finds nothing.

**The slug is alive but belongs to somebody else.** This is the one that costs you. `facebook.com/bukalapak` is not the Indonesian marketplace — it is an app page called *Eoddata beeip.com* with 124 followers. Guessing brand slugs from company names produces these constantly, and an existence check waves every one of them through.

Give this actor an expected brand per slug and it reports `EXACT`, `STRONG`, `WEAK` or `MISMATCH` against the page's real name.

## What you get per slug

| Field | What it tells you |
|---|---|
| `exists` / `status` | Does the slug resolve to a page at all |
| `name` / `pageId` | Who the page actually is |
| `brandMatch` / `brandMatchScore` | Whether that is who you expected |
| `followers` / `followersLabel` | Audience size, plus the label Facebook rendered |
| `primaryCategory` / `categories` | How Facebook classifies the page |
| `phones` / `websites` / `emails` / `addresses` | Public contact details from the about tab |
| `payloadTier` / `postsAreTrustworthy` | How complete Facebook's answer was — see below |

## Quick start

Existence only:

```json
{ "slugs": ["nike", "starbucks", "some-slug-you-are-unsure-about"] }
```

Existence plus brand verification:

```json
{
  "pages": [
    { "slug": "bukalapak", "expectedBrand": "Bukalapak" },
    { "slug": "tokopedia", "expectedBrand": "Tokopedia" }
  ],
  "onlyBrandMismatch": true
}
```

`nike`, `facebook.com/nike` and `https://www.facebook.com/nike/` all reduce to the same slug, so you can paste URLs straight from a spreadsheet.

### Cleaning a list

Set `onlyNotFound: true` to get just the dead slugs — the rows to delete. Set `onlyBrandMismatch: true` to get just the ones pointing at the wrong company — the rows to re-research. The `RUN_SUMMARY` record carries the totals either way, including `mismatchedSlugs`.

## The payload tier, and why it is on every record

Facebook returns one of three response sizes, and the boundaries were measured rather than assumed (20 pages × 3 repeats, deterministic):

| Tier | Size | Meaning |
|---|---|---|
| `HOLLOW` | ~330 KB | No such page. A known-fake control slug returns exactly this. |
| `REDUCED` | ~0.7–1.4 MB | The page exists and the header is present, but Facebook withheld the post feed. |
| `FULL` | ≥1.5 MB | Header plus roughly ten posts. |

`REDUCED` is the tier that misleads people. On it, `postsInPayload` is **0 for pages that post every day** — NASA came back reduced on three consecutive fetches, Coca-Cola carried two posts. It is sticky per page, not a random throttle, so retrying does not clear it.

That is why `postsAreTrustworthy` exists and why this actor does not sell you a posting-frequency metric. A zero post count on a `REDUCED` payload is an absence of evidence, not evidence of absence, and any tool that averages the two together will quietly tell you an active competitor has gone dormant.

Follower count, name, category and contact details are read correctly on `REDUCED` payloads, so those fields are unaffected.

## Limits worth knowing

- **Approximate follower counts.** Facebook renders `39M`, not `39,214,880`. `followers` is the parsed integer; `followersLabel` preserves what was actually shown. For small pages the count is exact.
- **Only public data.** Whatever a logged-out visitor cannot see, this cannot see. Many pages publish no phone or email at all.
- **No post feed, no engagement metrics.** Paginating posts requires a `doc_id` that Facebook no longer ships in page HTML, so it is out of scope by design rather than by omission.
- **Personal profiles are not pages.** `profile.php` and the other reserved paths are rejected rather than guessed at.
- **Brand matching is a signal, not a verdict.** `WEAK` means "a human should look at this". Regional pages like `Kopi Kenangan | South Jakarta` score as `STRONG` against `Kopi Kenangan`, which is usually right but not always what you want.

## Cost and proxy

One request per slug, no login, no cookies, no token handshake. **Leave the proxy off** — this surface applies no TLS fingerprint gate (all 16 profiles tested return 200) and no IP gate, so a proxy adds latency and cost for nothing.

Pages are large, up to ~20 MB each, and Facebook sends no `content-length` and ignores `Range` requests, so the full body must be downloaded to classify it. That is fast in practice (~1s for an 8 MB page) and the actor fetches concurrently; raise `concurrency` to go faster at the cost of memory.

## Output shape

Every record carries `_input`, `_source`, `_scrapedAt` and `recordType`. `recordType` is `PAGE` for a checked slug, `RUN_SUMMARY` once per run, and `ERROR` for a slug that could not be fetched. Three dataset views are provided: **Overview**, **Brand check** and **Contacts**. Optional `exportFormats` also writes JSON, NDJSON, CSV or XLSX to the key-value store.

## Development

```bash
pip install -r requirements.txt
python -m src            # needs an Apify runtime
python test_local.py     # runs the checker against live pages, no Apify needed
```

`CRAWLING_METHOD.md` documents where each field comes from and which markers the parser keys off.
