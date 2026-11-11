# Crawling Method — Philippine Daily Inquirer

**Last verified:** 2026-08-24

## WAF

`inquirer.net` (WordPress-based, spans multiple subdomains --
`newsinfo.`, `lifestyle.`, `business.`, etc.) shows **no active challenge**.
`curl_cffi` `chrome124` gets a clean 200 on homepage, article pages across
subdomains, and the site-wide RSS feed -- no challenge body, no 403.

`robots.txt` checked at `www.inquirer.net/robots.txt` (441 bytes) -- no
Claude/GPTBot/anthropic-ai disallow anywhere in the file.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld`

`GET https://<subdomain>.inquirer.net/<id>/<slug>` (subdomain varies by
vertical: `newsinfo`, `lifestyle`, `business`, `sports`, etc. -- all confirmed
to share the same template/ld+json shape)

A single `NewsArticle` ld+json block carries `headline`, `description`,
`datePublished`, `dateModified`, `author` (`{"@type": "Person", "name":
..., "url": <byline page>}`), `image`, `publisher`, `copyrightHolder` --
and, unusually for this portfolio, **it DOES include `articleBody`
directly**. Two site-specific quirks must be handled to use it, though:

1. **The raw ld+json text contains literal unescaped control characters**
   (real newline bytes inside a JSON string value, not `\n` escapes) --
   Python's `json.loads` raises `"Invalid control character at..."` under
   default `strict=True` parsing. Fix: parse with `json.loads(text,
   strict=False)`, which tolerates this.
2. **`articleBody`'s value is double HTML-entity-escaped raw WordPress
   Gutenberg block markup** -- e.g. the true underlying content is
   `<!-- wp:paragraph --><p>MANILA, Philippines...</p><!-- /wp:paragraph -->`,
   but the JSON string holds
   `&amp;lt;!-- wp:paragraph --&amp;gt;&amp;lt;p&amp;gt;MANILA...`. This
   requires **`html.unescape()` called twice** (once to turn `&amp;lt;`
   into `&lt;`, again to turn `&lt;` into the real `<` character) before
   the result is valid HTML. Parsing it with BeautifulSoup and collecting
   only `<p>` tags then naturally skips `<figure>`/`<figcaption>` blocks
   (image credit captions embedded mid-article, e.g. "Sen. Panfilo Lacson
   —File photo by Niño Jesus Orbeta/Inquirer" -- these are not real body
   text and are correctly excluded since they aren't `<p>` elements).

`description` (used directly, no unescape needed) is oddly composed: on
sampled articles it concatenates the lead image's caption text with the
opening paragraphs of the body (e.g. "Sen. Panfilo Lacson —File photo
by... \n\n\n\nMANILA, Philippines — Public officials..."). This is passed
through verbatim as the site's actual `description` value -- not a parsing
bug, just how Inquirer's own auto-generated meta description happens to be
built.

### 2. Latest headlines — `S2-rss`

`GET https://www.inquirer.net/fullfeed`

Site-wide feed spanning all verticals/subdomains, standard RSS 2.0 with
`media:content` (lead image). `description` is single HTML-entity-escaped
(`&lt;br/&gt;`, `&lt;a href=...&gt;`) and ends with a literal boilerplate
sentence, `"...Keep on reading: <a href="...">Title</a>"` -- the extractor
unescapes and strips tags (one unescape pass here, not two -- this is a
different, single-escaped field from the article-page `articleBody`), but
deliberately keeps the "Keep on reading: Title" text since it's real
content the feed generates, not noise to discard.

## Paywall behavior

None observed. Inquirer.net is free, ad-supported -- no `isAccessibleForFree`
field or truncation marker exists in the ld+json vocabulary, and the full
`articleBody` was present and un-truncated on the sampled article.

## Known limits

- Only 1 article sampled in depth (hard-news, `newsinfo` subdomain). Other
  verticals (`lifestyle`, `business`, `sports`, `technology`) were only
  spot-checked via the RSS feed's link list, not deep-crawled -- if one of
  them uses a materially different ld+json shape, `UnexpectedShape` will
  raise rather than silently returning an empty body.
- The double-unescape step is specific to how WordPress + this site's
  particular ld+json plugin serializes Gutenberg block content. If Inquirer
  changes CMS or plugin, this could become single-escaped (or not escaped
  at all) -- the extractor would then either mis-render `articleBody` as
  literal tag soup (if now single-escaped) or raise `UnexpectedShape` (if
  no `<p>` tags survive over-unescaping); worth a quick smoke-test diff if
  output ever looks wrong.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check the
double-unescape assumption on `articleBody` -- this is the most fragile
part of this actor and the one most likely to silently break if Inquirer's
WordPress export pipeline changes.
