# Sierra Leone Government Tenders Scraper

Scrapes Sierra Leone's official government tender/procurement notices from
the National Public Procurement Authority (NPPA) "Bids / Tenders" board at
`nppa.gov.sl/bid/`. For each tender you get the procuring government
entity, when it was posted, when it expires, a description, and a direct
link to the tender document (PDF). No account, login, or API key needed.

## Why this actor exists

NPPA also runs a newer e-GP (electronic Government Procurement) platform
(`egp.nppa.gov.sl`), which would normally be the richer source — but as of
this actor's last check its tender-listing backend service is down
(`502 Bad Gateway` on every path, confirmed over multiple retries), and its
separate Open Contracting Data Standard export is live but currently has
zero published records. NPPA's older WordPress site, however, publishes
the same real tender notices by hand on a plain page that has none of
those problems — this actor targets that page instead. See
`CRAWLING_METHOD.md` for the full investigation.

## What this actor returns — and what it doesn't

Each record is one tender exactly as published on NPPA's board:
procuring entity, the raw "Date Posted" / "Expiration Date" text (plus a
best-effort parsed date for each), a free-text description, and the PDF
document link. It does **not** return a tender reference/lot number as a
separate field — NPPA's board doesn't have one; any such number only
appears incidentally inside the free-text description or PDF filename.
It also doesn't download or read the PDF itself, only links to it.

## Input

```json
{
  "keyword": "roads",
  "onlyOpenTenders": false,
  "maxResults": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `keyword` | string | Only return tenders whose procuring entity or description contains this text (case-insensitive). Leave blank to return every tender on the board. |
| `keywords` | array | Run multiple keyword filters in one job. Combined with `keyword` if both are set. |
| `onlyOpenTenders` | boolean | If true, excludes tenders whose Expiration Date has already passed. NPPA's board does not auto-remove expired entries -- most rows on the board at any given time are typically already expired. Rows whose date can't be parsed are kept either way. Default `false`. |
| `maxResults` | integer | Caps how many records are pushed per keyword (default 100, max 1000). The whole board is one page (~30 rows as of this writing), so this is mostly a safety cap. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per tender. Real output for `{"keyword": "roads", "maxResults": 1}`:

```json
{
  "_input": "roads",
  "_source": "S1-bid-tenders-table",
  "_scrapedAt": "2026-08-27T04:05:42Z",
  "_rowIndex": 5,
  "biddingOrganization": "SIERRA LEONE ROADS AUTHORITY",
  "datePosted": "02-07-2026",
  "datePostedIso": "2026-07-02",
  "expirationDate": "13-08-2026",
  "expirationDateIso": "2026-08-13",
  "isExpired": true,
  "descriptionOfBidding": "MANO RIVER UNION ROAD DEVELOPMENT AND TRANSPORT FACILITATION PROGRAMME PHASE IV",
  "documentUrl": "https://nppa.gov.sl/wp-content/uploads/2026/07/INVITATION-FOR-BID-JULY-2026.pdf",
  "_totalMatches": 4,
  "_truncated": true
}
```

("roads" matched 4 tenders total; "... 3 more" with the default `maxResults`.)

A keyword matching nothing produces one record instead:

```json
{
  "_input": "zzznotarealkeyword",
  "_source": "none",
  "_scrapedAt": "2026-08-27T04:06:00Z",
  "_error": "no_results"
}
```

| Field | Description |
|---|---|
| `_input` | The keyword that produced this record, or `"(all bids)"` when no keyword filter was given. |
| `_source` | Extraction strategy (`S1-bid-tenders-table`, or `none` on error). |
| `_scrapedAt` | UTC ISO 8601 timestamp. |
| `_rowIndex` | 0-based position of this tender in NPPA's table (newest first, as published). |
| `_totalMatches` / `_truncated` | Total tenders matching this keyword before any `maxResults` cap, and whether the cap actually cut the output short. |
| `biddingOrganization` | The procuring government entity, exactly as published (upstream formatting quirks preserved verbatim). |
| `datePosted` / `expirationDate` | Raw date text exactly as published (format is inconsistent upstream). |
| `datePostedIso` / `expirationDateIso` | Best-effort `YYYY-MM-DD` parse of the above. Omitted if it genuinely can't be parsed. |
| `isExpired` | `true` if the parsed expiration date is before today (UTC). Omitted if the date couldn't be parsed. |
| `descriptionOfBidding` | Free-text description of the tender, exactly as published. |
| `documentUrl` | Direct link to the tender's PDF. Omitted when NPPA's own row has a broken/missing download link (happens occasionally -- a real upstream data-quality issue, not a parsing failure). |
| `_error` / `_errorDetail` | Present only on a failed/empty job: `no_results` (keyword matched nothing) or `blocked_or_transient` (network/blocking problem fetching the board). |

## Notes

- See `CRAWLING_METHOD.md` for the full technical writeup, including why
  NPPA's newer e-GP platform can't currently be used and the exact page
  this actor targets instead.
