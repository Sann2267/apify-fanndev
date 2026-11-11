"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-27): Djibouti's official company/business registrar
is **ODPIC** (Office Djiboutien de la Propriete Industrielle et Commerciale),
an autonomous government agency under the Ministry of Commerce that runs the
"Registre du Commerce et des Societes" (RCS) and also sits inside the
"Guichet Unique" one-stop business-registration desk. Two candidate "Guichet
Unique" marketing domains were found (`www.guichet-unique.dj` -- timed out
on every request, likely dead/misconfigured DNS-but-no-listener; and
`guichet-unique-djib.com` -- alive, but a pure informational WordPress site
with no search tool). ODPIC's own site, **`odpic.dj`**, is what actually
publishes registry data online, and is what this actor scrapes.

`robots.txt` (`https://odpic.dj/robots.txt`) is the stock unmodified
WordPress default:

    User-agent: *
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php
    Sitemap: https://odpic.dj/wp-sitemap.xml

One `User-agent: *` group, no mention of Claude/ClaudeBot/anthropic-ai/
GPTBot/AI crawlers anywhere in the literal text, and no `Disallow` covering
`/wp-json/` (the only path this actor touches besides the root). API
responses do carry an `X-Robots-Tag: noindex` header -- this only asks
search engines not to index the JSON endpoint in their index; it is not a
crawl restriction and does not mention any specific bot.

## The API: ODPIC publishes its own RCS filings as a public WordPress CPT

ODPIC's site runs a custom post type, `publication_registre` ("Publications
Registres"), used to publish every new Registre du Commerce et des Societes
(RCS) filing -- effectively a public, chronological gazette of company/
business-name registrations, going all the way back to entries from 1914
(pre-independence colonial-era filings appear to have been migrated in
alongside current ones). It is registered with `show_in_rest: true`, so it
is fully queryable through WordPress's standard public REST route with
**no login, no nonce, no CAPTCHA**:

    GET https://odpic.dj/wp-json/wp/v2/publication_registre
        ?search=<free text -- matches company/person name (title), NOT file_nbr>
        &after=<ISO 8601 -- registration/post date lower bound>
        &before=<ISO 8601 -- registration/post date upper bound>
        &orderby=<date|title|relevance> (default: date)
        &order=<asc|desc> (default: desc, i.e. newest filings first)
        &page=<1-based>&per_page=<1-100>

Confirmed during recon (2026-08-27, `curl_cffi` chrome124, no proxy):
- 19,602 total records at recon time (`X-WP-Total` header), 197 pages at
  `per_page=100` (WordPress's own hard per_page cap -- `per_page=150` is
  rejected with HTTP 400 `rest_invalid_param`).
- `search=` matches against the post title (company/establishment name) AND
  the custom `person_name` field (e.g. `search=MOHAMED` -> 827 hits spanning
  both `ETABLISSEMENT MOHAMED TAHA SAID SARL` and person names like
  `WAEL MOHMAED TARECHE`). It does **not** match `file_nbr`/`file_ser`
  (searching the literal file number `24856` returns zero hits) -- there is
  no way to look up one exact filing by its registration number through this
  route; browsing by name or date range is the only supported lookup.
- `after`/`before` (WordPress's standard post-date range filters) work
  against the `date` field, which was confirmed to always equal
  `registration_date`/`filing_date` on every sample checked.
- Default order (no `orderby`/`order` given) is newest-first by date --
  confirmed the first few unfiltered rows are 2026-08-26, 2026-08-24,
  2026-08-24, matching a `orderby=date&order=desc` request.
- 15 rapid sequential requests (different pages) all returned HTTP 200 with
  no slowdown or block -- no rate limiting, no WAF/CAPTCHA markers
  (`Just a moment`, `cf-mitigated`, `captcha-delivery.com`, etc.) observed
  anywhere. Plain `nginx/1.18.0` + `PHP/8.0.30`.
- No separate per-entity detail route is needed -- the list endpoint already
  returns every field ODPIC publishes per filing (registration/filing dates,
  file number/series, main owner's person number and name, address, and a
  free-text `disclaimers` field that in practice holds the declared share
  capital for company filings, e.g. `"10 000 FDJ"`, and is empty for many
  sole-trader filings). `GET /wp-json/wp/v2/media?parent=<id>` (checking for
  an attached scan/PDF of the filing) returned an empty list on every sample
  tried -- no attachments are published alongside these records.

## Field flattening (deliberate, documented)

The raw `wp/v2` response wraps each filing in generic WordPress CMS
plumbing (`guid`, `content` -- always empty for this CPT, `template`,
`class_list`, `_links`, duplicate `modified`/`modified_gmt` timestamps that
were confirmed identical to `date`/`date_gmt` on every sample, since these
posts are never edited after publishing). This actor strips that
hypermedia/CMS scaffolding and keeps only the substantive registry fields
verbatim (`file_nbr`, `file_ser`, `registration_date`, `filing_date`,
`main_owner_person_nbr`, `person_name`, `addresses`, `disclaimers`), plus
`id`/`slug`/`link`/`date` for identification, and unwraps `title.rendered`
to a plain `title` string (the same unwrap this portfolio's news actors
already do for WordPress `title.rendered` fields). No field is renamed or
reinterpreted beyond that -- per `.ai/CLAUDE.md` principle 5.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://odpic.dj"
API_PATH = "/wp-json/wp/v2/publication_registre"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/publication-registre/",
}

# Server-side hard cap confirmed during recon (per_page=150 -> HTTP 400).
PER_PAGE = 100

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0

# Safety cap on page depth per query/browse job -- keeps an unfiltered
# "latest" browse or a very broad search term from paging through the
# entire ~197-page directory when the caller only asked for a handful of
# records but set maxResults too high by mistake.
MAX_PAGES_PER_JOB = 100
