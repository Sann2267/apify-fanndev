# Crawling method — elibrary.judiciary.gov.ph (Philippine Supreme Court E-Library)

Recon log, 2026-09-07. Everything below was confirmed live, not inferred.

## Why this target

Applies the Babak 37 pattern from `ACTOR_MARKET_RESEARCHER_NEW.md`: **take a
data-type already proven to sell, then find a jurisdiction nobody has built
it for.** Court-judgment scrapers exist on the Apify Store for the US
(`parseforge/justia-case-law-scraper`, `crawlerbros` CourtListener,
`parseforge/caselaw-access-scraper`), the UK (`nomad-agent`, `parseforge`,
`jungle_synthesizer` BAILII, `spookyweb`), India (`parseforge`,
`jungle_synthesizer`), Ireland, Japan, the CJEU and China — and Singapore
(this portfolio's own `sg-court-judgments-scraper`).

**The Philippines is empty.** Store queries for `Philippines Supreme Court`,
`Philippines jurisprudence` and `elibrary judiciary` returned *zero* hits;
`Philippines legal` returned only unrelated noise (Lamudi property,
7-Eleven, Shopee).

## Jurisdictions rejected first (recon, not guesses)

The Babak 37 recommendation named Malaysia, Hong Kong and New Zealand. All
three failed the gate before the Philippines was even considered:

| Target | Verdict |
|---|---|
| `legalref.judiciary.hk` (HK Judiciary) | `robots.txt` = **`User-Agent: * / Disallow: /`**. Off limits. |
| `hklii.hk` (HK Legal Information Institute) | `robots.txt` allows all but `/api` — and the site is a pure SPA shell (2,693 bytes, no content). All data comes from the one path that *is* disallowed. Off limits. |
| `nzlii.org` (NZ Legal Information Institute) | Cloudflare content-signal robots.txt with an explicit `User-agent: ClaudeBot / Disallow: /`. Off limits (same posture as Grenada/Nauru in Babak 31/34). |
| `forms.justice.govt.nz` (NZ Judicial Decisions Online) | Connection reset from Indonesia on **all five** TLS profiles (chrome124 / chrome99_android / safari17_0 / edge101 / chrome110) — geo/ISP-level, same signature as Circa Sports in Babak 36. Needs an external prober before it can be judged. |
| `ejudgment.kehakiman.gov.my` (Malaysia) | Redirects to `cms2.kehakiman.gov.my/CommonWeb`, which is a **login-gated ASP.NET Case Management System** (`__VIEWSTATE` + Dynatrace RUM), not a public judgment archive. |
| `putusan3.mahkamahagung.go.id` (Indonesia MA) | ClaudeBot explicitly disallowed. Off limits. |
| `pdki-indonesia.dgip.go.id`, `iponlineext.myipo.gov.my` | `Disallow: /` and ClaudeBot-disallowed respectively. Off limits. |

## Robots posture of the chosen target

- `https://elibrary.judiciary.gov.ph/robots.txt` → **HTTP 404** (IIS "File or
  directory not found"). The site declares **no crawler policy at all** —
  nothing is disallowed, and there is no AI-bot directive to honour or
  violate. Same posture as `elitigation.sg` in Babak 37.
- Separately, the *document* pages carry
  `<meta name="robots" content="noindex,nofollow">`. That is an **indexing**
  directive aimed at search engines, not an access directive: it is present
  on *both* the canonical `showdocs` page and its printer-friendly twin (the
  classic duplicate-content reason), and the site's own dtSearch document
  view serves the identical text with **no** robots meta at all. The corpus
  is the Supreme Court's official public record of its own decisions,
  published expressly for public access. Defaults here stay gentle anyway
  (`maxConcurrency` 4, cap 16).

## Architecture

CodeIgniter/PHP on **Microsoft-IIS**, with a bolted-on **dtSearch** engine
(`dtisapi6.dll`) behind the portal's search iframe. A leaked PHP notice
(`Undefined index: search`, `models/elibmodel.php` line 720) confirmed the
CodeIgniter backend.

**No WAF, no challenge, no login, no cookie gate.** `curl_cffi` `chrome124`
gets clean 200s everywhere. Six rapid sequential document fetches: all 200,
0.27–0.32 s each, no rate-limit response.

**TLS caveat:** the server presents an **incomplete certificate chain** (it
omits the intermediate), so strict verification fails with `unable to get
local issuer certificate` on every profile. `VERIFY_TLS = False` is set for
this host only — read-only fetches of public records, nothing sent upstream.

### Endpoints that matter

| Purpose | Endpoint |
|---|---|
| Monthly listing | `GET /thebookshelf/docmonth/<Mon>/<Year>/<page>` |
| Decision full text | `GET /thebookshelf/showdocs/1/<docId>` |
| Full-text search | `POST /assets/dtSearch/dtSearch_system_files/dtisapi6.dll` |
| Search doc view | `GET …/dtisapi6.dll?cmd=getdoc&DocId=…` |

- **Listing is paginated with no next-page links.** Aug 2025: page 1 = 85
  items, page 2 = 23, page 3 = 0. An empty page is the only stop signal.
  Archive years run **1996 → present** (31 years of monthly links).
- **dtSearch honours `pageSize=100`** (confirmed: 100 result anchors in one
  response) even though the portal's own UI only ever asks for 10 — a 10×
  saving on search paging.
- **Search reaches further back than browse**: the `sc_decision` index
  returned a 1991 decision (`G.R. No. 96025, May 15, 1991`), earlier than the
  monthly listing's 1996 floor.
- Pagination is driven by re-POSTing dtSearch's own hidden `NextPageForm`
  (which carries the engine-resolved index token and the next `startAt`)
  rather than rebuilding the params by hand.

### dtSearch corpora

Index tokens look like `*{81aab6aa66450ae68a1f722f505a17c7} sc_decision`.
The `*{hash}` is a content hash that changes when the judiciary rebuilds an
index, so the client **re-harvests them from the live search form at run
time** and only falls back to the pinned recon-time values (trust-but-verify,
per `.ai/CLAUDE.md` rule 7).

Probed with a query (`contract`) that returns 5,000 hits on `sc_all`:

| Corpus | Result |
|---|---|
| `sc_all` | ✅ 5,000 |
| `sc_decision` | ✅ 5,000 |
| `circular` | ✅ 113 |
| `case_index` | ✅ 38 (but renders no `getdoc` anchors) |
| `manual` | ✅ 36 |
| `sc_resolution` | ❌ `$E 0001 Unable to access index C:\elibrev2\…\sc_resolution` |
| `administrative_matter` | ❌ same |
| `bar_matter` | ❌ same |

Three of the eight corpora the judiciary itself lists are **broken
server-side**. They answer HTTP 200 with "0 result(s)" plus that error
string. Reporting that as "no matches" would be a silent lie, so the
extractor raises `BrokenSearchIndex` and the actor emits an explicit
`search_index_unavailable` record carrying dtSearch's own error text.

## Shape traps found only by running it

1. **The two id spaces are not interchangeable.** dtSearch's `DocId` is its
   own numbering, unrelated to the portal's `showdocs` id. `G.R. No. 241587`
   (6 Aug 2025) is dtSearch `DocId=69244` but portal `showdocs/1/70008`,
   while `showdocs/1/69244` is a completely different case (`G.R. No. 235790`,
   Sep 2022). Search rows therefore carry their own `documentUrl` and never a
   fabricated showdocs link.
2. **The caption separator differs between the two views.** The document page
   prints `[ G.R. No. 279772, June 29, 2026 ]` (comma); a dtSearch hit prints
   `[ G.R. No. 176317. July 23, 2014 ]` (**period**). The first build parsed
   only the comma form and silently emitted
   `caseNumber = "G.R. No. 176317. July 23, 2014"` with a null date. The
   regex now accepts `[,.]` with a greedy prefix so the split lands on the
   last separator actually followed by a date — necessary because case
   numbers are full of their own periods (`G.R. No.`) and administrative
   matters carry nested commas
   (`A.M. No. P-26-390 [Formerly OCA IPI No. 19-4946-P], June 10, 2026`).
3. **An unknown document id soft-404s.** `showdocs/1/999999999` returns
   **HTTP 200** with a "Document Search Error / Document not available on the
   database" body. The first build happily emitted that as a valid decision
   with `fullTextLength=106` and no error — exactly the silent corruption
   `.ai/project/CONSTRAINTS.md` forbids. Now detected explicitly and reported
   as `decision_not_found`.
4. **dtSearch paging re-serves documents.** Page 2 of `negligence` repeated
   two documents from page 1 (`49276`, `53090`) — the engine's relevance
   ordering is not stable between requests. Results are deduped on
   `dtSearchDocId`.
5. **Chrome inside the content container.** The portal page opens with a
   "View printer friendly version" link; the dtSearch document view prefixes
   `← click for PDF copy`; both end with a "Source: Supreme Court E-Library"
   CMS footer. All three are stripped from `fullText`. The PDF link is not
   merely discarded — it points at the **official Philippine Reports PDF**
   and is captured as `reporterPdfUrl`.
6. **`<h3>` glues the document type to the party line**
   (`…RESPONDENT.D E C I S I O N`), and the type is letter-spaced. Split
   apart into `caseTitle` + `documentType`.
7. **The reporter citation is bare text**, not an element, printed above the
   caption (`930 Phil. 215`). It only survives in the container's leading
   text. Absent on decisions not yet reported.

## Variants verified

| Case | Shape |
|---|---|
| `70008` (G.R. No. 241587, 2025) | FIRST DIVISION / `ROSARIO, J.` / DECISION / no reporter cite |
| `69244` (G.R. No. 235790, 2022) | SECOND DIVISION / `LEONEN, SAJ.` / DECISION / `930 Phil. 215` |
| `70515` (A.M. No. P-26-390 …) | **EN BANC** / **`PER CURIAM`** / **RESOLUTION** / nested-bracket docket number |
| dtSearch `63979` (G.R. No. 205698, 2018) | EN BANC / `BERSAMIN, J.` / `837 Phil. 608` / consolidated (12 docket numbers in the title) / **358,578 chars** |
| Jan 1996 listing | 58 items; oldest era parses identically (`322 Phil. 677`) |
| `"probable cause"` phrase search | `SPECIAL THIRD DIVISION` appears as a division variant; largest single opinion measured **2,379,838 chars (2.4 MB)** — well under Apify's 9 MB per-item limit, but the reason `fetchFullText` defaults to off |

## Out of scope (deliberately)

- **Republic Acts** (`/republic_acts/fetch_ra`) — a DataTables endpoint that
  returns **HTTP 500 even with the CodeIgniter `csrf_test_name` token
  harvested from the page** and the cookies in place. Needs more
  reverse-engineering, and it is a different data-type (statutes, not case
  law) that belongs in its own actor.
- **Lawyers list / Roll of Attorneys** (`/lawyers_list/fetch_lawlist`) — a
  GET dumps **6.6 MB** with a PHP notice. Genuinely interesting as a separate
  lead-gen actor; not case law.
- **Justices bios**, **Philippine Reports browse**, `/caseindex` — different
  data-types.
- `/thebookshelf/54` (SC Case Index) returns **HTTP 500** upstream.
