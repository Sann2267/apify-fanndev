# Crawling Method — Uruguay Government Tenders (ARCE OCDS)

**Last verified:** 2026-08-27

## Target discovery

Uruguay's public procurement is regulated by **ARCE** (Agencia Reguladora
de Compras Estatales, created by Law 19.355 of 2015, under the Presidency
of the Republic). Every one of the 287+ state institutions that purchase
through the national system publishes on ARCE's single platform,
`www.comprasestatales.gub.uy` (formerly "Compras y Contrataciones
Estatales" / ACCE, the name used in this actor's original task brief --
still findable under that older name, the entity is now branded ARCE).
Confirmed via a live web search plus the platform itself, not a
tender-alert blog: `www.gub.uy/agencia-reguladora-compras-estatales/`
(the agency's own `.gub.uy` government profile page) and
`data.open-contracting.org/en/publication/43` (the Open Contracting
Partnership's own Data Registry, independently confirming ARCE as a
publisher).

Viewing tender/award data on `comprasestatales.gub.uy` needs **no account**
-- confirmed by direct fetch of the search pages
(`/consultas/`, `/consultas/buscar/...`), which return normal 200 HTML with
real listing content, no login redirect. (Registering to actually *bid* on
a tender is a separate, account-gated step via `proveedores.gub.uy` --
outside this actor's scope, and the "fine if only BIDDING requires login"
carve-out applies.)

## robots.txt -- a redirect quirk, not a policy block

`https://www.comprasestatales.gub.uy/robots.txt` does **not** serve robots
rules -- it returns a bare `301 Moved Permanently` to
`https://www.gub.uy/agencia-compras-contrataciones-estado` (the agency's
homepage, not robots.txt content), on every attempt, with or without
following the redirect. This is a routing quirk specific to that one path
on that one subdomain (every other path tested on
`www.comprasestatales.gub.uy`, including the real data endpoints used by
this actor, returns normal 200 content -- see below) -- not a deliberately
published `Disallow` policy, and there is consequently no robots.txt on
this specific host naming Claude/ClaudeBot/anthropic-ai or any other bot.

Since `comprasestatales.gub.uy` is itself one property of the broader
`gub.uy` government platform (the redirect target lands there), that
platform's own `https://www.gub.uy/robots.txt` was also checked directly
and confirmed clean: a standard Drupal robots.txt disallowing only
`/admin/`, `/user/login`, `/search/`, and similar internal/utility paths
under a single blanket `User-agent: *` group -- no bot-specific rule, no
blanket site-wide `Disallow: /`, and no mention of Claude, ClaudeBot,
anthropic-ai, or any AI-crawler name anywhere in the file.

## No WAF/TLS gate observed

Every endpoint this actor uses (`/ocds/rss`, `/ocds/rss/{year}/{month}`,
`/ocds/record/{id}`, and every release link returned by those) answered
with clean `200` responses to a **plain `curl` request with no TLS
impersonation, no browser-like headers, and no session/cookie handling at
all** during recon -- the simplest possible HTTP client. No challenge page,
no `403`, no rate-limit response was observed at any point. This actor
still uses a standard browser-like TLS profile (consistent with the rest of
this portfolio) as a baseline precaution, but no anti-bot layer was
actually identified on this target.

## The API -- a genuine, purpose-built public OCDS service

Confirmed via a live web search plus direct verification of every endpoint
below with real, current data (fetched 2026-08-27, i.e. today):
Uruguay/ARCE runs a dedicated **OCDS (Open Contracting Data Standard)**
service at `comprasestatales.gub.uy/ocds/*` -- not a reverse-engineered
internal admin grid. Three GET endpoints, all unauthenticated:

### 1. `/ocds/rss` and `/ocds/rss/{year}/{month}` -- release feed

```
GET https://www.comprasestatales.gub.uy/ocds/rss
GET https://www.comprasestatales.gub.uy/ocds/rss/2026/01
```

Returns RSS 2.0 XML, one `<item>` per **release event** (not per purchase --
a single purchase can have several: an initial tender call, amendments,
clarifications, and an eventual award all show up as separate items over
time). Each item's `<title>` carries `id_compra:<N>,release_id:<X>` as
literal text; `<link>`/`<guid>` give the direct release URL/ID;
`<category>` gives the event type. Confirmed live category values seen
during recon: `tender`, `tenderUpdate`, `tenderAmendment`,
`tenderCancellation`, `award`, `awardUpdate`.

- **Bare `/ocds/rss`** (no year/month): the newest **500** items
  platform-wide, newest first -- confirmed by counting `<item>` tags on a
  live fetch (exactly 500, every time).
- **`/ocds/rss/{year}/{month}`**: every item published in that single
  calendar month, newest first, **not capped at 500** -- a live fetch of
  `2026/01` alone returned **11,441** items. Both `year` and `month` are
  required together; year-only (`/ocds/rss/2025`) returns a live `404`.

This actor's `mode=list` uses one of these two windows (never paginates
across multiple months -- a single month already vastly exceeds this
actor's `maxResults` cap of 5000 in every case observed) and truncates
client-side to `maxResults`.

### 2. `/ocds/record/{id_compra}` -- purchase-level record package

```
GET https://www.comprasestatales.gub.uy/ocds/record/1367008
```

Returns a **linked** OCDS record package (a documented OCDS spec variant,
distinct from Ecuador SERCOP's compiled record used elsewhere in this
portfolio): `records[0].releases` is a list of `{url, date, tag}`
*references* to each release event for that purchase, not the release
content itself:

```json
{
  "records": [{
    "ocid": "ocds-yfs5dr-1367008",
    "releases": [{ "url": "http://www.comprasestatales.gub.uy/ocds/release/adjudicacion-1367008", "date": "...", "tag": ["award"] }]
  }]
}
```

**An unknown `id_compra` returns a live `404`** with a JSON error body
(`{"message":" El identificador de la compra especificado no se encuentra
en el sistema"}`) -- confirmed live -- handled as `RecordNotFound`, not
assumed to be a `200` empty shell (contrast Ecuador SERCOP, whose `record`
endpoint 200s with an empty response on an unknown ocid instead).

### 3. Release links (from `/ocds/rss` or `/ocds/record`) -- full content

Following any `url` returned by either endpoint above (e.g.
`/ocds/release/adjudicacion-1367008`, `/ocds/release/llamado-1314718`)
returns the full OCDS 1.1 release package: `buyer`, `parties` (with
`contactPoint` email/phone for the procuring entity), and either a
`tender` block (title, description, items, `tenderPeriod`,
`procurementMethod`/`procurementMethodDetails` in Spanish e.g. `"Concurso
de Precios"`, `"Compra Directa"`, `"Licitacion Publica"`) or an `awards`
block (`suppliers`, and `items[].unit.value.{amount,currency}` -- price is
per line item with no award-level total, unlike Ecuador SERCOP's
`awards[].value.amount`; this actor's own `totalAwardAmount` sums unit
price x quantity across every awarded item, documented as a same-actor
fold, not an upstream total). Currency is `UYU` (Uruguayan peso).

**An invalid/malformed release ID does not 404** -- it returns a live
`500` with a genuine upstream parsing error (`{"message":" Parametro
[changeType] no posee un valor identificado"}`), a server-side bug
triggered by an ID that doesn't match the expected `<eventType>-<id>[-<n>]`
pattern. This actor never constructs release IDs itself -- it only follows
`url` values returned verbatim by the RSS feed or the record endpoint, so
this bug is never actually triggered in normal operation, but is
documented here since a naive re-implementation guessing release-ID formats
would hit it.

`mode=detail` (and `fetchDetail: true` list rows) fetch `/ocds/record/{id}`
first, then follow **every** linked release sequentially (a small politeness
delay between links; purchases in this system carry a handful of release
links at most, never a long chain), and fold the results into one summary
record -- the same fold-across-releases pattern this portfolio's other OCDS
integrations use (Ecuador SERCOP, Nigeria NOCOPO, Tanzania NeST), since
ARCE's API, like those, has no server-side merged view either.

## Content negotiation quirk

Sending an explicit `Accept: application/json` header to the XML-only
`/ocds/rss*` endpoints produces a live `406 Not Acceptable` -- a real
content-negotiation response, not a block (confirmed: the exact same
request with no `Accept` header, or a generic `Accept: */*`, succeeds with
`200` and the expected RSS XML). This actor sends a generic `Accept: */*`
header on every request for this reason, since the same header value works
identically well on the JSON-returning `record`/release endpoints too.

## Reachability

Unlike Ecuador SERCOP's open-data host (unreachable from several outside
networks during that actor's own recon), every `comprasestatales.gub.uy`
endpoint used here answered normally from this session's own network with
a plain, non-impersonated HTTP client -- no country-specific residential
proxy pin was needed or applied. `proxyConfiguration` defaults to generic
Residential (no country pin), matching this portfolio's more common
default, as a light precaution rather than a confirmed requirement.

## Market check

Searched the Apify Store (via live web search, since Store search wasn't
directly browsable) for "uruguay tenders", "comprasestatales", and "ARCE"
before building -- no actor targeting Uruguay's procurement system was
found. Per this session's own task brief, the `scrapers_lat` seller cluster
(confirmed elsewhere in this portfolio's research to systematically own
Peru/SEACE, Colombia/SECOP, Mexico/CompraNet, Argentina/Comprar,
Paraguay/DNCP, and Chile/Mercado Publico) was checked specifically: their
public Apify listings include `paraguay-dncp-scraper` and `seace-scraper`
(Peru), confirming the known LatAm footprint, but **no Uruguay-targeting
actor appears in their portfolio** -- independently re-confirming the task
brief's own market check. Two adjacent LATAM aggregators noted in this
portfolio's Ecuador build (`iadb-tenders` by `foxlabs`, `licitaciones-latam`
by `karmic_mastodon`) do not list Uruguay among their covered countries
either.
