# Crawling Method — Karir.com Scraper

**Last verified:** 2026-08-26

## Target

[karir.com](https://karir.com) — an Indonesian job board ("Situs Lowongan Kerja
Indonesia"). Job search/listing site, not a news outlet, so the recon and
architecture differ from this portfolio's news-scraper actors (no article
text, no RSS/sitemap-of-articles pattern — this one is search + structured
job postings).

## robots.txt — independently re-verified

```
User-agent: *
Crawl-delay: 1

# Old site
Disallow: /karir/
Disallow: /jobs/
Disallow: /klasika/
Disallow: /php/
Disallow: /opportunities/1061574

# LinkedIn Bot
User-agent: LinkedInBot
Disallow: Thank you for your business! We look forward to working with you again.
```

A single flat `User-agent: *` group. No explicit Claude/ClaudeBot/Claude-Web/
Claude-SearchBot/anthropic-ai block anywhere, no blanket `Disallow: /`. The
`Disallow` lines under "# Old site" are commented as legacy and target path
prefixes (`/karir/`, `/jobs/`, `/klasika/`, `/php/`) that the current
Next.js frontend doesn't use at all — this actor never touches them. The one
non-legacy line, `Disallow: /opportunities/1061574`, singles out **one**
specific listing ID; every other `/opportunities/<id>` is allowed (confirmed
live: fetching `/opportunities/1401468` and others returns 200 normally).
This actor honors that one exclusion defensively — see
`DISALLOWED_OPPORTUNITY_IDS` in `src/constants.py` — any search result or
direct input that resolves to ID `1061574` is skipped with a
`disallowed_by_robots_txt` error record rather than fetched.

The separate LinkedInBot group is a joke/placeholder entry (its "Disallow"
value is a sentence, not a path) and doesn't apply to this actor's user
agent.

The API host this actor actually calls, `gateway2-beta.karir.com`, has no
`robots.txt` of its own (404) — no restrictions declared for that host.

## No login required — full detail is public

**Critical check passed.** Every field used by this actor — job title,
full requirements, full responsibilities, salary range, company profile,
address — comes back with **no session, no Authorization header, no API
key, and no cookie** sent at all. Confirmed live with a bare `curl_cffi`
POST carrying only `Content-Type`/`Accept` headers. When an employer
chooses to stay anonymous, the API returns the literal upstream label
`"LABEL_COMPANY_CONFIDENTIAL"` for `company_name` (and an empty/placeholder
`company` object) — that's the employer's own privacy choice, not a
login-gate; the job posting itself (title, requirements, responsibilities,
salary) is still fully returned.

## No WAF found

Checked with `curl_cffi` (`impersonate="chrome124"`) against the homepage,
the client-rendered search page, an individual job detail page, and the
JSON API host directly. No Cloudflare/Akamai/PerimeterX/DataDome markers,
no `cf-ray` header, no challenge page, no 403 of any kind — clean 200s
everywhere tested. Retry/backoff scaffolding (`src/client.py`) is kept
anyway per portfolio convention, in case that changes later.

## Architecture: reverse-engineered public JSON API, not JSON-LD

karir.com is a Next.js app, but unlike most SSR sites in this portfolio,
its search page (`/search-lowongan`, aliased by pretty URLs like
`/lowongan-kerja-jakarta`) ships **no data at all** in `__NEXT_DATA__` —
`pageProps` is just `{"userData":null}`. All real data is fetched
client-side from a JSON REST API on a separate host. This was found by
downloading the site's webpack chunks and locating the shared API-client
module, which defines two axios instances:

```js
h = m("https://karir-ms-beta.karir.com")
E = m("https://gateway2-beta.karir.com")
```

...and an endpoint map (`s.H`) including:

```js
search:              "v2/search/opportunities"   // used via E (gateway2-beta)
opportunity:          "v1/opportunity/detail"      // used via E (gateway2-beta)
```

Both were confirmed live with plain `curl_cffi` POST requests carrying a
JSON body and no auth — this is the primary (and only) strategy used;
there was no need to fall back to JSON-LD or `__NEXT_DATA__` scraping.

An individual job page (`/opportunities/<id>`) **does** also embed the
same detail payload server-side inside a non-standard
`<script type="application/ld+json">` tag (`@type: "Article"` wrapping a
`data`/`companyData` object, HTML-entity-double-encoded) — this was found
first, during initial recon, but the direct API call returns the identical
data already-unescaped and with cleaner types (e.g. `degrees` as a real
list instead of a comma-joined string), so the actor calls the API
directly rather than parsing that HTML.

