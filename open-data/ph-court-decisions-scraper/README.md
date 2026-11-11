# Philippine Supreme Court Decisions Scraper

Search and export **Philippine Supreme Court decisions** from the Judiciary's
own free archive — the [Supreme Court E-Library](https://elibrary.judiciary.gov.ph).
No account, no API key, no login.

You get the case number, the parties, the deciding division, the ponente, the
promulgation date, the Philippine Reports citation and the **complete opinion
text** — as the Court itself prints them.

## What you can do

| Mode | Use it for |
|---|---|
| **Full-text search** | Every decision mentioning a doctrine, statute, party or phrase — `malversation`, `probable cause`, `syndicated estafa`. Powered by the E-Library's own dtSearch engine, with keyword-in-context snippets and per-document hit counts. |
| **Browse by year** | Bulk-harvest the archive month by month for a year range (monthly listings run **1996 to present**). |
| **Full decision (by ID)** | Pull the complete text of specific decisions you already have IDs for. |

Search reaches further back than browse — a 1991 decision was returned from
the decisions index during testing.

## Example input

Find recent decisions on a doctrine, with full opinions:

```json
{
  "mode": "search",
  "searchPhrase": "probable cause",
  "searchCorpus": "sc_decision",
  "searchType": "phrase",
  "maxResults": 50,
  "fetchFullText": true
}
```

Bulk-harvest a year:

```json
{ "mode": "browse", "fromYear": 2025, "toYear": 2026, "maxResults": 500 }
```

Fetch specific decisions:

```json
{ "mode": "decision", "docIds": ["70008", "69244", "70515"] }
```

## Example output

```json
{
  "_source": "S1-decision",
  "docId": "69244",
  "caseNumber": "G.R. No. 235790",
  "caseTitle": "PEOPLE OF THE PHILIPPINES, PLAINTIFF-APPELLEE, VS. MONICO D. SANTOS AND FRANCIS H. CANOZA, ACCUSED, MONICO D. SANTOS, ACCUSED-APPELLANT.",
  "documentType": "DECISION",
  "division": "SECOND DIVISION",
  "ponente": "LEONEN, SAJ.",
  "reporterCitation": "930 Phil. 215",
  "decisionDate": "2022-09-21",
  "decisionDateText": "September 21, 2022",
  "fullTextLength": 41129,
  "fullText": "930 Phil. 215 SECOND DIVISION [ G.R. No. 235790, September 21, 2022 ] …",
  "documentUrl": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/69244"
}
```

Set `fetchFullText: false` (the default) in search/browse mode for fast,
cheap summary rows without the opinion text.

## Good to know

- **Three of the portal's eight search corpora are broken on the
  judiciary's own servers** — `sc_resolution`, `administrative_matter` and
  `bar_matter` answer with dtSearch's `Unable to access index` error. The
  actor reports that as an explicit `search_index_unavailable` record instead
  of pretending there were no matches. `sc_decision` (the default) and
  `sc_all` work fine.
- **dtSearch stops counting at 5,000 matches** per query, so very broad
  searches report 5,000 as the total. Narrow the phrase or use `browse` for
  exhaustive coverage.
- **Search results and portal pages use different document IDs.** A search
  row carries `dtSearchDocId` (the engine's numbering) and links to the
  engine's document view; `docId` (the portal's numbering, usable with
  `mode: "decision"`) appears on browse and decision records. They are not
  interchangeable.
- Decisions not yet published in Philippine Reports have no
  `reporterCitation` / `reporterPdfUrl` — that is expected, not an error.
- Full opinions are long: 20,000–40,000 characters is typical, but en banc
  and consolidated cases run far bigger — one was measured at **2,379,838
  characters (2.4 MB)** in a single record. Budget accordingly when
  `fetchFullText` is on.

## Reliability

- **HTTP-only.** No browser, no login, no credentials. The site runs no WAF
  and imposes no rate limit; `maxConcurrency` still defaults to a polite 4.
- **Never fails silently.** Unknown document IDs soft-404 with HTTP 200 on
  this portal; the actor detects that and returns `_error: "decision_not_found"`
  rather than an empty-looking record. Every failure mode emits a row.
- **Raw passthrough.** Values are the portal's own — nothing renamed into a
  different taxonomy, nothing re-derived.

## Data source & limits

Data comes from the Supreme Court E-Library, the Philippine Judiciary's
official public archive of its decisions. The site publishes no `robots.txt`
policy (it 404s) and requires no authentication. Court decisions are public
records. You are responsible for how you use the output.
