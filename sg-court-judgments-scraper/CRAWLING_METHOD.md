# Crawling Method — sg-court-judgments-scraper

**Target:** [elitigation.sg/gd](https://www.elitigation.sg/gd/) — the
Singapore Judiciary's official **Grounds of Decision (GD)** portal: the
free, public, full-text archive of Singapore court judgments.

## WAF / anti-bot: none

- **`robots.txt` returns 404** (IIS "File or directory not found") — the
  site declares no crawler policy at all, so there is no AI-bot directive
  to honour or violate. (Checked explicitly because Babak 36 found several
  US targets blocking `ClaudeBot`/`ApifyBot` by name.)
- `curl_cffi` `chrome124` gets clean `200`s on the listing and on every
  judgment page. Zero Cloudflare/DataDome/PerimeterX/Akamai/Kasada markers
  in headers, cookies, or body.
- **No rate limiting observed**: 5 rapid sequential listing requests all
  returned 200 in **0.10–0.32 s** each. No cookie gate, no login, no
  session bootstrap needed.
- Plain **ASP.NET MVC**, and notably **no `__VIEWSTATE`** — pagination is
  ordinary GET query params, so no form-token replay is required.

## Endpoints

1. **Listing** — `GET /gd/Home/Index?Filter=SUPCT&YearOfDecision=<year|All>&SortBy=<DateOfDecision|Title>&CurrentPage=<n>&SortAscending=<bool>&PageSize=0&Verbose=False&SearchQueryTime=0&SearchTotalHits=0&SearchMode=True&SpanMultiplePages=False`
   plus optional `SearchPhrase=<free text>`.
   - **All of those keys are required** even when unused; the app echoes
     them back into its own pagination links.
   - **10 results per page**, paginated purely by `CurrentPage`.
   - Each result is a `div.card` carrying: `a.gd-cw` (catchwords),
     `a.gd-heardertext` (case title + `/gd/s/<id>` link),
     `a.citation-num-link` (neutral citation, printed with a trailing
     layout pipe that must be stripped), `a.decision-date-link`, and
     `a.case-num-link`.
   - **Decision date is only machine-readable inside the filter link's own
     data attribute** — `data-searchparam='DecisionDate:"2026-08-28"'`.
     The visible text is the human format ("28 Aug 2026"). Both are
     emitted (`decisionDate` / `decisionDateText`).
   - A query matching nothing renders zero cards — a real "no results"
     signal. A page missing `form#gdlistForm` entirely is treated as a
     shape change (`UnexpectedShape`), not a no-match.

2. **Judgment** — `GET /gd/s/<judgmentId>` (e.g. `/gd/s/2026_SGHC_175`).
   Full opinion inside `#divJudgement`.
   - An **unknown/invalid id soft-404s**: HTTP **200** with a ~3.7 KB body
     and **no `#divJudgement`**. Absence of that element is the only
     reliable not-found signal; there is no real 404.

## Coverage (verified live)

- **1,594 listing pages × 10 ≈ 15,900 judgments.**
- Page 1594 returns `/gd/s/1965_SGHC_6` — the archive genuinely reaches
  back to **1965**, and that 61-year-old judgment extracts cleanly.
- Despite the filter value being named `SUPCT`, the listing carries the
  whole corpus. Remote verification returned **SGHC** (General Division),
  **SGHCA** (Appellate Division), **SGHCI** (International Commercial
  Court), **SGFC** (Family Court) and **SGDC** (District Court) judgments
  from a single query. Other filter guesses (`STATECT`, `FAMCT`, `ALL`)
  all render **0 cards**, so the filter is fixed in `constants.py` rather
  than exposed as an input.

## Shape variations between courts (the substance of this build)

Local testing — not assumption — surfaced three genuine upstream
variations. All three initially produced silently wrong output:

1. **`catchwords` live in different elements on the two page types.**
   The listing tags them `a.gd-cw`; the judgment page uses a lowercase
   `.catchwords` class (**not** `.Catchwords`/`.HN-Catchwords`, which is
   what an initial guess tried and which silently returned `[]`). And they
   arrive in **three different bracket styles**:
   - `[Contract — Discharge — Breach]` — whole line bracketed (SGHC, SGHC(I))
   - `[Civil Procedure] — [Enforcement] — [Whether …]` — each segment bracketed (SGDC)
   - `Betting, Gaming and Lotteries — Betting` — no brackets at all (1965 SGHC)
   Normalised by stripping brackets and collapsing whitespace, which
   yields the same topic string across all three without altering wording.

2. **District/Magistrates' Court judgments have no `.HN-NeutralCit`.**
   They emit **two `.CaseNumber` nodes** instead — the citation in one
   (`[2026] SGDC 273`), the real case number in the other. Resolved by
   pattern-matching the citation format across those nodes. Nothing is
   synthesised when neither is present.

3. **`.title` is reused for boilerplate.** DC judgments open with a
   redaction-instruction template in the *same class* as the court name,
   so `css_first('.title')` returned **"Please delete where applicable –"**
   as `courtName`. Fixed by selecting the `.title` node that actually
   names a court.

Additionally, the enrichment merge originally used `{**row, **detail}`,
which let the judgment page's **empty** catchword list clobber the good
listing values. `merge_listing_and_judgment()` now only overwrites where
the detail page actually carries a value — the two pages genuinely carry
different subsets.

## Parsing

`selectolax` — judgment pages are large (one commercial judgment measured
**371 KB HTML / 178,532 characters of text**), so a fast parser matters
here more than on a typical listing site. Full text is whitespace-
normalised (`\xa0` → space, runs of spaces collapsed) and otherwise left
exactly as the court published it.

## TLS profile

`chrome124` — arbitrary but consistent; the site has no fingerprint-based
gating to react to. Not revisited unless behaviour changes.

## Known limits

- The listing exposes **no total-hit count**, so `maxResults` is a cap on
  what is actually paged through, not a slice of a known total.
- `judgeAuthor` is absent on some older judgments (e.g. 1965) — the field
  simply isn't printed, so it is emitted as `null` rather than guessed.
- Full text is plain text only; the portal's inline paragraph numbering is
  preserved as it appears in the text, but footnote markup is not
  separately structured.

## Store category & monetisation

Category: `BUSINESS` + `OTHER` (legal-research data; no `LEGAL` category
exists in the live Apify taxonomy).

**Competitive position (verified 2026-08-31):** the "court judgment
scraper" data-type has proven demand — sellers already cover the US
(`parseforge/justia-case-law-scraper` 10u, `crawlerbros` CourtListener,
`parseforge/caselaw-access-scraper`, `jungle_synthesizer` Google Scholar),
**UK** (`nomad-agent` 1u), **India** (`parseforge/india-supreme-court-scraper`
5u, `jungle_synthesizer/india-ecourts-judgments-scraper` 3u), **Ireland**
(`jungle_synthesizer` 3u) and the **CJEU** (`jungle_synthesizer` 5u).
**Singapore had zero actors** across every query tried (`Singapore court
judgment`, `elitigation`, `case law scraper`, `legal judgment scraper`) —
the only developed common-law jurisdiction left uncovered.

Pricing: pay-per-event, tiered on `apify-default-dataset-item`, at the
same $0.005 → $0.0035 band used by `h1bdata-scraper` and comparable to the
jurisdiction actors above. Justified by record value (a full judgment row
can carry 100k+ characters of primary legal text) against near-zero
operating cost (no proxy pressure, ~0.1–0.3 s/request, no WAF retries).
