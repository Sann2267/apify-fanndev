# Crawling Method — SINTA Researcher Index Scraper

**Last verified:** 2026-09-08

## Target

`sinta.kemdiktisaintek.go.id` — SINTA (Science and Technology Index), the
Indonesian government's national research portal.

Scale at build time: **335,591 researchers** (33,560 listing pages) and
**5,567 affiliations** (557 pages).

Discovered as Babak 43 candidate #3. The demand evidence is the academic
data-type generally — Google Scholar carries the largest numbers ever
found in this research (38 sellers, 3 serious, 3,132 users;
`marco.gullo/google-scholar-scraper` 1,958u / 522,648 runs) — while SINTA,
Garuda, Lattes, CNKI, CiNii and KCI had **zero actors** across every pass.

The honest caveat recorded in Babak 43 still stands: an Indonesian
researcher is also on Google Scholar, so the gap may reflect redundancy
rather than an untapped market. What is genuinely *not* on Scholar is the
part this actor centres: SINTA's own national scores (Overall / 3Yr /
affiliation) and the three-source metrics table.

## Domain gotcha — the reason this target was nearly written off

The portal used to be `sinta.kemdikbud.go.id`. That host now **fails DNS
resolution** — not a 404, not a timeout, but `Could not resolve host`,
which reads exactly like a dead project. The ministry was split and the
portal moved to `sinta.kemdiktisaintek.go.id` (200, 29 KB home, 88 KB
authors index). Garuda moved the same way.

Rule for this portfolio: a DNS failure on a `.go.id` / `.gov.*` host is a
**rename signal**, not a death certificate. Always look for the successor
domain before scoring a jurisdiction as dead.

## Anti-bot

**None found.** Apache/2.4.58, plain server-rendered HTML, no challenge, no
cookies, no login on any route used here. TLS impersonation and
retry/backoff are kept per portfolio convention (government hosts throttle
unpredictably under load).

## Route map

| Purpose | Route |
|---|---|
| Researcher index | `/authors` (+ `?page=N`, `?q=<text>`) |
| Researcher profile | `/authors/profile/<sintaId>` |
| Affiliation index | `/affiliations` (+ `?page=N`) |
| Affiliation profile | `/affiliations/profile/<affilId>` |

Both indexes render 10 records per page and print their own counters
("Page 1 of 33.560 | Total Records 335.591"), which the client parses and
uses both as the pagination bound and as `_totalRecordsAvailable` on every
emitted record.

## Parameters — one works, one silently does not

| Param | Verdict |
|---|---|
| `page=<n>` | **Works.** Page 2 returns different researchers than page 1. |
| `q=<text>` | **Works.** `q=zainul` narrows 335,591 records / 33,560 pages down to 153 / 16. |
| `sort=<1..5>` | **Silently ignored over GET.** The sort control lives in a `method="POST"` form; requesting `?sort=3` returned an identical first page to the default. Not exposed as an actor input — shipping it would be a knob that quietly does nothing, the same trap this portfolio hit on Blibli and on DJKN's `provinsi`/`kota`. |

## Parsing

Listing rows for **both** indexes share the container `div.list-item`, but
carry different inner blocks, so authors and affiliations have separate
parsers rather than one guessy shared one.

Per researcher card:

| Field | Source |
|---|---|
| Google Scholar ID | `.profile-name span.d-none` (rendered but visually hidden) |
| name + profile URL | `.profile-name a` |
| affiliation / department | `.profile-affil a`, `.profile-dept a` (IDs extracted from the hrefs) |
| SINTA ID | `.profile-id` text, `SINTA ID : <n>` |
| scores | `div.pr-num` / `div.pr-txt` sibling pairs, keyed by the label |
| subjects | `ul.subject-list li` |
| H-indexes | the Metrics table's `div.pr-txt-metric` cells, read in label/`:`/value triples |

**Hidden rows are read anyway.** The Web of Science H-index row carries
`class="d-none"` — hidden in the site's own UI, but a real value sits in
the markup. Dropping hidden rows would silently lose a whole metric, so
they are parsed like any other.

Profile pages add the per-source publication table (`table.stat-table`),
transposed into `"<Source> <Metric>"` keys — `Scopus Article`, `WOS
Citation`, `GScholar H-Index`, and so on.

### Gotcha: Indonesian number formatting

Scores render as `12.748`, `1.610.976`, `3.624.707`. **The dot is a
thousands separator, not a decimal point.** Parsing these with `float()`
would turn a 12,748-point national score into `12.748` — a 1000× error
that looks perfectly plausible in the output and would never raise. Every
numeric field goes through `parse_number`, which strips dots and returns an
int (and only treats a comma as a decimal separator). Verified:
`sintaScoreOverall` for SINTA ID 5980682 is `12748`, matching the site.

## Field coverage (25-card sample, unfiltered index)

| Field | Coverage |
|---|---|
| sintaId, name, affiliation, sintaScoreOverall, scopusHIndex | 25 / 25 |
| subjects | 22 / 25 |

## Not built here (same portal, future modes)

SINTA also exposes `/departments`, `/subjects`, `/sources` (journals),
`/books`, `/ipr`, `/researches` and `/comservices`, all on the same
server-rendered pattern — the cheapest expansion path if this actor finds
demand. Garuda (`garuda.kemdiktisaintek.go.id`, 22 KB) is the sibling
publication index on the same ministry domain.
