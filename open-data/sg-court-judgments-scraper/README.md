# Singapore Court Judgments Scraper

Search Singapore's official free court-judgment archive by keyword or year and export complete written judgments — citation, court, presiding judge, legal topic tags and the full opinion text. Coverage reaches back to 1965. No account, login, or API key needed.

## Why use this actor

- Search the entire public archive of Singapore court judgments by any phrase — a legal concept, a party name, or a citation
- Covers every level in one place: Court of Appeal, Appellate Division, General Division of the High Court, Singapore International Commercial Court, Family Court, District and Magistrates' Courts
- Returns the court's own catchwords (its official legal-topic tags), so you can filter by subject matter without classifying anything yourself
- Optional full text pulls the complete written judgment — often over 100,000 characters of primary legal material, ideal for research, litigation analytics, or building a searchable legal corpus
- No account, login, or API key required
- Stable JSON output, ready for spreadsheets, databases, or research pipelines

## How it works

Pick a `mode`:
1. **`search`** — search or browse judgments by phrase, year and sort order, paginated automatically.
2. **`judgment`** — fetch the full text of specific judgment ID(s) you already have.

## Input

**Search, lightweight (summary row per judgment):**
```json
{
  "mode": "search",
  "searchPhrase": "negligence",
  "year": "All",
  "sortBy": "DateOfDecision",
  "sortAscending": false,
  "maxResults": 50,
  "fetchFullText": false
}
```

**Search, with the complete written judgments:**
```json
{
  "mode": "search",
  "searchPhrase": "breach of contract",
  "year": "All",
  "sortBy": "DateOfDecision",
  "maxResults": 25,
  "fetchFullText": true
}
```

**Full judgment, by ID:**
```json
{
  "mode": "judgment",
  "judgmentIds": ["2026_SGHC_175", "2026_SGHCA_22"]
}
```

| Field | Type | Description |
|---|---|---|
| `mode` | string | `"search"` (default) or `"judgment"`. |
| `searchPhrase` | string | `search` mode — free-text search, e.g. `"negligence"`, `"minority oppression"`, a party name, or a citation. Leave empty to browse everything newest-first. |
| `year` | string | `search` mode — a single year of decision (e.g. `"2025"`), or `"All"` for the whole archive back to 1965. Default `"All"`. |
| `sortBy` | string | `search` mode — `"DateOfDecision"` (default) or `"Title"`. |
| `sortAscending` | boolean | `search` mode — `false` (default) puts the most recent judgments first; `true` starts from the oldest. |
| `maxResults` | integer | `search` mode — max judgments to return, paginated automatically (10 per page). Default 50. |
| `fetchFullText` | boolean | `search` mode — when `true`, each result also gets the complete written judgment plus court/judge/hearing detail. When `false` (default), only the summary row — much faster for large result sets. |
| `judgmentIds` | array | `judgment` mode — IDs in the archive's own `"<year>_<court>_<number>"` format, e.g. `"2026_SGHC_175"`. These appear as `judgmentId` on every search result. |
| `maxConcurrency` | integer | How many judgments to fetch in parallel. Default 4. |
| `proxyConfiguration` | object | Apify Proxy settings. Residential is on by default. |

## Output

**Search mode, `fetchFullText: false`** — one lightweight row per judgment (real captured output):
```json
{
  "_input": "q=negligence|year=All|sort=DateOfDecision",
  "_source": "S1-listing",
  "_scrapedAt": "2026-08-31T01:44:40Z",
  "judgmentId": "2026_SGHCR_36",
  "caseTitle": "LAO IOK SIM @LIU YUCHAN v UNITED OVERSEAS BANK LIMITED",
  "citation": "[2026] SGHCR 36",
  "decisionDate": "2026-08-18",
  "decisionDateText": "18 Aug 2026",
  "caseNumber": "HC/OC 271/2026 ( HC/SUM 1725/2026 )",
  "catchwords": [
    "Civil Procedure — Striking Out",
    "Tort – Negligence – Breach of Duty"
  ],
  "year": 2026,
  "courtCode": "SGHCR",
  "judgmentUrl": "https://www.elitigation.sg/gd/s/2026_SGHCR_36"
}
```

