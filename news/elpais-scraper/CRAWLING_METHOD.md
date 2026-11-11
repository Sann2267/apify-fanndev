# Crawling Method — El País (English Edition)

**Last verified:** 2026-08-25

## WAF

`english.elpais.com` shows **no active challenge**. `curl_cffi` `chrome124`
gets a clean 200 on the homepage, article pages, and the RSS feed -- no
challenge body, no 403.

`robots.txt` has a single `User-agent: * / Allow: /` group plus a long
list of individually named blocked-bots -- no Claude/GPTBot/anthropic-ai/
CCBot entry anywhere in the list.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

**Scope note:** this actor targets `english.elpais.com` (the dedicated
English-language edition) specifically, not the main Spanish site
(`elpais.com`), which was never screened and is known in the real world to
run a metered subscription paywall for its Spanish-language readers.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://english.elpais.com/<section>/<date>/<slug>.html`

The page emits 4 ld+json blocks (a `WebPage` graph, the article record, a
`SiteNavigationElement` list, and an `ItemList`) -- the extractor scans all
blocks and picks the one whose `@type` **contains** `"NewsArticle"` (the
field is an array here, e.g. `["NewsArticle", "Article",
"ReportageNewsArticle"]` or `[..., "OpinionNewsArticle"]`, not a bare
string like on tass.com).

Unlike TASS, this block **does carry a full `articleBody`** -- confirmed
matching (same paragraph text, same trailing newsletter-signup CTA
sentence) against the HTML `div.a_c[data-dtm-region="articulo_cuerpo"] > p`
render across 8 sampled articles, so ld+json is used directly as the
primary (and only) body source, per the JSON-LD-first extraction priority
-- no HTML fallback needed while it keeps agreeing with the rendered page.

`author`/`publisher` can arrive as a dict, a list of dicts, or a bare
string -- normalized to a comma-joined name string via `_flatten_names`.

### 2. Latest headlines — `S2-rss`

`GET https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada`

Standard RSS 2.0 with Media RSS + Dublin Core extensions:
`title`/`link`/`guid`/`pubDate`/`description`/`dc:creator`/`category*`/
`media:content`. Lives on a separate `feeds.elpais.com` subdomain
(Varnish-fronted) -- only `/robots.txt` on that subdomain 403s, which is
irrelevant since the feed endpoint itself returns a clean 200.
`description` is a short teaser only, not full article text.

## Paywall behavior

`isAccessibleForFree` is present on every sampled article and was `True`
on all 8 samples across `usa`/`international`/`technology`/`society`/
`opinion`/`climate`/`eps`/`economy-and-business` sections -- the English
edition appears to be fully open-access, unlike EL PAÍS's Spanish-language
metered paywall. The `_paywalled` output flag is still derived defensively
from the real `isAccessibleForFree` field (never hardcoded `False`), so a
subscriber-only article encountered later would be flagged correctly
instead of silently passed off as free.

## Known limits

- 404s are real HTTP 404s (verified with a synthetic out-of-range article
  slug) -- no soft-404 behavior observed.
- `description` in `latest` mode is a teaser, not the full article body --
  use `article` mode against `link` for full text.
- Only the English edition was sampled; behavior on the main Spanish site
  (`elpais.com`) was not verified and is expected to differ (real-world
  metered paywall).

## Diff cadence

Quarterly smoke test recommended.
