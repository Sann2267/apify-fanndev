# Crawling Method — TopCV Scraper

**Last verified:** 2026-08-26

## Target

[topcv.vn](https://www.topcv.vn) — Vietnam's largest job board. Job
search/listing site, not a news outlet, so the recon and architecture
differ from this portfolio's news-scraper actors (no article text, no
RSS/sitemap-of-articles pattern — this one is search + structured job
postings). Closest structural precedent in this portfolio: `karir-com-scraper`
(Indonesia, same vertical/region) — though the two targets turned out to
need different extraction strategies (see below).

## robots.txt — independently re-verified

```
User-agent: *
Sitemap: https://www.topcv.vn/sitemap.xml
Disallow: /cv/get-private-url/
Disallow: /private/
Disallow: /xem-cv/
Disallow: /xem-cv-draft/
Disallow: /sua-cv/
Disallow: /viet-cv/
Disallow: /edit/cv/
Disallow: /cv-ung-vien/
Disallow: /cv-ung-tuyen/
Disallow: /p/
Disallow: /v4/image/cv-template/cv-sample/toppy-list-mau-cv.png
```

A single flat `User-agent: *` group. No explicit Claude/ClaudeBot/Claude-Web/
Claude-SearchBot/anthropic-ai block anywhere, no blanket `Disallow: /`.
Every disallowed path is about *candidates'* private CV data (viewing/editing
a résumé, private CV share links) — none of it overlaps with what this
actor touches: `/tim-viec-lam-*` (search results) and `/viec-lam/*.html`
(individual job postings) are both fully allowed.

## No login required — full job posting is public

**Critical check passed.** Every field this actor extracts from a job
detail page — title, full description (HTML: responsibilities +
requirements + benefits), salary, employer info, skills, experience,
headcount — comes from the page's own public `application/ld+json`
`JobPosting` block, fetched with a bare `curl_cffi` GET and **no cookie,
session, or Authorization header of any kind**. Confirmed live across
several listings. `robots.txt`'s CV-related disallows are about
*candidate* data (the job-seeker side of the platform, which does require
login) — the *employer job posting* side this actor scrapes is fully
public, matching this project's public-data/no-login constraint.

## No WAF blocking found

topcv.vn sits behind Cloudflare (`server: cloudflare` response header) but
`curl_cffi` (`impersonate="chrome124"`) gets clean HTTP 200s with full page
content on the homepage, search results pages, and job detail pages —
confirmed live. The string `challenge-platform` does appear in the
homepage HTML, but it's Cloudflare's benign passive bot-telemetry script
tag (`/cdn-cgi/challenge-platform/scripts/precursor/main.js`), not an
active JS challenge — a real interstitial challenge page would be a small
(~15KB) stub, not the full ~1.2MB homepage this actor actually receives.
No `cf-mitigated` header, no "Just a moment" text, no captcha markers.
Retry/backoff scaffolding (`src/client.py`) is kept anyway per portfolio
convention, in case that changes later.

## Architecture: SSR HTML search + public JSON-LD detail (not a JSON API)

