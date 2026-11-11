# Crawling Method — El Universal (Mexico)

**Last verified:** 2026-08-24

## WAF

`eluniversal.com.mx` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on homepage, article pages, and the Arc outbound news
sitemap -- no challenge body, no 403.

`robots.txt` only blocks legacy offline-downloader tools (`HTTrack`,
`WebZIP`, `wget`, `Teleport`, etc.) and `Bytespider` -- **no Claude/GPTBot/
anthropic-ai disallow of any kind**. Notably, `Google-Extended` is grouped
in the *same* `User-agent:` block as `Googlebot`/`Googlebot-News` (which
only disallows `/files/` and `/descuentos/`, same as everyone else in that
group) rather than given its own outright `Disallow: /` -- i.e. this site
does not even opt out of Google's AI-training crawler, let alone Claude's.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.eluniversal.com.mx/<section>/<slug>/`

El Universal runs on **Arc Publishing** (same CMS family as
`gulfnews-scraper`/`thenational-scraper`). `BreadcrumbList` +
`NewsArticle` ld+json blocks carry rich metadata (`headline`,
`description`, `author`, dates, `isAccessibleForFree`, `keywords`,
`image`, `dateline`) but **no `articleBody` field** -- body text is
scraped from HTML.

**Quirk:** the page's `<article>` tag contains **zero `<p>` tags** on this
CMS instance -- naively selecting `soup.find("article")` would silently
yield an empty body. The real content container is `<div
class="content-story">`, found by walking up the DOM tree from a known
body paragraph during recon. Every `<p>` tag inside it is joined, with two
kinds of boilerplate filtered out:

- Literal `"[Publicidad]"` ad-slot placeholder paragraphs -- several
  scattered throughout a single article (sampled article had 4).
- A WhatsApp-channel promo CTA paragraph starting with `"Únete a nuestro
  canal ¡EL UNIVERSAL ya está en Whatsapp!..."` -- appears once near the
  end of every article.

Inline `"Lee también <related headline>"` cross-link paragraphs are
**deliberately left in** as real body text -- they're genuine editorial
content (a link to a related story embedded mid-article), not UI chrome,
matching the treatment of the dek paragraph in `independent-scraper`.

`author` can be a list or a single dict depending on story (wire vs.
staff-bylined) -- handled the same way as `thenational-scraper`/
`koreatimes-scraper`. `keywords` arrives as a comma-separated string, split
into a list.

`isAccessibleForFree` was present on the sampled article -- passed through
as-is; no premium/metered article was sampled in this recon, so paywall
truncation behavior is unverified (El Universal does have a subscriber
tier for some content in production).

### 2. Latest headlines — `S2-sitemap`

`GET https://www.eluniversal.com.mx/arc/outboundfeeds/news/?outputType=xml`

Arc Publishing's outbound rolling news sitemap, advertised via `Sitemap:`
in `robots.txt` (one of ~20 sitemap variants listed -- per-category
archives like `nacion`, `mundo`, `deportes`, plus a `horoscopo` sitemap and
a `consultas` index -- this is the cross-section rolling feed, 100 entries
at time of writing). `news:title` and `news:keywords` are wrapped in
`<![CDATA[...]]>` -- unlike `independent-scraper`'s `image:loc` or
`koreatimes-scraper`'s `news:title`, **no escaped entities were found
inside these CDATA blocks in samples** (titles with literal ampersands or
apostrophes weren't present in the sampled batch), so no extra
`html.unescape()` pass is applied here. `image:loc`/`image:caption` are
**not** CDATA-wrapped, so their `&amp;` query-string separators are
correctly XML-decoded by the parser already.

## Paywall behavior

Not directly observed -- the one sampled article was fully free with
complete body text. `isAccessibleForFree` is passed through for downstream
filtering if premium content is encountered in production.

## Known limits

- Only 1 article sampled in depth (a Sinaloa state-politics story).
  Opinion columns, sports, and entertainment sections were not verified
  for the same `div.content-story` container or boilerplate strings.
- The ad-placeholder and WhatsApp-CTA filters are maintenance points: if
  El Universal changes the wording of either, that text would leak into
  `articleBody` until the filter strings are updated (same trade-off as
  `independent-scraper`'s boilerplate-prefix list).
- 404s are real HTTP 404s (verified with a synthetic slug) -- no soft-404
  behavior observed.

## Diff cadence

Quarterly smoke test recommended.
