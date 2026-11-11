# Crawling Method — New York Post

**Last verified:** 2026-08-24

## WAF

None detected. `nypost.com` returns 200 on homepage, article pages, and the
site-wide RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck` markers, no challenge body.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile).

## Data sources

### 1. Article pages — `S1-html` (JSON-LD metadata + HTML body, both required)

`GET https://nypost.com/<year>/<month>/<day>/<section>/<slug>/`

This site is a **hybrid** case, unlike most of the portfolio's news actors:

- The page emits one `application/ld+json` `NewsArticle` block with
  `headline`, `datePublished`, `dateCreated`, `articleSection`, `author`
  (array of `Person`), `image`, `keywords`, `video`, and a `publisher`
  object — but **no `articleBody`**.
- The WordPress REST API (`/wp-json/wp/v2/posts?...`) is locked down,
  returning `401 {"message":"Invalid or missing API key."}` — so there is no
  JSON source for the body text either.
- `__NEXT_DATA__` is absent (not a Next.js site).

Full article text is therefore pulled from **HTML**: direct-child `<p>` tags
of `div.single__content.entry-content`, iterated until the first `<hr>` tag
(which marks the end of the article body and the start of a "Download the
app, follow us on social" footer block — confirmed by inspecting 3 sampled
articles, always the same boundary marker). Bare `<p>` tags (no `class`
attribute) are the real body paragraphs; `<p>` tags carrying a `class`
(`inline-module__cta`, `newsletter-form__error`) are newsletter-signup CTAs
injected inline and are skipped. Figures, asides, and other block types are
ignored by construction (only `<p>` is collected).

The two sources are merged into one record: JSON-LD dict spread first, then
`articleBody` from HTML overwrites/adds the key.

**Quirk — regional sub-brand publisher metadata:** several articles under
`/us-news/` and `/business/` returned `publisher.name: "California Post"`
(with `parentOrganization.name: "New York Post"`) instead of `"New York
Post"` directly. This appears to be a geo/section-based sub-brand the
publisher runs on the same `nypost.com` domain — passed through verbatim per
raw-passthrough convention, not normalized. Don't be surprised if
`publisher.name` varies by article; `parentOrganization` (when present)
reliably points back to "New York Post".

No paywall marker (`isAccessibleForFree`, `.paywall` cssSelector, etc.) was
observed on any of the 4 articles sampled (us-news, business ×2, sports
categories not tested). NY Post does have some "NYP+" premium-labeled
content in the browser UI, but no sampled article in this recon exposed a
truncation signal in the extracted HTML — worth re-checking if an NYP+-
tagged URL is specifically targeted later (see Known limits).

### 2. Latest headlines — `S2-rss`

`GET https://nypost.com/feed/`

Standard WordPress RSS 2.0 feed, 22 items per fetch, mixed sections (us-news/
sports/opinion/business observed in one sample). Fields: `title`, `link`,
`guid`, `pubDate`, `description`, and `dc:creator` (byline, WordPress
namespace extension — mapped to `creator`). No `<category>` tags present in
this feed (checked raw XML directly), so no `categories` field is emitted.

## Paywall behavior

No paywall enforcement observed in this recon (see quirk note above). Treat
as open-access for now; re-verify periodically, and specifically test an
NYP+-labeled article if one is identified, since the CSS class
`single--exclusive-article-disabled` (seen on the `<article>` tag on all
sampled pages) implies an exclusive-article paywall *feature* exists on this
theme even though it wasn't active on any sampled URL.

## Known limits

- Author bios are minimal in JSON-LD (`name` + `URL` to author page only, no
  email/jobTitle like LA Times).
- HTML-based body extraction is inherently more fragile than JSON-LD/JSON —
  if WordPress theme markup changes (`div.single__content.entry-content`
  class list, or the `<hr>` boundary marker), `UnexpectedShape` will fire.
  This is the intended fail-loud behavior per portfolio convention.
- No section-specific RSS feeds were tested; only the site-wide feed is
  wired up.

## Diff cadence

Quarterly smoke test recommended. In addition to the standard
`test_local.py` check, specifically re-verify the `<hr>` boundary and the
bare-`<p>`-vs-classed-`<p>` filter still separate body text from CTAs
correctly — this is the most fragile part of this actor (HTML structure, not
JSON-LD) compared to the rest of the news-scraper portfolio.