Unlike `karir-com-scraper`, **no public JSON REST API could be found**
behind topcv.vn's search UI. topcv.vn is a classic server-rendered
PHP/Laravel-style site (there is no `__NEXT_DATA__`, no Apollo state, no
`application/json` XHR to imitate) — its search form is a Vue-enhanced
widget that, on submit, simply navigates the browser to a pretty "slug"
URL. Every plausible query-param name was tested live and found to be
silently ignored (ignored, not erroring — the response is still a normal
200 with the *unfiltered* result set, which makes this easy to miss if
you don't check the reported result count):

- `?keyword=python`, `?q=python` on `/tim-viec-lam-moi-nhat` — ignored,
  still returns the full ~48k unfiltered count.
- `?location=1`, `?l=1`, `?locations=l1` on a keyword page — ignored,
  count stays identical to the unfiltered keyword search.
- `?type_keyword=1` — no effect on its own.

### The real filtering mechanism: pretty-URL path slugs

Reverse-engineered by testing many URL combinations live and cross-checking
each one's reported result count (`<h1 id="search-job-heading" ... title="Tuyển
dụng N việc làm ...">`) against a known baseline:

| Filter | URL pattern | Confirmed live |
|---|---|---|
| Keyword only | `/tim-viec-lam-{keywordSlug}` | `/tim-viec-lam-python` → "16 việc làm Python"; `/tim-viec-lam-ke-toan` → "4.481 việc làm Kế Toán"; a made-up slug (`/tim-viec-lam-abcxyz123`) → "0 việc làm", proving it's real full-text matching, not a fixed category whitelist |
| City only (newest-sorted) | `/tim-viec-lam-moi-nhat-tai-{citySlug}-l{cityId}` | `/tim-viec-lam-moi-nhat-tai-ha-noi-l1` → "22.234 việc làm tại Hà Nội" |
| Keyword + city | `/tim-viec-lam-{keywordSlug}-tai-{citySlug}-kl{cityId}` | `/tim-viec-lam-python-tai-ha-noi-kl1` → "13 việc làm Python tại Hà Nội" (a subset of the keyword-only count, as expected) |
| No filter (newest) | `/tim-viec-lam-moi-nhat` | baseline "48.xxx việc làm" |
| Pagination | `?page=N` (1-based) | page 1 and page 2 return disjoint job-ID sets |

**Important gotcha found during recon:** the keyword+city *combined*
pattern uses `-kl{cityId}` (note the `k`), NOT `-l{cityId}` — an earlier
attempt at `/tim-viec-lam-python-tai-ha-noi-l1` (using the city-only
suffix on a keyword URL) returned HTTP 200 but silently reinterpreted the
*entire* URL as a city-only search (title said "22.234 việc làm tại Hà
Nội", completely dropping "python" — coincidentally close to the
city-only baseline count), rather than erroring or 404ing. The correct
`-kl{cityId}` suffix was only found by inspecting the real
"search by province" link list topcv.vn itself renders at the bottom of
every keyword search-results page.

The `keywordSlug` is produced by this actor's own `slugify()`
(`src/extractor.py`) — Vietnamese-aware: `đ/Đ → d/D`, NFD-normalize +
strip combining marks for all other diacritics, lowercase, non-alphanumeric
runs → single dash. Verified live to match the site's own conversion for
both diacritic and plain-ASCII/multi-word input (e.g. "Nhân viên bán hàng"
→ `nhan-vien-ban-hang` → real 6,518-result page; "ke toan" (already
ASCII) → `ke-toan` → same page as diacritic "Kế toán").

### City ID list

`src/constants.py`'s `CITY_IDS` (63 provinces, slug → numeric ID) was
scraped live from the "search by province" link list topcv.vn renders on
every keyword search page (e.g. `/tim-viec-lam-python`). ID gaps (41–43,
63) are real and match the site's own list as rendered — not an omission
by this actor; likely retired/merged province IDs following Vietnam's
2025 administrative province merger (topcv.vn's UI still shows a
"Địa điểm làm việc đã được cập nhật theo Danh mục Hành chính mới" tooltip
on job cards' location links, confirming the site is mid-migration on this
exact axis).

### Search results page: SSR HTML CSS selectors (S1-html-search)

Each search results page embeds job cards as
`<div class="job-item-search-result" data-job-id="...">` — title,
canonical job URL, company name/URL/logo, a displayed salary label (e.g.
"Tới 45 triệu", or "Thoả thuận" = negotiable — not parsed into a number,
passed through as displayed text), city, experience-required label, a tag
list (job function + a truncated tooltip of additional tags), and a
relative posted/updated label. Also present near the top of the page: a
`SearchResultsPage`/`ItemList` JSON-LD block, but it only carries
title+URL per item (no company/salary/location) — the HTML cards carry
strictly more, so they're the primary source; the JSON-LD block wasn't
used.

**Not every search result lives at a `/viec-lam/<slug>/<id>.html` URL** —
sponsored/employer-branded listings can appear at
`/brand/<company-slug>/tuyen-dung/<slug>-j<id>.html` instead (seen live
for MB Bank postings). This actor doesn't rely on the card's own display
URL to get the job ID — it reads `data-job-id` directly, and confirmed
live that the alternate-URL-scheme job IDs still resolve correctly via
the canonical-redirect trick below when hydrating full detail.

**Pagination stop condition:** the page footer's
`<span id="job-listing-paginate-text">1 / 31 trang</span>` gives
`(current_page, total_pages)` directly — `run_search()` stops when
`current_page >= total_pages`, an empty page is returned, `maxResults` is
reached, or the page returns non-200.

### Detail page: public schema.org JobPosting JSON-LD (S1-jsonld)

```html
<script type="application/ld+json">{"@context":"http://schema.org/","@type":"JobPosting", ...}</script>
```

Confirmed live on every job detail page tested — a complete, richly
structured object: `title`, `description` (HTML, combines job description
+ candidate requirements + benefits under `<h2>` sub-headings),
`jobBenefits` and `employerOverview` (the same benefits/responsibilities
HTML, also available standalone), `identifier` (`{name, value}` — the
employer's numeric company ID), `datePosted`/`validThrough`,
`employmentType`, `hiringOrganization` (`{name, sameAs, logo}`),
`jobLocation` (`{address: {streetAddress, addressLocality, addressRegion,
postalCode, addressCountry}}`), `baseSalary` (`{currency, value:
{unitText, maxValue?, minValue?}}` — when the employer marks salary
negotiable, `value.value` holds the literal string `"Thoả thuận"` instead
of a number, confirmed live; this is common), `industry`, `skills`
(comma-joined string), `experienceRequirements`
(`{monthsOfExperience}`), `occupationalCategory`, `totalJobOpenings`.
Passed through close to verbatim per this portfolio's raw-passthrough
convention (`src/extractor.wrap_detail`).

**Canonical-redirect trick for ID-only lookups:** a job detail URL is
`/viec-lam/<any-slug>/<id>.html` — the slug segment is cosmetic. Confirmed
live: `GET /viec-lam/xxx/2143657.html` (deliberately wrong slug) still
returns HTTP 200 and redirects to the real canonical URL
(`/viec-lam/fullstack-software-engineer/2143657.html`) with the full
JobPosting JSON-LD intact. So `fetch_detail()` always builds
`/viec-lam/x/<id>.html` regardless of what slug (if any) the caller
supplied — no need to know or guess the real slug.

**Not-found behavior:** an invalid/expired job ID does **not** return a
real HTTP 404 — it still returns HTTP 200, but the final redirected URL is
the bare listing root, `https://www.topcv.vn/viec-lam` (no id segment).
Confirmed live with both a very old ID (`1`) and a deliberately
out-of-range one (`999999999`) — both redirect to `/viec-lam` and carry no
`JobPosting` JSON-LD. `src/extractor.is_not_found_url()` detects this by
comparing the resolved response URL, and `fetch_detail()` also falls back
to "not found" if, for any reason, the JSON-LD block is simply absent.

## Cloud smoke test findings

Two things were caught by testing on the actual Apify platform (residential
proxy, different egress than local recon) that local `curl_cffi` testing
alone didn't surface:

1. **Fixed: one hydrate task's failure was taking down the whole search
   batch.** `run_search()`'s per-job `_hydrate()` task didn't originally
   catch `RuntimeError`/`ConnectionError` from a blocked/exhausted-retries
   detail fetch -- that exception propagated up through
   `asyncio.gather()` uncaught, which was caught by `run_search()`'s
   *outer* try/except and replaced the **entire** batch (all already-fetched
   summaries) with a single generic `blocked_or_transient` error record.
   Confirmed live: a 5-result search that should have produced 5 records
   produced exactly 1 after a single detail fetch failed. Fixed by
   catching those exceptions inside `_hydrate()` itself and falling back
   to that one job's search-summary record (same as any other detail-fetch
   failure) instead of letting it escape to the outer handler.
2. **A synthetic/unrealistic job ID (`"999999999"`) reliably triggers
   `blocked_or_transient` via the residential proxy, while a realistic
   invalid ID (`"1"`) correctly returns `not_found`.** Both resolve
   cleanly to `not_found` when fetched directly (no proxy) from this
   recon session's own IP. This looks like target-side extra scrutiny on
   suspicious-looking huge IDs specifically via certain proxy exits, not a
   bug in this actor's not-found detection (`is_not_found_url()` — see
   above) — real topcv.vn job IDs are ordinary ~7-digit numbers, so this
   shouldn't affect normal use. Left as a known edge case rather than
   special-cased.

