# Crawling method — glints.com

Reconnaissance and implementation notes. Last verified **2026-09-21**.

## Surface

| Property | Finding |
| --- | --- |
| Endpoint | `POST https://glints.com/api/v2/graphql` |
| Transport | Plain GraphQL over JSON. No persisted queries, no `doc_id`, no operation allow-list. |
| Auth | None. Responses carry `"isAuthenticated": false` as a first-class state. |
| Introspection | **Enabled.** The full schema is readable, which is where every input shape in `src/queries.py` came from. |
| Edge | Cloudflare, passive. |
| Root query type | `RootQuery`, 22 fields. |

There are three GraphQL endpoints in the site bundle. Only the v2 one carries jobs:

| Path | Server | Carries jobs? |
| --- | --- | --- |
| `/api/graphql` | Apollo Server | No — different schema, introspection disabled |
| `/api/v2/graphql` | Go | **Yes** — `searchJobsV3`, `getJobById`, `getCompanyById`, … |
| `/api/v2-alc/graphql` | Go | Same schema as v2, proxied |

## WAF profiling

No gate. The full TLS ladder was run against the same IP:

| Profile | `/id` homepage | Search page |
| --- | --- | --- |
| `chrome124` | 200 | 200 |
| `safari17_0` | 200 | 200 |
| `firefox133` | 200 | 200 |
| `edge101` | 200 | 200 |
| `chrome99_android` | 200 | 200 |

No rate limiting either: 30 serial searches finished in 3.5 s and 24 concurrent searches in 0.7 s, all 200. No cookies, tokens, signatures or warm-up requests are required.

### …except on the static sitemap paths, from a datacenter IP

The table above is from a residential home IP. **On Apify's datacenter addresses the picture splits by path**, which only showed up on the platform:

| Path | `chrome124` from Apify DC | `safari17_0` from Apify DC |
| --- | --- | --- |
| `/api/v2/graphql` | 200 | 200 |
| `/sitemap_index.xml` | **403** | **200** |

So Cloudflare scores glints.com's *static* paths per TLS fingerprint on datacenter ASNs while leaving the JSON API alone — the same shape as the Blibli `merchant/info` gate. Two consequences, both implemented:

- `get_text()` sends a full browser document header set (`accept`, `sec-fetch-*`, `upgrade-insecure-requests`, referer) rather than relying on impersonation alone, because a header-less GET is what scores worst.
- `get_text()` treats 401/403/406/429 as **rotate-and-retry**, not plain retry, and gets at least a full pass of the ladder (`max(max_retries, len(TLS_PROFILES))` attempts). Before this fix it retried the same blocked fingerprint until it ran out and the whole `sitemapCrawl` mode failed on the platform while passing locally.

Verified in the run log: `HTTP 403 for .../sitemap_index.xml; rotating profile` → `Rotated TLS profile to safari17_0` → `Sitemap discovery succeeded`. `robots.txt` is also tried as a second discovery route since it advertises the same index on a different path.

`curl_cffi` is still used, and the ladder is still implemented, because the zone *could* start gating without notice. The client rotates profiles on a challenge body or an unexpected 403 rather than failing the run.

**Proxy is therefore off by default.** Residential is wired up and available if a future rate limit appears or a specific exit country is needed, but paying for it today buys nothing.

## The one real gate

`searchJobsV3` with `page >= 2` returns HTTP 403:

```json
{"errors":[{"message":"please login for more information"}]}
```

This is a product paywall, not an anti-bot measure — no header, cookie, `expInfo` echo, device id, tracking session id, `searchVariant` or `sortBy` combination moves it. All were tested.

So **anonymous search tops out at 50 jobs per query** (`pageSize` silently caps at 50; asking for 100 or 200 returns exactly 50 with `hasMore` still true).

### Two ways around it, both implemented

1. **Filter fan-out** (`search` mode). Every query is its own page 1, so many narrow queries reach far more of the corpus than one broad one. Measured: 8 different slices of the same market yielded **326 unique jobs**, against a 50-job ceiling for any single query. Results are deduplicated by job id across the whole fan-out.

