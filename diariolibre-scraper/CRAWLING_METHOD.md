# Crawling Method — Diario Libre

**Last verified:** 2026-08-26

## WAF

`diariolibre.com` shows **no active challenge**. `curl_cffi` `chrome124` gets
a clean 200 on the homepage (~460 KB, `Microsoft-IIS/10.0` server header, no
`cf-ray`/`cf-mitigated`/`x-datadome-cid`/`x-akamai-*` header, no
`_px3`/`_pxhd`/`_abck`/`__cf_bm` cookie), article pages (both `actualidad`
and `opinion` sections sampled), `/sitemap.xml`, `/sitemapnews`, and
`/feed/portada.xml` — no challenge body, no 403, no body markers from the
`waf-triage.md` list.

`robots.txt` is a single `User-agent: *` group — **no separate
Claude/ClaudeBot/Claude-Web/Claude-User/Claude-SearchBot/anthropic-ai group
exists at all**, so the multi-user-agent-group parser bug flagged in the
research doc (several `User-agent:` lines sharing one `Disallow:` block) does
not apply here — there's only one group to parse:

```
User-agent: *
Disallow: /xstatic/
Disallow: /XStatic/

Sitemap: https://www.diariolibre.com/sitemap.xml
Sitemap: https://www.diariolibre.com/sitemapnews
```

Neither disallowed path (`/xstatic/`, `/XStatic/`, static-asset directories)
affects article URLs, `/feed/portada.xml`, or `/sitemapnews`.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://www.diariolibre.com/<section>/<subsection>/<yyyy>/<mm>/<dd>/<slug>/<id>`

The page emits exactly **one** `<script type="application/ld+json">` tag,
but unlike tass.com/eluniversal.com.mx (bare `NewsArticle` dict) or
clarin.com/gulfnews.com (several separate `<script>` tags), it's a single
`{"@context": "https://schema.org", "@graph": [...]}` envelope holding three
nodes: `NewsMediaOrganization`, `WebSite`, and `NewsArticle`. The extractor
walks the `@graph` list (falling back to treating the whole payload as a
list or a bare dict, in case a different template ever drops the wrapper)
and picks the node whose `@type` is `NewsArticle`.

That node **carries `articleBody` directly** — full text, confirmed
non-empty and consistent across 3 sampled articles (a straight news piece,
a macroeconomics/currency piece, and an `/opinion/` column) — plus
`headline`, `alternativeHeadline`, `description`, `keywords` (comma-
separated string with a trailing comma, e.g.
`"Ministerio de Educación,estudiantes afectados,...,"` — split and
empty-filtered), `image` (a single `ImageObject` dict), `datePublished`,
`dateModified`, `articleSection` (comma-joined string, e.g.
`"actualidad,educacion"` or `"opinion,en-directo"` — kept as the raw string,
not split, since it reads as one taxonomy path), `author` (a single
`Person` dict — `{"name": ..., "url": ...}`, no multi-byline array
observed in either the news or opinion sample), `publisher` (`Organization`,
always `"Diario Libre"`), `mainEntityOfPage.@id` (the canonical URL), and
`inLanguage` (`"es"`).

**No `isAccessibleForFree` field at all** on any sampled `NewsArticle` node
(news or opinion) — this is different from kyivpost.com/clarin.com, which
carry the field either always-true or genuinely mixed. Combined with zero
"suscriptores"/"suscríbete"/"premium"/paywall-badge hits anywhere in the raw
HTML across all samples, the site appears to have no metering/paywall
mechanism at all, so the field is simply omitted from the output rather than
fabricated as `null` or assumed `true`.

**Quirk — not a data-corruption bug, but worth flagging given the
clarin-scraper precedent:** every text field inside the ld+json
(`headline`, `alternativeHeadline`, `description`, `keywords`,
`articleBody`, `author.name`) contains **literal un-decoded named HTML
entities embedded directly in the JSON string value** — e.g. the raw JSON
reads `"headline": "Denuncian retraso en reconstrucci&oacute;n..."`, with
the literal six characters `&oacute;` inside the string, not a JSON escape
(`json.loads` already resolves `\uXXXX`/`\n`/etc. — this is a separate,
additional layer the CMS writes on top). Left as-is, every accented
character in Spanish text would render as its HTML entity code instead of
the real character. A second pass of `html.unescape()` is applied to every
text field before it's returned, confirmed to correctly restore `ó`, `á`,
`ñ`, `é`, `í`, `ú`, etc.