### Search endpoint

```
POST https://gateway2-beta.karir.com/v2/search/opportunities
Content-Type: application/json

{
  "keyword": "sales",
  "locale": "id",
  "limit": 20,
  "offset": 0,
  "sort_order": "newest"
}
```

Returns `{"code":200,"data":{"total_opportunities": N, "opportunities": [...]}}`.
`keyword` matches against the job title (`job_position`) — confirmed live
by inspecting sampled titles for several keywords. Additional optional
filters accepted by the endpoint and exposed as pass-through advanced input
fields: `location_ids`, `company_ids`, `industry_ids`, `job_function_ids`,
`degree_ids`, `min_salary`, `max_salary`, `level`, `workplace`. This actor
does not attempt to resolve human-readable location/industry/job-function
names to their numeric IDs — see Known limits.

**Page size is server-capped at 20** — confirmed live: requesting
`limit: 50` or `limit: 100` still returns only 20 items. Pagination uses
`offset` in steps of 20 until `offset >= total_opportunities` or a short
page is returned.

**`sort_order`** accepts `newest`, `priority`, `popular`, `highest_salary`
(reverse-engineered from the site's own sort dropdown, which maps
"Terbaru"/"Prioritas"/"Paling Populer"/"Gaji Tertinggi" to these exact
values). Confirmed live that each produces a genuinely different result
order. An unrecognized value is silently ignored (falls back to default),
not rejected — same pattern as other actors in this portfolio (e.g.
`poshmark-scraper`), so only the confirmed-working values are exposed.

### Detail endpoint

```
POST https://gateway2-beta.karir.com/v1/opportunity/detail
Content-Type: application/json

{"opportunity_id": 1401468}
```

Returns `{"code":200,"data":{...full job object...}}`. The full object
includes `requirements`/`responsibilities` (HTML strings), `salary_lower`/
`salary_upper` (nullable ints — undisclosed salary is a real, common case,
not a login-gated field), `degrees`/`majors`/`job_functions`/`job_levels`
(lists), `posted_at`/`expires_at`/`updated_at`, and a nested `company`
object (id, name, logo, industry, description, subscriber count, benefits).

**Not-found behavior:** a nonexistent/invalid ID does **not** return HTTP
404 — it returns **HTTP 400** with body
`{"code":400,"message":["Invalid Opportunity"],"data":null}`. Confirmed
live with a deliberately invalid ID (`999999999`). `src/main.py`'s
`fetch_detail()` detects this specific message and reports it as a normal
`not_found` record rather than a generic `http_400` error.

## Pagination stop conditions

`run_search()` in `src/main.py` stops when any of: the requested
`maxResults` cap is reached, an empty page is returned, `offset >=
total_opportunities`, or a page comes back shorter than requested (defends
against `total_opportunities` disagreeing with the actual result count,
which was not observed but is treated defensively).

## Known limits

- **Location/industry/job-function filtering is ID-based, not
  name-based.** `v1/location/search` (the endpoint the site's own location
  autocomplete presumably calls) was tested with every plausible body-key
  name (`keyword`, `name`, `q`, `search`, `term`, `value`) and always
  returned the same fixed, unfiltered list of ~20 locations regardless of
  input — no working name→ID lookup could be reverse-engineered in the
  time available. This actor exposes `locationIds`/`jobFunctionIds`/
  `industryIds`/`degreeIds`/`companyIds` as optional pass-through filters
  for users who already know the numeric IDs (visible in karir.com's own
  filter UI network calls), but does not resolve a city/industry *name*
  to an ID itself. Free-text keyword search (which matches job titles) is
  fully supported and is the primary way to narrow results.
- **Result volume reflects the site's actual current live inventory**,
  which is a few hundred active postings at any given time (empty-keyword
  search returned `total_opportunities: 164` at recon time) — this is a
  real property of the target, not a pagination bug.
- **`salary_lower`/`salary_upper` are frequently `null`** — Indonesian job
  postings commonly use a `salary_info` label like
  `LABEL_COMPETITIVE_SALARY` instead of disclosing a figure. These label
  strings are passed through raw (they're upstream i18n keys, not
  translated by this actor).
- **`description` means different things in the two record shapes** —
  in a full-detail record it doesn't appear at all (the job's HTML body
  is `requirements`/`responsibilities` instead); in a compact
  search-summary record (`fetchFullDetails: false`), `description` is the
  city/province name, not job description text — an upstream naming quirk,
  passed through as-is per this portfolio's raw-passthrough convention.

## Diff cadence

Quarterly smoke test recommended.
