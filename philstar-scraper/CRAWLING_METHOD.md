# Crawling Method — Philippine Star

**Last verified:** 2026-08-24

## WAF

`philstar.com` shows **no active challenge**. `curl_cffi` `chrome124` gets a
clean 200 on homepage, article pages, and the site-wide RSS feed -- no
challenge body, no 403.

`robots.txt` is minimal (226 bytes: `User-agent: *` / `Petalbot` disallowing
`/admin/`, `/images/profile/`, and a handful of legacy `.php` paths) --
**no Claude/GPTBot/anthropic-ai disallow anywhere**.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.philstar.com/<section>/<yyyy>/<mm>/<dd>/<id>/<slug>`

A single `NewsArticle` ld+json block carries `headline`,
`alternativeHeadline`, `description`, `datePublished`, `dateModified`,
`author`, `articleSection`, `keywords` (a plain string, not an array --
passed through verbatim per portfolio convention), and `image`. **No
`articleBody` field.**

**Important quirk:** the `description` field value is itself
**HTML-entity-escaped HTML**, not plain text --
`"&lt;p&gt;Public officials who orchestrate...&lt;/p&gt;\r\n"`. Naively
reading it verbatim leaks literal `&lt;p&gt;`/`&lt;/p&gt;` noise into the
dataset. The fix requires two steps in the right order: `html.unescape()`
first (to turn the escaped entities into real `<p>` tags), **then** parse
the result with BeautifulSoup to strip the now-real tags. Doing it in the
other order (parsing the raw escaped string directly) doesn't work --
HTML parsers decode entities into literal text characters, they don't
re-tokenize decoded text as new tags, so `get_text()` on the raw string
would still return the visible `<p>...</p>` wrapper as plain text.

Full body text: `div.article__content > p`, bare paragraphs. No ad
placeholders, stray empty tags, or other noise observed in samples --
simpler than most of this portfolio's HTML-extraction targets.

### 2. Latest headlines — `S2-rss`

`GET https://www.philstar.com/rss/headlines`

Standard RSS 2.0, exactly 10 items per fetch (site does not appear to
support a larger page size via query params -- not attempted further since
10 is sufficient for a "latest" feed). Fields: `title`, `link`, `author`
(present directly on the feed item -- unusual; most portfolio feeds only
carry byline on the article page itself), `guid` (`isPermaLink="true"`,
matches `link`), `pubDate`, `description` (a real teaser, HTML-entity
escaped inline `&nbsp;`/`&rsquo;` etc. which the XML parser decodes
transparently -- no `<p>` wrapper issue here since the RSS description is
genuinely plain text, unlike the ld+json field above).

## Paywall behavior

None observed. Philippine Star is free, ad-supported, general-audience
national news -- no `isAccessibleForFree` field or truncation marker
exists in the ld+json vocabulary, and no paywall overlay was found in
sampled HTML.

## Known limits

- Only 1 article sampled in depth (hard-news, Headlines section). If a
  different section (opinion, lifestyle, sports) uses a different body
  container class, this extractor would raise `UnexpectedShape` rather
  than silently return nothing.
- `keywords` is a single string field on this site (not a JSON array like
  some other portfolio targets) -- passed through as-is, no artificial
  splitting into a list.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check the
`description` double-encoding quirk -- if philstar ever fixes their ld+json
generator to emit plain text instead of escaped HTML, the `_clean_description`
unescape+strip step becomes a no-op (harmless) rather than a bug, so no
urgent action needed if/when that happens.
