# Crawling Method — Channel NewsAsia (CNA)

**Last verified:** 2026-08-24

## WAF

`channelnewsasia.com` (Mediacorp, Singapore) shows **no active challenge**.
`curl_cffi` `chrome124` gets a clean 200 on homepage, article pages, and the
site-wide RSS feed -- no challenge body, no 403.

`robots.txt` is a standard Drupal-generated file (`Disallow: /admin/`,
`/search`, `/user/*`, `/api/*` for `User-agent: *`) with **no
Claude/GPTBot/anthropic-ai specific disallow** -- unlike several US outlets
screened in this batch (e.g. USA Today, The Hill, Politico all explicitly
disallow `ClaudeBot`/`Claude-Web`/`anthropic-ai`), CNA does not block AI
crawlers. It explicitly `Allow:`s several `/api/v1/*-feed` endpoints,
including the RSS feed used here.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://www.channelnewsasia.com/<section>/<slug>-<id>`

A single `<script type="application/ld+json">` block is present, but unlike
most of this portfolio it is a **`@graph` array** (`{"@context": ...,
"@graph": [...]}`) rather than a bare dict or list of dicts -- the extractor
scans the array for the node with `"@type": "NewsArticle"`. That node
carries `headline`, `description` (teaser, not full body), `datePublished`,
`dateModified`, `author` (`{"@type": "Person", "name": ...}` -- for wire
content this is often just `"CNA"`), and `image`.

**Important: the `NewsArticle` node has NO `articleBody` field at all.**
Full text must be read from the HTML: `div.text > div.text-long` blocks (in
document order), each containing bare `<p>` tags. This selector matters
because the raw `.text-long` class alone matches **44 unrelated elements**
per page (CNA reuses it for CSS/JS override snippets scattered through the
page -- `<div class="text-long"><style>...</style></div>` etc.) -- only the
ones nested directly under `div.text` are real body content.

**Most articles have exactly one `div.text > div.text-long` block.**
Longform/brand-studio pieces (observed on a syndicated Financial Times
article, `/experiences/travel-influencers-drive-bookings-6324931`) split the
body across **10 separate blocks** interspersed with ad/embed placeholders
elsewhere in the DOM -- concatenating paragraphs from all matched blocks in
document order reconstructs the full continuous article correctly (verified
by reading the joined text end-to-end, ending on the FT syndication credit
line). The extractor always collects from *all* matched blocks, never just
the first, to handle this.

### 2. Latest headlines — `S2-rss`

`GET https://www.channelnewsasia.com/api/v1/rss-outbound-feed`

Explicitly `Allow:`ed in `robots.txt`. Standard RSS 2.0, ~20 items per
fetch. Fields: `title`, `link`, `guid` (`isPermaLink="false"`, actually the
full article URL, not an opaque ID), `pubDate`, `category` (comma-joined
string when an article has multiple categories, e.g. `"Experiences ,CNA
Luxury ,Travel"` -- not repeated `<category>` tags), `media:thumbnail`
(`url`/`width`/`height` attributes, no text content). `<description>` is
present but **empty on many items** (e.g. straight wire-copy articles) and
populated with a teaser on others (feature/analysis pieces) -- both are
normal, not a parsing failure.

## Paywall behavior

None observed. CNA is Mediacorp's free, ad-supported English news service --
no metering or subscription product exists on the sampled articles
(hard-news wire copy, sport, and one long-form syndicated feature all
returned full `articleBody` text with no truncation marker).

## Known limits

- `author` on the `NewsArticle` node is frequently just the org name
  (`"CNA"`) rather than an individual byline -- this reflects how CNA
  attributes wire-service and desk-written content, not a bug.
- No explicit paywall/premium marker exists in the JSON-LD vocabulary here
  (no `isAccessibleForFree` field) -- if CNA ever introduces a subscription
  tier, this extractor would need a new signal to detect it (see
  `derspiegel-scraper` for an example of hard-paywall detection pattern to
  adapt).

## Diff cadence

Quarterly smoke test recommended. Specifically re-check that
`div.text > div.text-long` still isolates real body content -- CNA's Drupal
theme scatters many decoy `.text-long` elements per page (44 in the sampled
article), so a theme change that alters the `div.text` wrapper structure
would silently truncate or empty the extracted body.
