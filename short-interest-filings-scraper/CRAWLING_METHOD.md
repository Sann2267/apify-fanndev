# Crawling method - Nasdaq / FINRA / SEC

Recon date: **2026-09-18**, plain HTTP, no proxy, no key, no login.

## Surfaces

| Source | URL | Result |
|---|---|---|
| Nasdaq short interest | `api.nasdaq.com/api/quote/{sym}/short-interest?assetClass=stocks` | 200 JSON, 24 settlement rows for Nasdaq-listed symbols |
| Nasdaq symbol info | `api.nasdaq.com/api/quote/{sym}/info?assetclass=stocks` | 200 JSON, carries `exchange` + `isNasdaqListed` |
| FINRA daily short volume | `cdn.finra.org/equity/regsho/daily/{VENUE}shvol{YYYYMMDD}.txt` | 200, 516-546 KB, ~12,300 rows, pipe-delimited |
| SEC submissions | `data.sec.gov/submissions/CIK{10-digit}.json` | 200, 1,000 recent filings + entity profile |
| SEC full-text search | `efts.sec.gov/LATEST/search-index?q=...&forms=...&startdt=&enddt=&from=` | 200 JSON, 100 hits/page |
| SEC ticker map | `www.sec.gov/files/company_tickers.json` | 200, 10,422 ticker -> CIK entries |

Five FINRA venue files verified live the same day: CNMS (consolidated, 12,282
rows), FNSQ (12,244), FNQC (5,435), FNYX (7,542), FORF (2,979).

**No WAF on any of the three.** No challenge, no cookie gate, no captcha.

## Gotchas found (and handled in code)

1. **Nasdaq rejects a custom User-Agent.** Setting `User-Agent: ApifyActor/1.0`
   killed the connection with `curl (92) HTTP/2 stream reset by server` - the UA
   no longer matched the impersonated TLS fingerprint. Nasdaq gets the browser
   UA; SEC gets a contact UA (which SEC's fair-access policy asks for). The
   header policy is therefore **per host**, not global.
2. **Nasdaq encodes failure inside a 200.** An unknown ticker returns HTTP 200
   with `status.rCode = 400` and `bCodeMessage[0].errorMessage = "Symbol not
   exists."`. Reading the HTTP status alone would treat that as success.
3. **Nasdaq publishes short interest only for Nasdaq listings.** GME, AMC, F, T
   and SPY all return `data: null` plus
   `"Short interest is not available. Short interest is only supported for
   Nasdaq Listed stocks"`. TSLA, AAPL, NVDA, QQQ return 24 rows. This is a
   source limit, not a block, and is surfaced as a `not_published` row that
   names the exchange and points at the `short-volume` mode.
4. **`assetClass` is not validated for stocks.** `TSLA&assetClass=etf` still
   returns the stock's 24 rows, while `SPY&assetClass=etf` returns nothing
   because SPY is NYSE Arca. The parameter is passed through but never trusted
   as a filter.
5. **FINRA answers 403 for a file that does not exist yet.** 2026-09-16 = 200 /
   544 KB, 2026-09-17 and -18 = `403 AccessDenied` (S3 XML). 403 therefore means
   "not published", and retrying it as a block would waste four requests per
   missing day. The Actor walks back up to 8 days to find the newest file.
6. **FINRA volumes are fractional** (`403792.045672`). Real, from fractional and
   odd-lot executions - not a parsing artefact, so they are kept as floats.
7. **EDGAR full-text returned a one-off 500** during recon and 200 on every
   retry with the same URL. Treated as transient (retried), not as a signature.
8. **EDGAR caps result sets at 10,000** and pages at 100 via `from`. Both caps
   are the API's; `totalMatches` on each row exposes the real match count.
9. **Date formats differ per source** - Nasdaq `MM/DD/YYYY`, FINRA `YYYYMMDD`,
   SEC `YYYY-MM-DD`. All normalised to ISO, since the point of one Actor is that
   the three join.

## Verified numbers (2026-09-18)

| Check | Result |
|---|---|
| TSLA short interest | 24 rows, latest settlement 2026-08-31, 74,230,933 shares, 2.04 days to cover |
| FINRA newest file | 2026-09-16, 12,282 symbols (consolidated) |
| AAPL submissions | 1,000 recent filings, latest 2026-09-10 (Form 4) |
| EDGAR `"short interest"` in 8-K | 4,946 matching documents |
| SEC ticker map | 10,422 tickers |

## Not implemented (deliberately)

- **XBRL company facts** (`data.sec.gov/api/xbrl/...`) - a fundamentals product,
  a different buyer, and a much larger schema. Out of scope for this release.
- **Filing document text** - this Actor returns filing metadata and direct URLs;
  downloading and parsing document bodies is a separate concern.
- **FINRA monthly / OTC files** - `regsho/monthly/` and `ORFshvol` paths both
  returned 403 on the patterns tried; the daily venue files cover the need.
