# Short Interest, Short Volume & SEC Filings Scraper

Three official US market-data sources in one Actor: **Nasdaq** short interest, **FINRA** daily short-sale volume, and **SEC EDGAR** filings with full-text search. Give it tickers or CIKs and get clean, joinable rows - no API key, no account, no registration.

## Why use this actor

- **Three sources, one schema.** Short interest, short volume and filings all come back with normalised dates (`YYYY-MM-DD`) and parsed numbers, so they join on ticker and date without cleanup.
- **Every US symbol covered for short volume.** FINRA's daily file carries ~12,300 symbols; you can pull the whole file or filter it down to your watchlist.
- **The short volume ratio is computed for you** - `shortVolume / totalVolume` on every row, the same definition on every row.
- **Full-text search across all of EDGAR**, not just one company's filings - find every 8-K that mentions a phrase, in a date range.
- **Honest about what each source publishes.** Nasdaq only publishes short interest for Nasdaq-listed stocks; ask for a NYSE ticker and you get an explicit row telling you that and pointing you at the mode that does cover it.
- **Knows when data is not out yet.** FINRA runs 1-2 days behind and skips weekends and holidays; leave the date empty and the Actor finds the newest published file itself.

## How it works

1. Pick a mode and give it tickers (`TSLA`), CIKs (`320193`), a date, or a search phrase.
2. The Actor calls the matching official source and parses its published file or response.
3. Formatted numbers become real numbers, dates become ISO dates, and each row keeps the publisher's original values alongside.
4. Rows land in your dataset, ready for JSON, CSV or Excel export.

You never need an API key, a data vendor account, or your own scheduling for the FINRA file-release lag.

## Input