2. **Sitemap crawl** (`sitemapCrawl` mode) — the complete route. `sitemap_index.xml` lists **4,870** sitemaps, and `getJobById` is **not** gated. Pairing them reaches the entire public corpus.

| Sitemap family | Count | Enumerates |
| --- | --- | --- |
| `sitemap_find_jobs_id_N` | 1,591 | ID search landing pages |
| `sitemap_companies_id_N` | 1,259 | ID company directory pages |
| `sitemap_job_id_N` | 733 | ID native postings (~73k) |
| `sitemap_sourced_job_id_N` | 541 | ID aggregated postings (~54k) |
| `sitemap_company_id_N` | 290 | ID company profiles |
| `sitemap_job_vn_N` / `_sg_` / `_my_` | 58 / 4 / 1 | VN, SG, MY postings |
| `sitemap_location_id_N`, `sitemap_category_id_N` | 24, 7 | Taxonomy pages |

Each posting appears twice per sitemap, once per language prefix (`/id/...` and `/id/en/...`); the crawler keeps one.

## Decoys and traps

Six things that look usable and are not. Each cost a probe round:

1. **`searchJobs.totalJobs` is meaningless.** It returns `10` for every market — ID, SG, VN, TW, MY, PH — regardless of the real corpus size, and regardless of `pageSize`. Do not use it for market sizing. The legacy `searchJobs` field also ignores `pageSize` entirely.
2. **`offset` / `limit` are ignored by `searchJobsV3`.** Only `page` / `pageSize` work. Passing `offset: 30` returns the same first rows again, so a naive offset loop silently emits duplicates while looking healthy.
3. **`offset` *does* work on `skills`.** The opposite of the search behaviour, which is why the skills walker is a real loop while search is not.
4. **`skills.count` reports 1000 but is not the end.** Offset 1000 still returns 50 rows; offset 1500 returns none. The stop condition must be an empty page, not the reported count.
5. **Two dead location surfaces.** `searchHierarchicalLocations` always returns `[]` — every combination of `countryCode`, `searchTerm`, `searchType`, `levels` and `withActiveJobsOnly` was tried. And inside `getJobSearchFiltersV2`, the `cities`, `citySubDivisions` and `cityIds` facets are *also* always empty, even while `companies` and `jobRoles` in the same response are populated and correctly keyword-scoped. The one live location surface is `getJobSearchFiltersV2.hierarchicalLocations` (20 entries, plus matching `locationIds`), which is what the `filters` mode reports as `topLocationNames`.
6. **`SalaryFilter` matches on overlap, not on the floor.** A job advertised at 3,500,000–5,000,000 matches `minimum: 5000000` because its *ceiling* touches the band. Measured: with `minimum: 15000000`, 46/46 results satisfy `maxAmount >= minimum` but only 17/46 satisfy `minAmount >= minimum`. Passed through faithfully so output matches what the site shows; documented in the input schema so nobody reads it as a bug. Side effect worth knowing: applying any salary filter also drops postings that hide their pay (21/50 results carry a salary with no filter, 49/50 with one).

Auth-gated and excluded: `searchNormalizedSchools` (401), `getBookmarkedJobs`, `getBookmarkedTalents`, `getUnlockedTalents`, `getMultiJobBoosting*`, `getObjectStorage*`.

Enum drift worth noting: the live `jobTypes` facet returns `PROJECT_BASED`, which the site's own filter UI does not offer. It is included in the input enum because postings really do carry it.

## Query construction

Queries in `src/queries.py` are written by hand against the introspected schema rather than lifted from the site bundle, so a webpack rebuild cannot rot them.

**The v2 resolver is stricter than Apollo Server** in two ways that both cost a debugging round:

- A fragment that is defined but never spread fails validation outright (`Fragment "CompanyCard" is never used`). Each operation therefore concatenates exactly the fragments it references — hence `JOB_FRAGMENTS` versus a bare `F_LOCATION` on the filters query.
- A missing or null `variables` map fails with `GRAPHQL_PARSE_FAILED` (`data['variables'] is not a map[string]interface{}`). The client always sends a map.

