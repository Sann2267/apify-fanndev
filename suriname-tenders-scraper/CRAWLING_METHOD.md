# Crawling Method — Suriname Government Tenders (gov.sr)

**Last verified:** 2026-08-27

## Target discovery — no dedicated e-GP platform; the official gov.sr site is the real source

Independent web search (English and Dutch queries, per the brief: "Suriname
aanbestedingen overheid online", "Suriname staatsbesluit aanbesteding",
"Suriname government tenders procurement portal official") turned up several
names that do **not** hold up under direct verification:

- **"Staatstenders Suriname" (`staattenders.sr`)** — described by AI search
  summaries as "the central hub since 2020" with "mandatory electronic
  submission by Q2 2026". `curl_cffi` DNS resolution fails outright
  (`Could not resolve host: staattenders.sr`) — this domain does not exist.
  Hallucinated, same recurring pattern flagged in Babak 22+ of this
  portfolio's research log (e.g. Barbados' `etenders.gov.bb` in Babak 26).
- **"GOEDGE" e-procurement platform** at the Ministry of Finance and
  Planning — mentioned in secondary sources as an integrated e-Procurement
  system, but no resolvable, reachable host was ever found for it during
  recon; treated as unverified/vaporware rather than pursued further, since
  a genuinely working alternative was already confirmed (below).
- A cluster of third-party commercial tender-alert aggregators
  (`tendersinfo.com`, `tendersgo.com`, `tendersontime.com`,
  `surinametenders.com`, `biddetail.com`, `globaltenders.com`) — same
  pattern as every other country in this portfolio's tender vertical: they
  compile/resell the same public notices the government already publishes
  for free. None used as a source.

The genuinely official, reachable, and **currently active** source is the
government's own website, **`gov.sr`** ("Overheid van de Republiek
Suriname") — a WordPress site (confirmed via `wp-json`, standard WP REST
routes, and `wp-content` asset paths) that is *also* the domain search
results themselves point to (`gov.sr/category/aanbestedingen/`, a "Ministerie
van Financiën en Planning werkt aan digitaal GovServices Portal" news post
on the same domain). This is not a guess or a decoy — it is Suriname's
actual central government web presence, and it publishes two genuinely
distinct, fully public tender data streams through its own REST API (see
below).

## robots.txt / WAF

`GET https://gov.sr/robots.txt` returns a plain 42-byte blanket allow:

```
user-agent: * 
disallow: 
crawl-delay: 60
```

One `User-agent` group, empty `Disallow`, a single `Crawl-delay: 60`
directive. No `Claude`/`ClaudeBot`/`anthropic-ai`/any other named-bot group
anywhere in the file, and no natural-language prohibition comment. This
actor honors the `Crawl-delay: 60` directive literally via a process-wide
rate limiter (`src/client.py::_RateLimiter`, same pattern as
`comoros-anpi-scraper`) shared across every request the run makes, so the
actual request rate against `gov.sr` never exceeds one request per 60
seconds regardless of how many pages a run needs to walk.

The host sits behind **Cloudflare**, but purely as a CDN/cache layer, not a
bot-blocking WAF: every JSON API response tested came back `200` on the
first try with plain `curl_cffi` `chrome124` impersonation, no challenge
page, no `cf_clearance` cookie requirement, `cf-cache-status: DYNAMIC`, and
a notably generous `cache-control: max-age=31536000` on the REST responses
themselves — meaning most read traffic against this API is absorbed by
Cloudflare's edge cache rather than hitting Suriname's own origin server at
all.

## No login required to view any listing

Both data sources below were confirmed reachable with a plain
unauthenticated `GET` — no cookies, no session, no API key:

- `GET /wp-json/wp/v2/aanbestedingen?per_page=100` → `200`, real data
  spanning May 2022 to today.
- `GET /wp-json/wp/v2/posts?categories=<id>` (the "Aanbestedingen" category)
  → `200`, real data with full bid text, deadlines as close as days out.

No login wall of any kind was encountered anywhere in this recon — not even
a partial one gating a "detail" view (unlike Zambia/Jamaica's
European-Dynamics-based platforms in earlier rounds of this portfolio's
tender vertical). There is no online bid-submission flow to speak of: every
notice instructs bidders to submit sealed paper bids in person or bidding
documents by email, so there is no "submit" action that could plausibly be
login-gated in the first place.

## Data sources — two genuinely different WordPress REST routes

