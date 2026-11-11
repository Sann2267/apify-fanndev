# Bahamas RGD Company Registry Scraper

Search the Bahamas' official company/business registry — run by the Registrar General's Department (RGD) — by name, and get back the top matching entity names and their internal registry IDs.

## Why use this actor

- No account, login, or CAPTCHA needed — this uses the RGD's own free public "Company Search" preview
- Search by company/business name (partial names work)
- Optionally search former/historical names instead of current ones
- Stable JSON output suitable for existence checks, spot-checking spelling/name conflicts, or as a first step before a paid lookup
- Automatic retries on temporary network hiccups

## Important limits (read this first)

This is the **free preview tier** of the Bahamas registry, and it is deliberately thin:

- **Only the top 3 best-matching names are returned per query.** The RGD's free tool is a "name preview," not a full browsable registry — it exists to help you identify which entity to pay for, not to hand over the full result set. There is no working pagination to get more than 3.
- **Only the company's name and internal ID are reliably populated.** Registration number, status, entity type, directors, shareholders, and share capital are all part of the RGD's paid **$100 BSD "Company Search Report"** (credit-card, requires a CARS account) — a payment/login flow this actor does not automate (out of scope for this project).
- **Very short or extremely common search terms can fail.** Words like `"Bank"`, `"Ltd"`, or 2-letter prefixes reliably return an error (`result_set_too_broad`) instead of results — this is an upstream backend limitation, not a bug in this actor. Use a real, specific company name or a distinctive fragment of one.

If you need the full official report (registration number, status, directors, share capital, filed documents), use this actor to confirm the entity exists and find its `entityId`, then complete the paid search yourself at [rgd.gov.bs](https://www.rgd.gov.bs/service/company-search).

## Input

```json
{
  "query": "Sandals",
  "queries": ["Baha Mar", "Colina"],
  "includeHistory": false,
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | A single company/business name (or a distinctive name fragment) to search for. |
| `queries` | array | Multiple names to search for in one run. |
| `includeHistory` | boolean | If `true`, searches former/historical company names instead of current ones. Default `false`. |
| `maxConcurrency` | integer | How many searches to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default (no anti-bot gate was actually found on this target). |

## Output

One record per matched entity (up to 3 per query). This is real output captured from a live run:

```json
{
  "_input": "Sandals",
  "_source": "S1-public-entities",
  "_scrapedAt": "2026-08-26T19:29:13Z",
  "entityId": 253874,
  "entityName": "SANDALS INTERTRADE LTD.",
  "entityType": null,
  "entityNumber": null,
  "entityStatus": null,
  "registrationDate": null,
  "legacyMigrationStatus": "NONE",
  "directors": [],
  "shareholders": [],
  "documents": [],
  "...": "(remaining upstream fields, all null on the free tier)"
}
```

And for `includeHistory: true` (query `"Bahamas Hot"`), each hit is a former-name record wrapping the current entity:

```json
{
  "_input": "Bahamas Hot",
  "_source": "S2-public-entities-history",
  "_scrapedAt": "2026-08-26T19:29:23Z",
  "nameHistoryId": 2564,
  "name": "Bahamas Hotel And Restaurnats Employers'Association",
  "entity": {
    "entityId": 1237,
    "entityName": "BAHAMAS HOTEL AND RESTAURNATS EMPLOYERS'ASSOCIATION",
    "...": "(same mostly-null shape as above)"
  }
}
```

| Field | Description |
|---|---|
| `_input` | The query you requested, for traceability. |
| `_source` | `S1-public-entities` (current-name search), `S2-public-entities-history` (former-name search), or `none` for an error record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `entityId` | RGD's internal numeric ID — reference this if you go on to pay for the full Company Search Report. |
| `entityName` | Registered name exactly as on file. |
| `entityType`, `entityNumber`, `entityStatus`, `registrationDate`, directors/shareholders/documents/etc. | Present in the schema (raw-passthrough from upstream) but `null`/empty on every free-tier result seen — part of the paid report, not a gap in this actor. |
| `legacyMigrationStatus` | Upstream internal tag — reliably populated (`"NONE"` on every sample seen). |

A record with `_error` instead of entity fields means the query didn't produce a usable result:
- `"not_found"` — the search matched nothing (real empty result).
- `"result_set_too_broad"` — the query was too short/common for the backend to answer (see Limits above); retry with a more specific name.
- `"blocked_or_transient"` — a temporary network issue.

## Notes / limits

- The free search caps out at 3 results per query and does not support real pagination — this reflects the RGD's own tool, not a limitation of this actor.
- Almost every field beyond name/ID is `null` on the free tier by design (see Limits above) — this is what the RGD itself returns for free, not missing data on this actor's side.
- This actor covers the free public name-search only. The paid $100 BSD Company Search Report (full profile, directors, documents) requires a CARS account and credit-card payment directly on `rgd.gov.bs`, which is outside the scope of this actor (no login/payment automation).