```json
{
    "mode": "short-interest",
    "symbols": ["TSLA", "AAPL", "NVDA"],
    "includeSymbolInfo": true,
    "maxItems": 500
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `short-interest`, `short-volume`, `filings`, `filing-search`, `company` or `reference`. |
| `symbol` / `symbols` | string / array | Tickers, or CIKs for the SEC modes. In `short-volume` mode this filters the daily file. |
| `date` / `dates` | string / array | Trading days for `short-volume`, `YYYY-MM-DD`. Empty = newest published day. |
| `venue` | string | Which FINRA file: `consolidated` (default), `nasdaq-carteret`, `nasdaq-chicago`, `nyse`, `finra-adf`. |
| `forms` | array | Form filter for `filings` and `filing-search`, e.g. `["8-K"]`. |
| `since` | string | `filings` mode: only filings on or after this date. |
| `query` | string | `filing-search` mode: the full-text query. Quote a phrase for an exact match. |
| `startDate` / `endDate` | string | Date window for `filing-search`. |
| `assetClass` | string | `stocks` (default) or `etf`, for `short-interest`. |
| `includeSymbolInfo` | boolean | Adds company name and exchange to short interest rows. One extra request per ticker. |
| `maxItems` | integer | Row cap for the run. Default `500`. |
| `proxyConfiguration` | object | Optional; not needed. |

### Example inputs

Bi-monthly short interest history for three Nasdaq names:

```json
{ "mode": "short-interest", "symbols": ["TSLA", "AAPL", "NVDA"] }
```

Yesterday's short volume for a watchlist:

```json
{ "mode": "short-volume", "symbols": ["TSLA", "GME", "AMC", "AAPL"] }
```

A whole day of short volume, every symbol:

```json
{ "mode": "short-volume", "date": "2026-09-16", "maxItems": 15000 }
```

Every 8-K Apple filed this year:

```json
{ "mode": "filings", "symbol": "AAPL", "forms": ["8-K"], "since": "2026-01-01" }
```

Every filing that mentions a phrase, across all companies:

```json
{ "mode": "filing-search", "query": "\"reverse stock split\"", "forms": ["8-K"], "startDate": "2026-08-01", "endDate": "2026-09-18" }
```

## Output

### `SHORT_INTEREST` (short-interest mode)

```json
{
    "_input": "TSLA",
    "_source": "S1-nasdaq",
    "recordType": "SHORT_INTEREST",
    "symbol": "TSLA",
    "settlementDate": "2026-08-31",
    "settlementDateRaw": "08/31/2026",
    "shortInterest": 74230933,
    "avgDailyShareVolume": 36423555,
    "daysToCover": 2.037993,
    "companyName": "Tesla, Inc. Common Stock",
    "exchange": "NASDAQ",
    "isNasdaqListed": true
}
```

One row per settlement date; a single ticker returns 24 rows, which is a full year of history.

### `SHORT_VOLUME` (short-volume mode)

```json
{
    "_input": "consolidated:2026-09-16",
    "_source": "S1-finra",
    "recordType": "SHORT_VOLUME",
    "symbol": "TSLA",
    "date": "2026-09-16",
    "venue": "consolidated",
    "shortVolume": 9572952.431456,
    "shortExemptVolume": 1064.0,
    "totalVolume": 16690602.218114,
    "shortVolumeRatio": 0.573553,
    "market": "B,Q,N"
}
```

Fractional volumes are genuine - they come from odd-lot and fractional-share executions, and FINRA publishes them that way.

### `FILING` (filings mode)

```json
{
    "recordType": "FILING",
    "cik": "0000320193",
    "companyName": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "form": "8-K",
    "accessionNumber": "0000320193-26-000018",
    "filingDate": "2026-07-30",
    "reportDate": "2026-07-30",
    "sicDescription": "Electronic Computers",
    "isInlineXBRL": true,
    "filingUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/aapl-20260730.htm",
    "filingIndexUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/0000320193-26-000018-index.htm"
}
```

### `FILING_MATCH` (filing-search mode)

```json
{
    "recordType": "FILING_MATCH",
    "companyDisplayName": "Gossamer Bio, Inc.  (GOSS)  (CIK 0001728117)",
    "cik": "0001728117",
    "form": "8-K",
    "fileDate": "2026-09-09",
    "fileType": "EX-99.1",
    "relevanceScore": 13.785957,
    "totalMatches": 815,
    "documentUrl": "https://www.sec.gov/Archives/edgar/data/1728117/000172811726000064/ex991.htm"
}
```

### `COMPANY` (company mode)

```json
{
    "recordType": "COMPANY",
    "cik": "0000320193",
    "companyName": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "sicDescription": "Electronic Computers",
    "category": "Large accelerated filer",
    "stateOfIncorporation": "CA",
    "fiscalYearEnd": "0927",
    "filingCount": 1000,
    "latestFilingDate": "2026-09-10",
    "latestFilingForm": "4",
    "hasOlderFilingShards": true
}
```

### `SOURCE` (reference mode)

```json
{
    "recordType": "SOURCE",
    "source": "finra-consolidated",
    "isAvailable": true,
    "detail": "latest published file found",
    "sample": { "latestDate": "2026-09-16", "rows": 12282, "sampleSymbol": "A" }
}
```

Run this first when scheduling: it tells you the newest date each source actually has.

### Error rows

```json
{
    "recordType": "ERROR",
    "_input": "GME",
    "_error": "not_published",
    "_errorDetail": "Short interest is not available. Short interest is only supported for Nasdaq Listed stocks (exchange=NYSE). Use mode 'short-volume' for daily FINRA data, which covers every US symbol."
}
```

`_error` is one of `not_found`, `not_published`, `not_in_file`, `empty_response`, `empty_section`, `invalid_symbol`, `invalid_date`, `no_matches`, `shape_changed` or `blocked_or_transient`.

## What you can build with it

- **Short-squeeze screens** - join Nasdaq short interest (the level) with FINRA short volume (the daily flow) on ticker, and rank by days-to-cover and rising short ratio.
- **Daily short-pressure dashboards** - one `short-volume` run per day, whole file, ~12,300 rows.
- **Filing alerts** - schedule `filings` per watchlist ticker with `since` set to yesterday, and get every new 8-K, 10-Q or Form 4.
- **Event scanning across the market** - `filing-search` for phrases like "going concern", "reverse stock split" or "delisting notice" in a date window.
- **Reference data** - `company` mode gives CIK, SIC industry, filer category and exchange for entity resolution.

## Notes & limits

- **Nasdaq publishes short interest only for Nasdaq-listed stocks.** NYSE names return an explicit `not_published` row that names the exchange. Use `short-volume` for full market coverage.
- **Short interest is bi-monthly, not daily.** Two settlement dates per month, published with a regulatory lag.
- **FINRA runs 1-2 days behind** and publishes nothing for weekends or market holidays. A date with no file returns `not_published`, not an error you need to chase.
- **SEC returns the 1,000 most recent filings** per company. When there are older ones, `hasOlderFilingShards` is `true` so you know the history is longer than what you received.
- **EDGAR full-text search covers 2001 onward** and caps any result set at 10,000 documents; the row's `totalMatches` tells you how many matched in total. Narrow with `forms` and a date window to get under the cap.
- **This Actor identifies itself to the SEC** and paces its requests inside SEC's fair-access policy.

## Scheduling tips

- `short-volume` with no date: run daily in the evening UTC - it will pick up the newest published file automatically.
- `short-interest`: twice a month is enough; more often just re-reads the same settlement dates.
- `filings` with `since` = yesterday: run daily per watchlist.
- Start with one `reference` run when you build the schedule, to see each source's current data date.

## Troubleshooting / FAQ

**My NYSE ticker returns no short interest.** That is the publisher's limit, not a failure - Nasdaq only publishes it for its own listings. The `not_published` row says so explicitly. FINRA short volume covers that ticker.

**`not_published` for a recent date.** FINRA has not released that file yet, or it is a weekend or market holiday. Leave `date` empty to always get the newest available one.

**A symbol is missing from the daily file.** Symbols that did not trade that day are not in it; the Actor emits a `not_in_file` row for each one you asked for.

**Why are the volumes fractional?** Because FINRA publishes them that way - fractional-share and odd-lot executions are reported to six decimals.

**Can I get older filings than the 1,000 returned?** Not in this Actor. Check `hasOlderFilingShards` to know whether older history exists.

## Legal & fair use

All three sources are official public disclosures published by Nasdaq, FINRA and the US Securities and Exchange Commission. This Actor reads them as published, without an account and without circumventing any access control, and identifies itself where the publisher asks clients to do so. The output is market data, not investment advice.