No OCDS (Open Contracting Data Standard) endpoint or dedicated RSS feed was
found (gov.sr's own `/feed/` is the generic site-wide blog feed, not
tender-specific — not used). Both sources found are already clean JSON, so
no HTML scraping was needed at all — a genuine best case on the "JSON API >
HTML scraping" priority order.

### `tenders` — the `aanbestedingen` custom post type (`GET /wp-json/wp/v2/aanbestedingen`)

A **dedicated custom post type**, separate from the site's generic blog
`post` type, used government-wide by individual ministries for routine
procurement notices (works, goods, services) — mostly in Dutch. **671
records at recon time**, `X-WP-TotalPages: 671` at `per_page=100` → 7
pages, dating back to **20 May 2022**. Six ministry/sector categories were
observed across the full archive: Openbare Werken & Ruimtelijke Ordening
(Public Works & Spatial Planning, the largest by far), Landbouw, Veeteelt
en Visserij (Agriculture, Livestock & Fisheries), Olie, Gas en Milieu (Oil,
Gas & Environment), Ruimtelijke Ordening ROM, Bekendmaking, and
Uncategorized.

Each record is **intentionally thin**: title, publish/modified date, and
the ministry/sector taxonomy term (fetched inline via `_embed=wp:term`, no
second request needed). This CPT's REST schema does not register a
`content` field at all (confirmed: the key is simply absent from every API
response, not empty) — and the individual rendered page itself carries
nothing beyond the title and, inconsistently (present on some records,
absent on others, confirmed by direct comparison), a one-line "Ministerie
van ..." text widget that is already redundant with the taxonomy term. No
PDF/document links, no deadline, no budget figure were found on any sampled
detail page. Because there is nothing richer to fetch, this actor does
**not** issue a separate per-record detail request for this list type — the
list response already is the complete record.

An optional `categorySlug` input lets a user restrict results to one
ministry (e.g. `openbare-werken-ruimtelijke-ordening`); the slug is
resolved to its numeric category ID at request time via
`GET /wp-json/wp/v2/categories?slug=...` rather than hardcoded, so a future
taxonomy change on gov.sr's end doesn't silently break the filter.

### `notices` — posts tagged "Aanbestedingen" (`GET /wp-json/wp/v2/posts?categories=<id>`)

The **same "Aanbestedingen" category name**, but applied to the site's
regular blog `post` type instead of the custom post type above — a
genuinely different, much smaller set of **larger, internationally/
donor-financed solicitations** (explicitly referencing a "Social Bond"
issued by the Republic of Suriname in February 2026, the World Bank/
UNCITRAL-style "International Competitive Bidding (ICB)" and "National
Competitive Bidding (NCB)" procedures, and one Inter-American Development
Bank-financed IT project) — mostly in English. **~11 currently open**
notices at recon time, all dated June–August 2026; older/closed notices
appear to be removed from this category rather than archived, so this list
type reflects "what's open right now" rather than a historical record —
reported honestly rather than padded.

Unlike the `tenders` CPT, this regular `post` type's REST schema **does**
register `content`/`excerpt`, so the full rendered body — background,
procurement method, eligibility criteria, bid evaluation criteria, pre-bid
meeting date, clarification deadline, submission deadline and address, and
a link to the downloadable bidding-document PDF — is already present in the
same list response this actor fetches, with zero extra requests. This
actor passes through both the raw rendered HTML (`contentHtml`) and an
HTML-stripped plain-text version (`contentText`) for convenience.

The category's own numeric ID is resolved dynamically via
`GET /wp-json/wp/v2/categories?slug=aanbestedingen` at the start of every
run rather than hardcoded (`src/client.py::resolve_notices_category_id`),
for the same future-proofing reason as the optional `tenders` filter above.

## TLS profile

`chrome124`, consistent with the portfolio-wide default. No profile-specific
blocking was ever observed on this target — a plain `curl_cffi` request
cleared every endpoint on the first try.

## Encoding / dates

Response bytes are correctly UTF-8; Dutch diacritics (`ë`, `ï`) and smart
quotes render correctly. WordPress' own `date_gmt`/`modified_gmt` fields
come back as naive `YYYY-MM-DDTHH:MM:SS` strings (already UTC, no
timezone suffix) — this actor normalizes them to a proper `Z`-suffixed ISO
8601 string (`publishedAt`/`modifiedAt`) rather than passing the ambiguous
naive form through.
