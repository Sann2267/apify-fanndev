# Crawling Method — The Manila Times

**Last verified:** 2026-08-26

## WAF

`manilatimes.net` sits behind **Cloudflare** (CDN passthrough, `server:
cloudflare` header, no active JS challenge) plus a CloudFront edge in front
of that. `curl_cffi` `chrome124` gets a clean 200 on the homepage, article
pages across every section (News, Business, Sports, TMT Newswire), and the
site-wide RSS feed on every request made during recon (~25 requests) --
no challenge body, no 403, no captcha markers.

`robots.txt` (206 bytes) is `User-agent: *` only, disallowing `/ajax/*`,
`/*.pdf`, `/widget/*`, `*/page/*`, `/search*`, plus `Crawl-delay: 600`
(10 minutes) and two more crawl-delay-only blocks for `Marfeelman` and
`Petalbot`. **No Claude/GPTBot/anthropic-ai disallow anywhere**, and no
blanket `Disallow: /`. (Sibling outlet Manila Bulletin returned HTTP 403 at
the robots.txt fetch itself when screened elsewhere in this project --
Manila Times shows no such pattern; robots.txt and every sampled page
returned clean 200s.)

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. The 10-minute crawl-delay is noted but not auto-enforced by this
actor (consistent with portfolio convention of not throttling to
spec-only crawl-delay values); keep `maxConcurrency` modest in practice.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.manilatimes.net/<yyyy>/<mm>/<dd>/<section>[/<subsection>]/<slug>/<id>`

A single `NewsArticle` ld+json block carries `headline`, `description`,
`datePublished`, `dateModified`, `author` (`{"@type": "Person", "name": ...,
"url": <author page>}` -- wire-service reprints use the agency as the
author name, e.g. `"PR Newswire"`, `"Agence France-Presse"`),
`articleSection`, `keywords` (observed as an empty string on every sampled
article, not omitted), `image` (`ImageObject` with `url`/`width`/`height`),
`isAccessibleForFree`, and `genre`. It **does** include `articleBody`
directly, unusually for this portfolio -- but two quirks make the HTML
version preferable:

1. **The raw ld+json script text contains literal unescaped control
   characters** (real newline bytes inside a JSON string value) -- Python's
   `json.loads` raises `"Invalid control character at..."` under default
   `strict=True`. Fix: `json.loads(text, strict=False)` (same fix used in
   `inquirer-scraper`).
2. **`articleBody`'s JSON-LD value has no paragraph breaks** -- sentences
   from different paragraphs run directly together (e.g.
   `"...its logo.In a statement..."`), and its quotes/dashes are
   HTML-entity-escaped (`&ldquo;`, `&rsquo;`, `&mdash;`). Rather than try to
   reconstruct paragraph boundaries from this, the extractor pulls the body
   from HTML instead: `div.article-body > p`, joined with blank lines.
   Confirmed consistent across News, Sports, Business, and TMT Newswire
   (wire-service) article templates. A stray empty leading `<p>` appears on
   some wire-service reprints and is filtered out (`get_text(strip=True)`
   guard).
3. **`description` is separately quirky**: plain text, no tags, but
   HTML-entity-escaped on some articles (`"MANILA, Philippines &mdash; June
   Mar Fajardo..."`) and already-clean on others. `html.unescape()`d
   unconditionally (safe no-op when nothing to unescape).

### 2. Latest headlines — `S2-rss`

`GET https://www.manilatimes.net/latest/feed/`

Discovered via the site's own `/rss` landing page (`<title>RSS Feeds | The
Manila Times</title>`), which links ~35 category-specific feeds
(`/news/feed/`, `/business/feed/`, `/sports/feed/`, ...). `/latest/feed/`
is the broadest one: channel `<description>` self-identifies as `RSS Feed :
Latest News`, and sampled items span every section (News, Business, Sports,
World, Entertainment & Lifestyle, TMT Newswire). Standard RSS 2.0 with
`dc:creator`, `media:thumbnail`, and `media:content` namespaces, **50 items
per fetch** (vs. 10 on `philstar-scraper`/`inquirer-scraper`'s feeds).

**Notable quirk (a positive one):** the `<description>` CDATA block on each
`<item>` carries the **full article body** as real `<p>`-tagged HTML
(single HTML-entity-escaped inside the CDATA, e.g. `&ldquo;`), not just a
teaser sentence -- confirmed by comparing feed item length against the
matching article page's body. The extractor unescapes once and joins `<p>`
text with blank lines, so `latest` mode returns full-text records without
an extra per-article fetch. Sitemap/Google-News-sitemap paths
(`/sitemap.xml`, `/sitemap_index.xml`, `/news-sitemap.xml`, etc.) all 404 --
this site relies on RSS for machine-readable discovery, not sitemaps.

## Paywall behavior

None observed. `isAccessibleForFree: true` on every sampled article
(News, Business, Sports, wire-service TMT Newswire) -- Manila Times is
free, ad-supported, general-audience national news, consistent with the
other Philippine dailies in this portfolio.

## Known limits

- Sampled News, Sports, Business, and TMT Newswire (wire-service reprint)
  sections; Opinion/Entertainment & Lifestyle templates were only
  spot-checked via the RSS feed's link list, not deep-crawled. If one of
  them uses a different `div.article-body` shape, `UnexpectedShape` raises
  rather than silently returning nothing.
- `keywords` is consistently an empty string on every sampled article --
  unclear if any article ever populates it; passed through as-is either way.
- The site's own `/rss`, `/feed/rss`, `/arc/outboundfeeds/rss/` "feed-like"
  paths silently 200 with the **homepage HTML**, not XML or a 404 -- only
  the real `<slug>/feed/` pattern returns actual RSS. Any future
  URL-guessing here should check `content-type: text/xml`, not just status
  200.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check the JSON-LD
`articleBody` paragraph-break gap -- if Manila Times' CMS ever starts
emitting real paragraph breaks (e.g. `\n\n` or per-paragraph JSON-LD nodes)
in that field, the HTML-fallback approach becomes unnecessary complexity
(harmless either way, just worth simplifying) rather than a bug.
