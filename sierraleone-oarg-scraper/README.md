# Sierra Leone Business Registry Name Search

Search Sierra Leone's official business registry — the Office of the Administrator and Registrar-General (OARG) — to check whether a business name is already registered, and see every existing matching name. Automates the same public "Company Search" tool available at `oarg.gov.sl/company-search/`. No account, login, or API key needed.

## What this actor returns — and what it doesn't

This is a **name-availability / name-collision checker**, the same tool OARG provides so people about to register a business can check whether their candidate name is already taken. For each query it returns either:

- **The name is available** — no existing business is registered under a matching name, or
- **One record per existing matching business name** — every registered business name that contains your query text.

It does **not** return registration numbers, incorporation dates, status (active/dissolved), registered address, business type, or director/owner names — OARG's public search tool does not expose those fields at all; there is no other online lookup on the site that does. If your use case needs a full company profile rather than a name check, this actor is not a fit — but if you need to check name availability before registering, or find every business matching a keyword, this gives you exactly what OARG's own website gives a human visitor, at scale.

## Why use this actor

- Searches Sierra Leone's real, live registry search — the main `oarg.gov.sl` WordPress site is currently broken (returns HTTP 500 on every page due to a theme bug), but this actor targets the separate, working legacy search app that the broken site doesn't affect
- No login, no CAPTCHA, no session/CSRF handshake — a single stateless request per query
- Truncation-aware output: every record reports how many matches actually exist upstream, even if you cap how many get pushed to your dataset
- Rejects known-bad queries (names containing `'` or `;`) client-side instead of sending a request that would crash the upstream server and waste your run

## Input

```json
{
  "businessNames": ["TRADING", "BANK"],
  "maxResultsPerQuery": 200,
  "maxConcurrency": 3,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `businessName` | string | A single business/company name (or fragment, minimum 3 characters) to search for. |
| `businessNames` | array | Multiple names/fragments to search for in one run. |
| `maxResultsPerQuery` | integer | Caps how many matches are pushed to the dataset per query (default 200, max 2000). The registry has no server-side result limit — a common word can match thousands of names (`"TRADING"` matches 1,972), so the full response is always downloaded regardless of this cap; it only limits the output. |
| `maxConcurrency` | integer | Parallel queries (default 3, max 5). |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

**Note:** queries must be at least 3 characters (the site's own rule) and must not contain an apostrophe (`'`) or semicolon (`;`) — either character crashes OARG's search backend with a suppressed server error. This actor detects both cases and returns a clear `_error` record instead of sending a doomed request.

## Output

One record per matching business name. Real output for `{"businessName": "BANK"}`:

```json
{
  "_input": "BANK",
  "_source": "S1-company-search",
  "_scrapedAt": "2026-08-26T22:36:14Z",
  "nameExists": true,
  "_totalMatches": 138,
  "_truncated": false,
  "matchedBusinessName": "SKYE BANK (SL) LIMITED"
}
```

(138 total matches with the default `maxResultsPerQuery: 200` cap all get pushed — one record per matching name, "... 137 more" in this example.)

A query with no matches produces one record instead:

```json
{
  "_input": "zzznotexist123abc",
  "_source": "S1-company-search",
  "_scrapedAt": "2026-08-26T22:35:26Z",
  "nameExists": false,
  "_totalMatches": 0,
  "_truncated": false
}
```

An invalid or unsafe query also produces one record:

```json
{
  "_input": "O'Brien",
  "_source": "none",
  "_scrapedAt": "2026-08-26T22:35:26Z",
  "_error": "unsafe_query",
  "_errorDetail": "Query contains [\"'\"] -- known to crash OARG's backend (upstream bug, not a transient failure). Query rejected client-side without sending a request."
}
```

| Field | Description |
|---|---|
| `_input` | The exact query string that produced this record. |
| `_source` | Extraction strategy (`S1-company-search`, or `none` on error). |
| `_scrapedAt` | UTC ISO 8601 timestamp. |
| `nameExists` | `true` if the query matched an existing registered name, `false` if available. |
| `_error` / `_errorDetail` | Present only on failed/invalid queries: `invalid_query` (under 3 characters), `unsafe_query` (contains `'`/`;`), `upstream_backend_error` (server crashed anyway), `blocked_or_transient`. |
| `_totalMatches` | Total matches OARG reported for this query, before truncation. |
| `_truncated` | `true` if `_totalMatches` exceeded `maxResultsPerQuery`. |
| `matchedBusinessName` | The registered business name (present only when `nameExists` is `true`). |

## Notes

- See `CRAWLING_METHOD.md` for the full technical writeup, including why the domain most people would guess (`oarg.gov.sl/`, `oarg.gov.sl/business-register/`) currently returns a fatal WordPress error, and the exact working search endpoint this actor targets instead.
