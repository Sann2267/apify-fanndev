# Samoa Government Tenders Scraper (Ministry of Finance)

Scrapes Samoa's Ministry of Finance (MOF) tender pages, `mof.gov.ws`, for
public procurement: currently open tenders with document links, and the
archive of contract award records with winning bidders and amounts. No
account or login needed.

## Why use this actor

- Pulls from the government's real, official tender pages — not a
  third-party tender-alert aggregator
- Two views in one actor: **Current tenders** (open now, ~101 at a time,
  each with direct document links) and **Contract awards** (~40 records,
  with winning bidder(s), contract amounts, and every company that
  competed)
- Direct links to every tender's PDF/DOCX/XLS documents — advertisement,
  bidding document, technical annexes
- No account, no API key, no CAPTCHA to solve
- Stable JSON output, ready for a spreadsheet, database, or alerting
  pipeline

## How it works

1. Pick a list type: `current` for what's open for submission right now,
   or `awards` for the contract-award archive.
2. The actor fetches the matching listing page and returns up to the limit
   you set.
3. Results stream into your dataset, ready to download as JSON, CSV, or
   Excel.

## Input

**Currently open tenders (default):**
```json
{
  "listType": "current",
  "maxResults": 500,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

**Contract award records:**
```json
{
  "listType": "awards",
  "maxResults": 100
}
```

| Field | Type | Description |
|---|---|---|
| `listType` | string | `"current"` (default) — tenders open for submission right now (~101 at a time), each with document links. `"awards"` — contract award records (~40 at a time) with winning bidders and amounts. |
| `maxResults` | integer | Caps how many records are kept in the output. Default 500, max 10,000. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

Real output for `{"listType": "current", "maxResults": 1}`:

```json
{
  "_input": "list:current",
  "_source": "S1-webflow-cms-tender-adverisements",
  "_scrapedAt": "2026-08-27T19:09:03Z",
  "recordType": "CURRENT_TENDER",
  "title": "Procurement of Medical Consumables 2027 - 2029",
  "closingDate": "October 26, 2026 11:00 AM",
  "agency": "Ministry of Health",
  "contactText": "Contact Details: Brenda Sefo brenda.sefo@health.gov.ws | OR Dean Faafetai deanf@health.gov.ws +685 68100 | Portal Link",
  "documents": [
    { "label": "Advertisement / Notice", "url": "https://cdn.prod.website-files.com/.../MOH%20Advert%20Medical%20Consumables%20Tender%202027-2029.pdf" },
    { "label": "Tender Document", "url": "https://cdn.prod.website-files.com/.../MOH%20-%20SBD%20for%20Medical%20Consumables%202027-2029.docx" },
    { "label": "Annex A- Schedule of Requirement", "url": "https://cdn.prod.website-files.com/.../Annex%20A-%20Schedule%20of%20Requirement.xls" },
    { "label": "Annex B- Product Information", "url": "https://cdn.prod.website-files.com/.../Annex%20B-%20Product%20Information.xls" }
  ]
}
```

Real output for `{"listType": "awards", "maxResults": 1}`:

```json
{
  "_input": "list:awards",
  "_source": "S1-webflow-cms-tender-awards",
  "_scrapedAt": "2026-08-27T19:09:11Z",
  "recordType": "TENDER_AWARD",
  "contract": "Capital Works LOT 3 Financial Year 2025/2026",
  "approvalDate": "July 30, 2026",
  "implementingAgency": "Land Transport Authority",
  "winningBiddersText": "Togitogiga Package 1: Ulia Construction Ltd - SAT $1,156,844.40 inclusive of all applicable taxes\nTogitogiga Package 2: Ulia Construction Ltd - SAT $1,167,792.97 inclusive of all applicable taxes",
  "allBiddersText": "Ulia Construction Ltd, OTTs Constructors, R&R Construction Ltd, 3T's Company Ltd, Lee Transport Ltd, Lucky Construction, T&N Toleafoa and Company Ltd, and A&A Engineering Construction"
}
```

| Field | Description |
|---|---|
| `_input` | Which list this record came from: `"list:current"` or `"list:awards"`. |
| `_source` | Which part of the site the record came from. |
| `_scrapedAt` | UTC timestamp. |
| `_error` / `_errorDetail` | Present only on a failed run. |
| `recordType` | `CURRENT_TENDER` or `TENDER_AWARD`. |
| `title` / `closingDate` / `agency` | What is being procured, the bid deadline, and the procuring agency (`current` only). |
| `contactText` | Contact name(s), email(s), phone, and portal link, combined as upstream published them (`current` only). |
| `documents` | Direct links to the tender's PDF/DOCX/XLS documents, each `{label, url}` (`current` only). |
| `contract` / `implementingAgency` / `approvalDate` | The awarded contract's name, implementing agency, and approval date (`awards` only). |
| `winningBiddersText` / `allBiddersText` | Free text — winning bidder(s) with contract amounts (sometimes multiple lines for multi-lot contracts), and every company that competed (`awards` only). |

## Notes

- Every field is passed through exactly as published by the Ministry of
  Finance — no reformatting, no translation, no fabricated data.
- `winningBiddersText`/`allBiddersText` are kept as free text rather than
  split into structured amount/currency fields — the upstream formatting
  varies per contract (single-lot vs. multi-lot, inconsistent spacing
  around amounts) enough that a rigid parse would misrepresent some
  records; the raw text is reported as-is.
- See `CRAWLING_METHOD.md` for the full technical writeup.