**Search mode with `fetchFullText: true`, or `judgment` mode** — the complete judgment (real captured output, `fullText` truncated here for display):
```json
{
  "_input": "q=breach of contract|year=All|sort=DateOfDecision",
  "_source": "S2-judgment",
  "_scrapedAt": "2026-08-31T01:52:17Z",
  "judgmentId": "2026_SGHC_175",
  "caseTitle": "Reformd Pte Ltd v Kopigi Pte Ltd",
  "citation": "[2026] SGHC 175",
  "decisionDate": "2026-08-28",
  "decisionDateText": "28 Aug 2026",
  "caseNumber": "Originating Claim No 483 of 2024",
  "catchwords": [
    "Contract — Discharge — Breach",
    "Contract — Termination",
    "Contract — Damages — Nominal Damages"
  ],
  "year": 2026,
  "courtCode": "SGHC",
  "judgmentUrl": "https://www.elitigation.sg/gd/s/2026_SGHC_175",
  "courtName": "In the GENERAL DIVISION OF THE high court of the republic of singapore",
  "coram": "General Division of the High Court — Originating Claim No 483 of 2024 S Mohan J 3–5, 11–12 February, 10 April 2026",
  "judgeAuthor": "S Mohan J:",
  "fullText": "In the GENERAL DIVISION OF THE high court of the republic of singapore [2026] SGHC 175 Originating Claim No 483 of 2024 Between Reformd Pte Ltd … Claiman t And Kopigi Pte Ltd … Def endant Counterclaim Between Kopigi Pte Ltd … Claimant in Counterclaim And Reformd Pte Ltd … Defendant in Counterclaim J ...",
  "fullTextLength": 108618
}
```

| Field | Type | Description |
|---|---|---|
| `judgmentId` | string | The archive's own ID, `"<year>_<court>_<number>"`. Feed it back in `judgment` mode. |
| `caseTitle` | string | The parties, as displayed. |
| `citation` | string | Official neutral citation, e.g. `"[2026] SGHC 175"`. |
| `decisionDate` | string | Decision date as `YYYY-MM-DD`. |
| `decisionDateText` | string | The same date in the archive's display format, e.g. `"28 Aug 2026"`. |
| `caseNumber` | string | The court's own case reference. |
| `catchwords` | array | The court's official legal-topic tags for the judgment. |
| `year` / `courtCode` | number / string | Decision year and court abbreviation (`SGHC`, `SGHCA`, `SGCA`, `SGHCI`, `SGFC`, `SGDC`, `SGMC`, …). |
| `judgmentUrl` | string | Direct link to the full written judgment. |
| `courtName` | string | Full-judgment records only — the court as printed in the judgment header. |
| `coram` | string | Full-judgment records only — court, case number, judge(s) and hearing dates. |
| `judgeAuthor` | string | Full-judgment records only — the judge who delivered the judgment. |
| `fullText` | string | Full-judgment records only — the complete written judgment as plain text. |
| `fullTextLength` | number | Full-judgment records only — character count, handy for filtering out short procedural decisions. |

A record with `_error` instead of data means that lookup couldn't complete
— `"_error": "no_results"` (nothing matched the search) or
`"_error": "judgment_not_found"` (unknown judgment ID). A record with
`"_warning": "full_text_unavailable"` means the summary row is real but
that one judgment's full-text fetch failed; the run still continues.

## Notes / limits

- Judgments span **1965 to the present**, across roughly 15,900 decisions.
- The archive doesn't publish a total match count, so `maxResults` caps how
  many judgments are paged through rather than slicing a known total.
- Full judgments are long — a single commercial decision can exceed 170,000
  characters. Turn `fetchFullText` off when you only need to build a case
  list, and on when you need the reasoning itself.
- A few fields are genuinely absent on some older judgments (for example,
  the authoring judge is not printed on some 1960s decisions). Those come
  back empty rather than guessed.
