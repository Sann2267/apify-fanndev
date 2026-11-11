# Crawling Method — Djibouti ODPIC

**Last verified:** 2026-08-27

ODPIC (Office Djiboutien de la Propriété Industrielle et Commerciale,
`odpic.dj`) is the Djiboutian government agency in charge of the Registre
du Commerce et des Sociétés (RCS). It is also the back-office for the
"Guichet Unique" one-stop business-registration desk.

## Portal discovery (two dead ends before the real source)

- `www.guichet-unique.dj` — the domain most third-party/blog sources cite
  as the official Guichet Unique portal. **Times out on every request**
  (`curl_cffi`, plain TCP connect, and a DNS-only check all failed/hung) —
  either dead or not publicly routable. Not usable.
- `guichet-unique-djib.com` — resolves and serves fine (WordPress), but is
  a pure informational/marketing site about registration *procedures*. No
  search tool, no company list, no API. A page crawled from it explicitly
  states name-availability checks happen **in person** at the desk
  ("recherche d'antériorité du nom commercial à l'accueil par les officiers
  de l'ODPIC") — consistent with there being no online lookup at that
  domain.
- **`odpic.dj`** — ODPIC's own site. Also WordPress, but publishes a
  dedicated custom post type, `publication_registre`, that is effectively a
  running public gazette of every RCS filing (registrations, going back to
  entries from 1914). This is what this actor uses.

## Robots.txt

```
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://odpic.dj/wp-sitemap.xml
```

Stock WordPress block. One `User-agent: *` group, no
Claude/ClaudeBot/anthropic-ai/GPTBot mention anywhere in the literal text,
no disallow for `/wp-json/` (the only path this actor touches besides the
root).

## WAF / anti-bot

**None observed.** Plain `nginx/1.18.0` + `PHP/8.0.30`, no
Cloudflare/`cf-ray`/challenge markers, no CAPTCHA. 15 rapid sequential
requests across different pages during recon all returned HTTP 200 with no
slowdown. API responses carry `X-Robots-Tag: noindex` — a search-engine
indexing hint, not a crawl restriction, and it names no specific bot.

## The API: a public WordPress REST route, no login required

The custom post type is registered with `show_in_rest: true`, so it is
queryable through WordPress core's standard public route:

```
GET https://odpic.dj/wp-json/wp/v2/publication_registre
    ?search=<name>          -- matches company/establishment title AND person_name
    &after=<ISO 8601>        -- registration date lower bound
    &before=<ISO 8601>       -- registration date upper bound
    &orderby=date|title      -- default: date
    &order=asc|desc          -- default: desc (newest first)
    &page=<1-based>&per_page=<1-100>
```

Confirmed via `curl_cffi` `chrome124`, no proxy, 2026-08-27:

- 19,602 total records at recon time (`X-WP-Total` header), 197 pages at
  the max `per_page=100` (`per_page=150` → HTTP 400 `rest_invalid_param`).
- `search=MOHAMED` → 827 hits mixing company-name matches
  (`ETABLISSEMENT MOHAMED TAHA SAID SARL`) and owner-name matches
  (`WAEL MOHMAED TARECHE`) — confirms `search` covers both the post title
  and the custom `person_name` field.
- `search=24856` (an exact, real `file_nbr`) → **zero hits**. There is no
  way to look up one filing by its file number through this route; name or
  date-range browsing is the only supported lookup.
- `after=2026-08-20T00:00:00` → 8 matches, all dated 2026-08-23 through
  2026-08-26 — standard WordPress date-range filtering works as expected.
- Default order (no `orderby`/`order`) is already newest-first by date —
  confirmed identical to an explicit `orderby=date&order=desc` request.
- `orderby=date&order=asc` surfaces the oldest record on file: "GLOBE
  INTERNATIONAL AGENCIES", dated **1914-02-05** — pre-independence colonial
  filings appear to have been migrated into the same feed as current ones.
- `GET /wp-json/wp/v2/media?parent=<id>` (checking for an attached
  scan/PDF) returned an empty list on every sample tried — no attachments
  are published with these records.
- No separate per-entity detail route exists or is needed — the list
  endpoint already returns every field ODPIC publishes per filing.

### Sample fields per row (raw, before this actor's flattening)

```json
{
  "id": 10390250,
  "title": {"rendered": "ETABLISSEMENT TAREK WAGDALLE"},
  "slug": "etablissement-tarek-wagdalle",
  "link": "https://odpic.dj/publication-registre/etablissement-tarek-wagdalle/",
  "date": "2026-08-26T00:00:00",
  "file_nbr": "24856",
  "file_ser": "2026",
  "registration_date": "2026-08-26",
  "filing_date": "2026-08-26",
  "main_owner_person_nbr": "1121844",
  "person_name": "TAREK WAGDALLE MOHAMED",
  "addresses": "BALBALA, CHEICK MOUSSA - DJIBOUTI",
  "disclaimers": ""
}
```

`content.rendered` is always empty for this post type. `date`/`date_gmt`
and `modified`/`modified_gmt` were confirmed identical on every sample
checked (these posts are never edited after publishing).

## Field flattening (deliberate — see `src/extractor.py`)

Raw `wp/v2` rows carry generic WordPress CMS/hypermedia scaffolding
(`guid`, `content`, `template`, `class_list`, `_links`, duplicate
`modified*` timestamps) that is constant boilerplate, not registry data.
This actor strips it and keeps, verbatim: `file_nbr`, `file_ser`,
`registration_date`, `filing_date`, `main_owner_person_nbr`,
`person_name`, `addresses`, `disclaimers`, plus `id`/`slug`/`link`/`date`
for identification, and unwraps `title.rendered` to a plain `title` string
(the same unwrap this portfolio's WordPress-backed news actors already do).
No field is renamed or reinterpreted beyond that.

## `disclaimers` is really "declared capital" in practice

The field is named `disclaimers` by ODPIC's own schema, but on every SARL/
company-form filing sampled it actually holds the declared share capital
(e.g. `"10 000 FDJ"`, `"20 000 FDJ"`). It's empty on most sole-trader
(`ETABLISSEMENT`/`ETS`/`QUINCAILLERIE`, etc.) filings. Kept under its
upstream name per this portfolio's raw-passthrough convention — documented
here and in the README rather than renamed.

## Pagination strategy

`page=<n>` (1-based), `per_page` fixed at the server's max of 100. This
actor keeps requesting increasing `page` values until a page returns zero
rows, the running total reaches the caller's `maxResultsPerQuery`, the
upstream `X-WP-Total` count for that filter set is reached, or a
`MAX_PAGES_PER_JOB` (100 pages) safety cap is hit.

## Sample queries tested during recon

- `search=MOHAMED` — 827 hits, mixed title/person_name matches.
- `search=SARL` — 6,553 hits.
- `search=24856` (a real file number, as text) — 0 hits, confirms file
  numbers aren't searchable this way.
- `search=zzzznonexistentxyz999` (garbage) — 0 hits, confirms the actor's
  `not_found` path fires correctly on a genuine no-match instead of
  crashing.
- No filter, `orderby=date&order=asc` — oldest record 1914-02-05; `desc`
  (default) — newest record 2026-08-26 at recon time.
- `after=2026-08-20T00:00:00` — 8 matches, all within the expected date
  window.

## Known limits

- No lookup by exact file number/registration number — only by name
  (company or owner) or by registration date range. This is a real
  limitation of ODPIC's own search index (title/person_name only), not a
  scraping gap.
- `addresses` is frequently blank, especially on sole-trader filings —
  reflects what ODPIC has on file, not a scraping gap.
- Historical filings (pre-1990s) are present in the feed but are sparser
  overall (e.g. some do not carry a `file_ser` or have unusual name
  formatting) — this actor does not special-case them; the flattener only
  fails loud (`UnexpectedShape`) if a row is missing `id`/`title` entirely.

## Diff cadence

Quarterly smoke test recommended — this is a live government WordPress
site; a plugin/theme migration could change the custom post type's REST
exposure or field names.
