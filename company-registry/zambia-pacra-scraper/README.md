# Zambia PACRA Business Registry Scraper

Search Zambia's official company and business-name registry — PACRA (Patents and Companies Registration Agency) — by registered business name. No account, login, or API key needed.

## Why use this actor

- Direct access to Zambia's official government business registry, the same data source banks, lawyers, and due-diligence teams use to verify a Zambian company
- Returns registration number, legal status (active/inactive), incorporation date, business type, industry classification, and full compliance standing (annual returns, share capital, beneficial ownership disclosure) — not just a "yes this name exists" check
- Search multiple company names in a single run
- No login, no CAPTCHA, no paid certificate purchase required — this actor only uses PACRA's free public search

## What this actor does NOT do

- **Search by registration number.** Despite PACRA's own search box inviting it, registration-number search does not actually work on the live site (verified with several real numbers) — only name search works. See `CRAWLING_METHOD.md` for details.
- **Return director/shareholder names or a full company certificate.** That level of detail requires a paid certificate purchase through PACRA's separate account-gated portal, which is out of scope for this actor.

## How it works

1. Give the actor one or more company/business names to search for.
2. The actor queries PACRA's public registry search for each name.
3. Every matching entity is returned as its own dataset row, with registration details and compliance status.
4. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "companyNames": ["Zambia Sugar Plc", "MTN Mobile Money"],
  "maxConcurrency": 4,
  "proxyConfiguration": { "useApifyProxy": false }
}
```

| Field | Type | Description |
|---|---|---|
| `companyName` | string | A single business name (or part of one) to search for. |
| `companyNames` | array | Multiple business names to search for in one run. |
| `maxConcurrency` | integer | How many search queries to run in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Off by default — this target has no anti-bot protection, so a direct connection works reliably. |

At least one of `companyName` / `companyNames` is required. Each query returns up to 50 matching entities (a server-side cap on PACRA's end — use a more specific name if you hit it).

## Output

One record per matching entity (`isicDescription` truncated here for readability):

```json
{
  "entityID": "AE3059AB-91CC-47B4-8491-3BB99208E5DE",
  "entityTypeId": 1,
  "entityName": "ZAMBIA SUGAR PLC",
  "entityNumber": "119640002880",
  "registrationDate": "26/03/1964",
  "natureofBusiness": "Manufacture of sugar",
  "parValueStatus": "1",
  "annualReturnStatus": 1,
  "nominalCapitalStatus": 1,
  "entityStatus": "Active",
  "companyType": "Local Company - Public",
  "entityLimit": "Ordinary Company",
  "annualReturnReason": "Annual returns have been prepared and lodged in accordance with section 270 of the Companies Act. The next annual return will be due on 31/08/2026. ",
  "nominalCapitalReason": "The current nominal capital is within the legal limit.",
  "parValueReason": "The share structure is upto date.",
  "isicClasification": "3290. Other manufacturing n.e.c.",
  "isicDescription": "Other manufacturing n.e.c. This class includes... (truncated)",
  "beneficialOwnerStatus": 0,
  "beneficialOwnerReason": "Your company has not complied with the requirement to disclose information on the beneficial ownership of all the shares held by shareholders in your company as per sections 21 and 123 of the Companies Act. ",
  "entityTypeLabel": "Local Company",
  "_input": "Zambia Sugar Plc",
  "_source": "S1-registrysearch-api",
  "_scrapedAt": "2026-08-26T17:24:29.132977Z",
  "_matchCount": 1
}
```

A search with zero matches still produces one row, so you can tell "searched, nothing found" apart from "this query never ran":

```json
{
  "_input": "zzzznonexistentcompanyxyz",
  "_source": "S1-registrysearch-api",
  "_scrapedAt": "2026-08-26T17:23:02.724224Z",
  "_matchCount": 0
}
```

| Field | Description |
|---|---|
| `_input` | The search query you sent, for traceability. |
| `_source` | Which strategy produced this record. |
| `_scrapedAt` | UTC timestamp of when the record was captured. |
| `_matchCount` | How many entities the query matched in total (present on every successful search). |
| `entityName` | The entity's registered business/company name. |
| `entityNumber` | PACRA registration/incorporation number. |
| `entityTypeLabel` | "Local Company", "Business Name", or "Foreign Company" (derived by this actor from PACRA's raw `entityTypeId` code). |
| `entityStatus` | Current registry status — "Active", "Inactive", or "Inactive (Duplicate)". |
| `companyType` | Legal form, e.g. "Local Company - Limited by Shares". |
| `registrationDate` | Registration/incorporation date (`dd/mm/yyyy`, PACRA's own format). |
| `natureofBusiness` / `isicClasification` / `isicDescription` | Business activity and industry classification, when PACRA has it on file. |
| `annualReturnStatus` / `nominalCapitalStatus` / `parValueStatus` / `beneficialOwnerStatus` | Compliance flags, each paired with a `*Reason` field explaining the status in plain language. |

A record with `_error` instead of `_matchCount` means that search could not be completed: `http_<code>` for an unexpected upstream response, `unexpected_shape` if PACRA changed the response format, or `blocked_or_transient` for a network hiccup.

## Data source

Zambia's Patents and Companies Registration Agency (PACRA) public business search, `search.pacra.org.zm`. See `CRAWLING_METHOD.md` for the full reverse-engineering writeup.