**Explicitly checked for the clarin-scraper-style digit-corruption bug**
(commas silently stripped from numbers inside `articleBody`, e.g. "1,8%"
→ "18%") on a currency/macroeconomics article with several thousands-
separated figures — `"6,716 millones de dólares"`, `"3,276.5 millones"`,
`"8,745.7 millones de dólares"`, `"6,291.3 millones"`, `"61.65 pesos"`,
`"4.97 pesos"` — **all intact, no digit-grouping or decimal-point
corruption found**. This CMS's ld+json `articleBody` is safe to use
directly, unlike Clarín's.

If `articleBody` is ever missing or empty from the ld+json (not observed in
any of the 3 samples — defensive fallback only), the extractor falls back
to `<meta name="ArticleText" content="...">`, a meta tag independently
present in the page `<head>` that mirrors the same HTML-entity-escaped full
text (confirmed present alongside `<meta name="ArticleAuthors">` and
`<meta name="ArticleCategories">` on the sampled pages). No CSS-selector
HTML body container was needed as a fallback because none of the visible
`<article>` DOM actually renders the paragraph text server-side — the
front-end hydrates the body client-side via JS, so the only HTML-level
fallback available is that meta tag, not a `<div>`/`<p>` scrape.

### 2. Latest headlines — `S2-rss`

`GET https://www.diariolibre.com/feed/portada.xml`

A custom, WordPress-adjacent RSS 2.0 feed (`xmlns:media` and `xmlns:atom`
declared on the root `<rss>` tag, no `dc:` namespace). Confirmed **28
items**, no pagination parameter found — noticeably smaller than
kyivpost.com's 100-item `/feed`, so `latest` mode can legitimately return
fewer records than `limit` asks for; this is normal feed size, not a bug.
`/feed/rss.xml`/`/rss.xml`/`/rss`/`/feed` (bare) were probed and either
404'd or redirected elsewhere — `/feed/portada.xml` is the one confirmed
working front-page feed (a 301 redirect from `/feed` also resolves to it).

Each `<item>` carries:
- `title`/`link` — as expected.
- `guid` — a **UUID**, not the numeric id embedded in the article URL
  (e.g. `guid = "83414514-018d-43dc-8790-d84c11c9e926"` for an article
  whose URL ends in `/3638691`) — the two are unrelated identifiers, kept
  as separate raw fields.
- `pubDate` — **not valid RFC-822** (uses the Spanish month abbreviation
  `"Ago"` instead of the required English `"Aug"`, e.g.
  `"Tue, 25 Ago 2026 10:39:00 GMT"`) — kept as the raw string per
  passthrough; downstream consumers relying on a strict RFC-822 parser will
  need a locale-aware date parser instead.
- Several repeated `<category id="..." vn="..." vid="..." vurl="...">`
  tags, one taxonomy group per `vn` value: `"Categorias"` (section, e.g.
  `"Actualidad"`), `"Subcategorias"` (subsection, e.g. `"Educación"`),
  `"Autores"` (byline — this feed has no `<dc:creator>`/`<author>` tag at
  all, so author comes from here instead), `"Lugares"` (a single place
  tag, e.g. `"Santiago"`), `"Temas"` (topic tags, repeatable, 1-6 observed
  per item), and `"PrincipalTema"` (the lead/primary topic tag, a subset of
  the `"Temas"` set). The extractor groups all `<category>` tags by their
  `vn` attribute and maps each group to a same-named output field
  (`category`, `subcategory`, `author`, `place`, `topics`,
  `principalTopic`).
