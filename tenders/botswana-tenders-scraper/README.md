# Botswana Government Tenders Scraper (Ministry Websites)

Pull public government tender and procurement notices published directly by Botswana ministries. Since Botswana decentralized public procurement in 2022, individual ministries now publish tenders on their own websites instead of (or alongside) the central PPRA portal. No account, login, or API key needed.

## Why use this actor

- No account or login needed — every notice covered here is published in plain public HTML
- Covers the Ministry of Finance's procurement notices (tenders, addenda, expressions of interest, adjudication decisions) and the Ministry of Health's open tenders
- Direct links to the actual tender-document PDFs, extracted from each page
- Stable JSON output suitable for pipelines, spreadsheets, or market-intelligence workflows

## How it works

1. Choose which ministry to pull from: `all` (default), `finance`, or `health`.
2. For the Ministry of Finance, the actor reads the ministry's own RSS feed for its Procurement category. For the Ministry of Health, it parses the tenders table on the ministry's static tenders page.
3. Results stream into your dataset, ready to download as JSON, CSV, or Excel.

## Input

```json
{
  "ministry": "all",
  "maxResultsPerMinistry": 100,
  "proxyConfiguration": { "useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"] }
}
```

| Field | Type | Description |
|---|---|---|
| `ministry` | string | `all` (default) = both ministries. `finance` = Ministry of Finance only. `health` = Ministry of Health only. |
| `maxResultsPerMinistry` | integer | Maximum records returned per ministry. Default 100, max 500. Both sources currently carry fewer than 10 records total — this is a safety cap for future growth, not a real-world limit today. |
| `proxyConfiguration` | object | Apify Proxy settings. Neither site has any anti-bot gate, so this is mostly a formality — residential is offered for consistency with other actors in this collection. |

## Output

One record per tender/notice. This is real output captured from a live run (27 Aug 2026).

**`ministry: "finance"`** — the most recent Ministry of Finance procurement notice:

```json
{
  "_ministry": "finance",
  "_source": "S1-mof-procurement-rss",
  "_scrapedAt": "2026-08-27T05:40:07Z",
  "title": "MINISTRY OF FINANCE ADJUDICATION DECISIONS",
  "article_url": "https://www.finance.gov.bw/index.php?option=com_content&view=article&id=619&catid=38&Itemid=246",
  "category": "Procurement",
  "pub_date": "Thu, 03 Oct 2024 23:08:44 +0200",
  "published_date": "2024-10-03T21:08:44Z",
  "pdf_url": "https://www.finance.gov.bw/images/MINISTRY-OF-FINANCE-ADJUDICATION-_DECISIONS.pdf",
  "attachment_title": "MINISTRY OF FINANCE ADJUDICATION DECISIONS"
}
```

**`ministry: "health"`** — the Ministry of Health's tender listing (currently a single entry — see Notes/limits):

```json
{
  "_ministry": "health",
  "_source": "S2-moh-tenders-table",
  "_scrapedAt": "2026-08-27T05:40:09Z",
  "tender_ref": "MTC\\MOHW\\CLS\\SER/10511/0707/2017",
  "title": "A Framework Services Contract for the Provision of EvaluationServices for Applications for Registration of Medicines",
  "pdf_url": "https://www.moh.gov.bw/Publications/tenders/DRU Tender Notice 2017.pdf",
  "closing_date": "31 August 2017",
  "adjudication_decisions_url": "http://www.ppadb.co.bw/health_13.html"
}
```

| Field | Description |
|---|---|
| `title` | The tender/notice title (both ministries). |
| `article_url` | The Ministry of Finance article page wrapping this notice (carries no text beyond the PDF link already in `pdf_url`). |
| `category` | Upstream's own RSS category tag — always "Procurement" (Ministry of Finance). |
| `pub_date` / `published_date` | Raw RFC-822 publish date and its UTC ISO 8601 equivalent (Ministry of Finance). |
| `pdf_url` | Direct link to the tender/notice PDF document (both ministries). |
| `attachment_title` | Link text of the embedded PDF anchor (Ministry of Finance). |
| `tender_ref` | The ministry's own tender reference code (Ministry of Health). |
| `closing_date` | Bid submission closing date as free text, e.g. "31 August 2017" (Ministry of Health — upstream provides no machine-readable date). |
| `adjudication_decisions_url` | A reference link to "Tender Adjudication Decisions" on `ppadb.co.bw` — passed through as raw data, **not fetched** by this actor (see Notes/limits). |
| `_error` / `_errorDetail` | Present instead of tender fields when a fetch failed: `blocked_or_transient`. |

## Notes / limits

- **Ministry of Finance data is real but not frequently updated.** As of this recon (27 Aug 2026), the newest notice in the feed is dated 3 Oct 2024 — a roughly 22-month gap. The site itself is not abandoned (other sections carry 2026-dated content), so this actor will pick up new procurement notices as soon as the ministry publishes them; a quiet feed reflects upstream's own posting cadence, not a scraping gap.
- **Ministry of Health data is thin.** The tenders page currently lists exactly one tender, dated 2017. The parser reads the page's table generically (not hardcoded to today's single row), so it will surface additional rows automatically if the ministry adds new ones.
- **`adjudication_decisions_url` points to `ppadb.co.bw`, which this actor does not fetch.** That domain was found unreachable (connection timeouts) during recon — the same domain family as Botswana's central PPRA tender portal, which is known to be down/gated. The URL is still included as raw reference data from the page.
- **Other ministries were investigated and are not covered.** The central `gov.bw/tenders` portal is live and public but currently empty ("There are currently no tenders available.") with no listing markup to build a reliable parser against. Several other ministry domains (Agriculture, Trade, Education, Local Government, Infrastructure, Minerals) either no longer resolve or timed out — likely decommissioned in favor of the unified `gov.bw` portal. See `CRAWLING_METHOD.md` for the full list of what was checked.