Field-level trap: `metadata.workShifts` is an **enum list**, not an object list, so a sub-selection on it is a validation error.

## Personal data

The `Job` type exposes `creator { name lastSeen online image }` — the individual recruiter handling the posting. That is personal data about a named person rather than information about the vacancy, so it is omitted from every selection in `src/queries.py`. The responsiveness signals alongside it (`isHighResponseRate`, `creatorResponseRate`, `creatorResponseTime`) are properties of the posting and are kept.

## robots.txt

`robots.txt` disallows `*/opportunities/jobs/explore?*` — the faceted search page with query strings, a standard SEO directive against index bloat. It also disallows the tracking paths `/api/glintsTracking/*` and `/api/gt/*`. The data API and the job, company and sitemap paths this actor uses are **not** disallowed, and the sitemaps are advertised in `robots.txt` itself.

## Error taxonomy

| Upstream | Actor behaviour |
| --- | --- |
| `RECORD_NOT_FOUND` (HTTP 404) | `_error: "not_found"` — a dead id is a fact, not a failure; no retry |
| `please login for more information` (403) | `_error: "login_required"`, paging stops cleanly |
| Challenge body markers | Rotate TLS profile, retry |
| 429 / 5xx | Exponential backoff with jitter, capped at 30 s |
| GraphQL validation error | Raised immediately — it will not heal on retry |
| Empty result | `_error: "no_results"` row, never a silent skip |

## Cost shape

| Mode | Requests |
| --- | --- |
| `search` | 1 per term (up to 50 jobs each) |
| `filters` | 1 per term |
| `suggestions` | 1 per keyword |
| `company` | 1 per employer, returns the profile *and* every open vacancy |
| `jobDetail` / `similarJobs` | 1 per job |
| `sitemapCrawl` | 1 per 100 jobs for ids, then 1 per job to hydrate |

`company` is the cheapest route to every vacancy at a known employer, and is not subject to the 50-row ceiling.

## Deployment

Actor `fanndev/glints-jobs-scraper` (`S07ImePIc0BWlVXuh`), build 0.0.2, private.

All eight modes verified on the platform, every run exit 0 at 512 MB:

| Mode | Time | Items |
| --- | --- | --- |
| `search` (ID) | 7 s | 30 |
| `search` (SG) | 5 s | 10 |
| `jobDetail` | 7 s | 2 (1 detail + 1 `not_found` for a dead id) |
| `company` | 6 s | 5 (1 profile + 4 vacancies) |
| `similarJobs` | 8 s | 11 |
| `sitemapCrawl` | 9 s | 10 |
| `filters` | 11 s | 1 |
| `suggestions` | 6 s | 10 |
| `skills` | 6 s | 60 |

Platform gotchas hit during deployment, all worth knowing before the next one:

- **`apify push` ignores `defaultRunOptions` and `categories`.** The actor was created at 4096 MB despite `actor.json` declaring 512, and with no categories. Both had to be set with `PUT /v2/acts/<id>`. At 4096 MB a pay-per-event actor bills 4 start events instead of 1, so this quadruples the floor price of every run for nothing — peak memory here is 61 MB.
- **`apify push` after an API change needs `--force`** ("modified there since modified locally").
- **`apify auth token` blocks on stdin**; redirect `</dev/null`. `apify call` likewise does not exit after the run completes — check `apify runs ls` instead of waiting on it.
- **`description` in `actor.json` is capped at 300 characters**; push fails outright above it.
- **Dataset `itemCount` lags** for a few seconds after a run finishes. Reading it immediately returns 0 for a run that really wrote 10 rows — do not mistake that for an empty run.
- **Free plan allows 5 concurrent runs**; starting a sixth returns `402 Payment Required`, which is a concurrency limit, not a billing problem. Account cap is $5/month.

## Re-verification

Run `python test_local.py` — it seeds fixtures from a live search, so nothing rots when a posting closes. Re-check quarterly, and specifically when:

- `searchJobsV3` starts erroring → the schema was versioned to V4; re-introspect.
- Page 2 starts working → the login wall was relaxed; add paging.
- Introspection stops working → fall back to harvesting queries from `_app-*.js`.
