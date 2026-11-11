# Malawi Government Tenders Scraper

Scrapes Malawi's official government procurement notices from the **Public
Procurement and Disposal of Assets Authority (PPDA)**'s own website,
`ppda.mw`. Covers open tenders, award notices, intentions to award, and
debarred suppliers — each pulled straight from PPDA's public notice boards.
No account, login, or API key needed.

## Why this actor exists

Malawi also runs a modern e-GP (electronic Government Procurement)
platform called **MANEPS** (`maneps.mw`, built by the same vendor —
Perago Systems — behind Sierra Leone's `egp.nppa.gov.sl`), which would
normally be the richer source. But its tender-listing page is a
JavaScript single-page app with zero data in the initial HTML response —
a real browser has to run its JS to see anything. PPDA's own corporate
website, however, publishes the same notices on plain, fully
server-rendered pages with no such requirement — this actor targets those
pages instead. See `CRAWLING_METHOD.md` for the full investigation.

## What this actor returns — and what it doesn't

Each record is one notice exactly as published on one of PPDA's boards.
Which fields are present depends on `noticeType` — PPDA's own tables don't
have the same columns for every category:

- **`tenders`** (Open Tenders): title, institution, reference number,
  publish date, closing date, attachment link.
- **`awards`** (Award Notices): same as tenders, minus closing date.
- **`intentions`** (Intentions to Award): same as awards, plus a
  "Financial Year" field (e.g. `"2023/2024"`).
- **`debarments`** (Debarred Suppliers): title, publish date, attachment
  link only — PPDA's debarment table has no institution/reference columns.
- **`admin_reviews`** (Administrative Review Notices): PPDA's board for
  this category was empty at the time this actor was built ("No
  publications available at the moment") — included for completeness and
  will start returning rows automatically if/when PPDA publishes one.

This actor does not download or read the linked PDF documents, only links
to them. It also does not attempt to reach MANEPS (`maneps.mw`) — see
above.

## Input

```json
{
  "noticeTypes": ["tenders"],
  "keyword": "hospital",
  "onlyOpenTenders": false,
  "maxResults": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `noticeTypes` | array | Which PPDA board(s) to fetch: `tenders`, `awards`, `intentions`, `debarments`, `admin_reviews`. Default `["tenders"]`. |
| `keyword` | string | Only return notices whose title, institution, or reference number contains this text (case-insensitive). Leave blank to return every notice on the selected board(s). |
| `keywords` | array | Run multiple keyword filters in one job. Combined with `keyword` if both are set. |
| `onlyOpenTenders` | boolean | If true, excludes `tenders` rows whose Closing Date has already passed. No effect on the other boards (they don't have a closing date). Default `false`. |
| `maxResults` | integer | Caps how many records are pushed per notice board per keyword (default 100, max 1000). Each board is a single page (tens to low hundreds of rows), so this is mostly a safety cap. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

One record per notice. Real output for `{"noticeTypes": ["tenders"], "maxResults": 1}`:

```json
{
  "_input": "(all notices)",
  "_source": "S1-ppda-notice-tables",
  "_scrapedAt": "2026-08-27T05:41:52Z",
  "_rowIndex": 0,
  "noticeType": "tenders",
  "title": "RE-ADVERT-PROCUREMENT OF FUMIGATION SERVICES",
  "institution": "Public Procurement and Disposal of Assets Authority",
  "referenceNo": "PPDA/FUMIGATION/08/2026",
  "publishDate": "2026-08-26",
  "closingDate": "2026-09-01",
  "attachmentUrl": "https://ppda.mw/storage/documents/opentenders/RFQ FUMIGATION SERVICES 1.pdf",
  "isClosed": false,
  "_totalMatches": 39,
  "_truncated": true
}
```

And for `{"noticeTypes": ["debarments"], "maxResults": 1}` (a board without
institution/reference columns):

```json
{
  "_input": "(all notices)",
  "_source": "S1-ppda-notice-tables",
  "_scrapedAt": "2026-08-27T05:42:05Z",
  "_rowIndex": 0,
  "noticeType": "debarments",
  "title": "Debarment of Suppliers - 15 August 2025",
  "publishDate": "2025-10-21",
  "attachmentUrl": "https://ppda.mw/storage/documents/ebarments//PRESS RELEASE ON DEBARMENT OF SUPPLIER - 15 AUGUST 2025 REVISED.pdf",
  "_totalMatches": 5,
  "_truncated": true
}
```

A keyword matching nothing produces one record instead:

```json
{
  "_input": "zzznonexistentqueryxyz",
  "_source": "none",
  "noticeType": "tenders",
  "_scrapedAt": "2026-08-27T05:42:24Z",
  "_error": "no_results"
}
```

| Field | Description |
|---|---|
| `_input` | The keyword that produced this record, or `"(all notices)"` when no keyword filter was given. |
| `_source` | Extraction strategy (`S1-ppda-notice-tables`, or `none` on error). |
| `_scrapedAt` | UTC ISO 8601 timestamp. |
| `_rowIndex` | 0-based position of this notice in PPDA's table (as published upstream). |
| `_totalMatches` / `_truncated` | Total notices on this board matching this keyword before any `maxResults` cap, and whether the cap actually cut the output short. |
| `noticeType` | Which board this record came from. |
| `title` | The notice's title, exactly as published. |
| `institution` | The procuring government entity. Absent on `debarments`. |
| `referenceNo` | Tender/notice reference number. Absent on `debarments`. |
| `financialYear` | Malawi government financial year (e.g. `"2023/2024"`). Only present on `intentions`. |
| `publishDate` / `closingDate` | ISO 8601 (`YYYY-MM-DD`) dates, already clean as published upstream. `closingDate` only present on `tenders`. |
| `isClosed` | `true` if `closingDate` is before today (UTC). Only computed for `tenders`. |
| `attachmentUrl` | Direct link to the notice's PDF. Omitted when the row has no download link. |
| `_error` / `_errorDetail` | Present only on a failed/empty job: `no_results` (keyword matched nothing) or `blocked_or_transient` (network/blocking problem fetching the board). |

## Notes

- See `CRAWLING_METHOD.md` for the full technical writeup, including why
  Malawi's newer MANEPS e-GP platform can't currently be used and the
  exact pages this actor targets instead.