- `<description readingtime="N"><![CDATA[...]]></description>` — **the
  CDATA payload is itself the FULL article body as HTML**
  (`<p>`/`<strong>` markup), not a short teaser like kyivpost.com's or
  gulfnews.com's `/feed` — confirmed on the lead item: the CDATA content
  (5,122 chars of HTML) covers the exact same ground as that same
  article's ld+json `articleBody` (2,865 chars of plain text), just with
  markup and a few extra structural breaks. This means `latest` mode alone
  can deliver complete article text without a second request to the
  article page. `readingtime` (whole minutes) is surfaced as
  `readingTime`.
- `<media:content medium="image" width="..." height="..." url="...">` with
  a nested `<media:title>` — used for `image`/`imageCaption`.

**Encoding note (corrected 2026-08-26 after a live-cloud smoke test caught
it):** the CDATA content is written as raw UTF-8 directly (no entity
escaping at all inside CDATA), and most non-CDATA element text (titles,
category names) uses **numeric** XML character references (`&#243;` for
`ó`) that `lxml`'s XML parser decodes correctly on its own. But some
titles carry a **double-escaped** ampersand-entity sequence in the raw
feed — e.g. the literal bytes `&#38;#37;` (`&#38;` is the numeric ref for
`&`, so a single XML-parse pass only resolves it to the literal text
`&#37;`, leaving the `%` still entity-encoded). Confirmed on a live title,
`"...hasta el 50 &#37; a productos..."`, that survived one parse pass and
reached the dataset un-decoded on the first Apify cloud run of this actor
(2026-08-26). Fix: run `title`/`category`/`subcategory`/`author`/`place`/
`topics`/`principalTopic`/`imageCaption` through the same `_unescape()`
(`html.unescape()`) helper already used on the ld+json path — matches the
double-escape pattern documented elsewhere in this portfolio for
`inquirer-scraper`. The one cosmetic artifact found: `get_text(" ",
strip=True)` on the CDATA's `<p>` tags inserts a stray space before
punctuation when a `<strong>word</strong>` tag is immediately followed by a
comma/period text node (e.g. `"Padres , madres ,"`) — fixed with a
`re.sub(r"\s+([,.;:!?])", r"\1", text)` post-pass.

The Google News sitemap (`/sitemapnews`, advertised in `robots.txt`,
`news:title`/`news:publication_date`/`news:keywords` per `<url>` entry, a
flat non-paginated list covering roughly the last 24-48h) was also
confirmed working end-to-end and would be a viable fallback, but
`/feed/portada.xml` was chosen as the primary `latest`-mode source because
it already carries the full article body plus richer taxonomy (place,
per-article reading time, media caption) in one request. Note `/sitemap.xml`
itself (also advertised in `robots.txt`) is a **sitemap index** of monthly
archives (`/sitemapnoticias/202608`, etc.), not a flat "latest" feed — don't
confuse it with `/sitemapnews`.

## Paywall behavior

**None observed.** No `isAccessibleForFree` field anywhere in ld+json
(news or opinion sections), and no "suscriptores"/"suscríbete"/"premium"/
"Fondo Blanco"/paywall-badge/login-required string found in the raw HTML of
any of the 3 sampled article pages. Diario Libre appears to be fully
open-access at the HTTP layer.

## Known limits

- `/feed/portada.xml` carries only ~28 items at a time — `latest` mode may
  return fewer records than `limit` requests; use `article` mode against
  individual `link`s (or `/sitemapnews`) if a larger backlog is needed.
- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  id/slug, ~118 KB generic error page) — no soft-404 behavior observed.
- `pubDate` in latest mode is not standards-compliant RFC-822 (Spanish
  month abbreviation) — parse with a locale-aware date library, not a
  strict RFC-822 parser.
- `author` in article mode assumes a single `Person` object per the 2
  news + 1 opinion samples — no multi-byline array was observed, but if
  the CMS ever emits one on a different template, `_author_name()` already
  handles a list the same way the rest of the portfolio does.
- Only 3 articles sampled in depth (2 `actualidad` news pieces spanning
  education and macroeconomics topics, 1 `opinion` column) plus a
  synthetic 404. All three shared the identical `@graph`-wrapped ld+json
  shape. A structurally different template (live-blog, video feature,
  photo gallery, or a paywalled premium section if one exists elsewhere on
  the site) was not sampled.

## Diff cadence

Quarterly smoke test recommended.
