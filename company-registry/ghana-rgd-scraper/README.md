# Ghana Business Registry Name Search

Search Ghana's official business registry — the Office of the Registrar of Companies (ORC) — for registered business and company names, and their entity type. Automates the same public "Name Search" tool available at `rgdonline.gegov.gov.gh/orc-app/`. No account, login, or API key needed.

## What this actor returns — and what it doesn't

This is a **name-availability / name-collision checker**, the same tool ORC provides so people about to register a business can check whether a name is already taken. For each matching business it returns:

- **Business name** (exactly as registered)
- **Entity type** — e.g. Sole Proprietor, Company Limited by Shares, Company Limited by Guarantee, Partnership, External Company, Subsidiary Business Name

It does **not** return registration numbers, incorporation dates, status (active/dissolved), registered address, or director/officer names — ORC's public search tool does not expose those fields. Getting them requires requesting a paid certified extract directly from ORC. If your use case needs a full company profile rather than a name/type lookup, this actor is not a fit — but if you need to check name availability, find every business matching a keyword or sector term, or screen a brand name against the official registry, this gives you exactly what ORC's own website gives a human visitor, at scale.

## Why use this actor

- Searches Ghana's real, current company registry — not the old/legacy `rgd.gov.gh` domain (which is neglected and partially compromised with injected spam links — see `CRAWLING_METHOD.md`)
- No login or CAPTCHA — the actor handles the session/CSRF handshake automatically
- Four match modes: exact, starts with, ends with, contains
- Truncation-aware output: every record reports how many matches actually exist upstream, even if you cap how many get pushed to your dataset

## Input

```json
{
  "businessNames": ["MTN", "COCOA BOARD"],
  "searchType": "cn",
  "maxResultsPerQuery": 200,
  "maxConcurrency": 2,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `businessName` | string | A single business/company name (or fragment) to search for. |
| `businessNames` | array | Multiple names/fragments to search for in one run. |
| `searchType` | string | `"eq"` exact match, `"sw"` starts with, `"ew"` ends with, `"cn"` (default) contains. |
| `maxResultsPerQuery` | integer | Caps how many matches are pushed to the dataset per query (default 200, max 2000). The registry has no server-side result limit — a broad `"cn"` query for a common word can match tens of thousands of names (`"GHANA"` matches 37,659), so the full response is always downloaded regardless of this cap; it only limits the output. |
| `maxConcurrency` | integer | Parallel queries (default 2, max 5) — kept low since this is a small, early-stage (`v0.0.1`) government web app. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

**Tip:** prefer specific/narrow search terms. A single generic word can trigger an 11+ MB response from the registry before any truncation happens.

## Output

One record per matching business name. Real output for `{"businessName": "MTN", "searchType": "cn"}`:

```json
{
  "_input": "MTN",
  "_source": "S1-name-search",
  "_scrapedAt": "2026-08-26T17:34:45Z",
  "searchType": "cn",
  "_totalAvailable": 8,
  "_truncated": false,
  "businessName": "MTN GHANA FOUNDATION LBG",
  "businessType": "Company Limited by Guarantee",
  "businessTypeCode": "CG"
}
```

A query with zero matches produces one record instead:

```json
{
  "_input": "XZQPLKQWERTYNOTREAL",
  "_source": "S1-name-search",
  "_scrapedAt": "2026-08-26T17:34:50Z",
  "searchType": "cn",
  "_totalAvailable": 0,
  "_truncated": false,
  "_error": "no_results"
}
```

| Field | Description |
|---|---|
| `_input` | The exact query string that produced this record. |
| `_source` | Extraction strategy (`S1-name-search`, or `none` on error). |
| `_scrapedAt` | UTC ISO 8601 timestamp. |
| `_error` / `_errorDetail` | Present only on failed/empty queries: `no_results`, `invalid_query` (ORC's own validation message, e.g. "Please enter name to search for"), or `blocked_or_transient`. |
| `searchType` | The match mode used for this query. |
| `_totalAvailable` | Total matches ORC reported for this query, before truncation. |
| `_truncated` | `true` if `_totalAvailable` exceeded `maxResultsPerQuery`. |
| `businessName` | The registered business name. |
| `businessType` | Human-readable entity type (see table below). |
| `businessTypeCode` | The registry's internal short code for `businessType`. |

Entity type codes observed so far (not necessarily exhaustive):

| Code | Label |
|---|---|
| `BN` | Sole Proprietor |
| `CG` | Company Limited by Guarantee |
| `CS` | Company Limited by Shares |
| `ET` | External Company |
| `PN` | Partnership |
| `SN` | Subsidiary Business Name |

## Notes

- The upstream registry itself sometimes lists a business name twice (an ORC data-quality issue, not a bug here) — matches are passed through raw, not deduplicated.
- See `CRAWLING_METHOD.md` for the full technical writeup, including why `rgd.gov.gh` (the domain most people would guess) is not actually where this data lives, and the exact CSRF/htmx request sequence required to get real results instead of a silent redirect.