## Known limits

- **Search filtering is one dimension of keyword and one dimension of
  city, combined via one specific URL pattern (`-tai-{city}-kl{id}`) —
  not a general filter API.** No salary-range, experience-level, or
  employment-type filter could be reverse-engineered as a working
  query-param or URL-slug combination in the time available (every
  attempt either got silently ignored or reinterpreted the URL as
  something else, as documented above). Free-text `keyword` (matches job
  titles/content) and `city` (Vietnamese province) are the two supported
  filter axes.
- **`salary_text` is the site's own display string, not a parsed
  number** (`"Tới 45 triệu"`, `"7 - 10 triệu"`, `"Thoả thuận"` =
  negotiable) — consistent with this portfolio's raw-passthrough
  convention rather than inventing a normalized currency schema topcv.vn
  doesn't expose structurally on the search page. The full-detail
  record's `baseSalary` (from JSON-LD) is more structured
  (`{currency, value: {unitText, maxValue}}`) but is likewise
  absent/partial when the employer chooses "negotiable".
- **Result volume reflects the site's actual current live inventory** —
  e.g. "python" nationwide returned only 16 active postings at recon
  time, "IT" (broad category) returned 1,549 — this is a real property of
  the target's current job market, not a pagination bug.
- **A small amount of ID overlap between adjacent search-result pages is
  possible** — observed live (119 unique IDs out of 120 fetched across 3
  pages for a broad "it" search): a pinned/highlighted listing can appear
  near a page boundary as live rankings shift between requests. Not
  deduplicated by this actor (mirrors this portfolio's general stance:
  pass through what the site returns rather than silently dropping
  results the site itself served).

## Diff cadence

Quarterly smoke test recommended.
