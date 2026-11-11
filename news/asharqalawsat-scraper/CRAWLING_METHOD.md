# Crawling Method — Asharq Al-Awsat (English edition)

**Last verified:** 2026-08-26

## robots.txt / Claude screening

`https://aawsat.com/robots.txt` and `https://english.aawsat.com/robots.txt`
return the **identical, byte-for-byte** Drupal-generated file:

```
User-agent: *
Disallow: /core/
Disallow: /profiles/
Disallow: /README.txt
Disallow: /web.config
Disallow: /admin/
Disallow: /comment/reply/
Disallow: /filter/tips
Disallow: /node/add/
Disallow: /search/
Disallow: /user/register
Disallow: /user/password
Disallow: /user/login
Disallow: /user/logout
Disallow: /media/oembed
Disallow: /*/media/oembed
... (index.php mirrors of the above)
Disallow: /json/
Disallow: /undefined

Sitemap: https://aawsat.com/sitemap.xml
Sitemap: https://aawsat.com/googlenews.xml
```

Only one `User-agent:` group exists in the entire file on both hosts, so
the documented Babak-14 multi-group-parser trap (several `User-agent:`
lines sharing one `Disallow:` block below them) cannot apply here. No
`Claude`, `ClaudeBot`, `Claude-Web`, `Claude-User`, `Claude-SearchBot`, or
`anthropic-ai` token appears anywhere in the file (case-insensitive
check), and there is no blanket `Disallow: /`. None of the disallowed
paths overlap with article URLs (`/<category>/<id>-<slug>`) or the
homepage this actor uses. Independently re-verified via `curl_cffi`
(chrome124) as required — both fetches returned HTTP 200 with the body
above.

## WAF

`english.aawsat.com` sits behind **Cloudflare** (`server: cloudflare`
response header on every request, `cf-ray` present) but shows **no active
challenge**. `curl_cffi` `chrome124` gets a clean HTTP 200 on the
homepage (~211 KB), every sampled article (~85-135 KB), and a battery of
synthetic 404 tests (right ID + wrong slug, and a 7-digit out-of-range
ID) — no challenge body, no CAPTCHA interstitial, no 403 at any point.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default. No profile ladder escalation was needed.

## Language scoping — Arabic vs English

`aawsat.com` (root domain) serves the **Arabic** edition. The **English**
edition lives at a separate subdomain, `english.aawsat.com` — confirmed
by fetching `https://aawsat.com/english` and `https://aawsat.com/english/`,
both of which 200-redirect to `https://english.aawsat.com/`. This actor
targets **`english.aawsat.com` exclusively** — every article URL and the
homepage-listing "latest" mode both operate on that subdomain only. No
Arabic content is scraped.

**Quirk:** the two editions share sitemap infrastructure hosted on the
root `aawsat.com` domain. `aawsat.com/googlenews.xml` and
`aawsat.com/sitemap.xml` (advertised via `Sitemap:` in robots.txt on
*both* hosts) contain only Arabic titles/URLs. `english.aawsat.com` has
its *own* `/googlenews.xml`, but it is broken/mismapped: every `<loc>`
tag is empty and every `<news:title>` is still in Arabic, despite each
entry carrying `<news:language>en</news:language>`. This makes both
sitemap variants unusable for English-language "latest" mode — see
below.

## Data sources

### 1. Article pages — `S1-jsonld+html`

`GET https://english.aawsat.com/<category>/<id>-<slug>`

Exactly **one** `<script type="application/ld+json">` block per article,
shaped as `{"@context": "https://schema.org", "@graph": [ {...} ]}` with
a single node inside `@graph`. The node's `@type` is **not constant**:
confirmed `NewsArticle` for hard-news/business/sport pieces and
`OpinionNewsArticle` for opinion columns (both valid schema.org
`NewsArticle` subtypes) across 5 sampled articles (business, opinion,
sports, interview). The extractor matches any node whose `@type` string
*contains* "NewsArticle" rather than an exact match, to tolerate other
subtypes not sampled (`ReportageNewsArticle`, `AnalysisNewsArticle`,
etc.) that this CMS family plausibly also emits.

Fields present on the node: `headline`, `name` (duplicate of headline),
`description`, `image` (`ImageObject` with `url`), `datePublished`,
`dateModified`, `author` (a single `Person` object — generic
`"Asharq Al Awsat"` for staff/wire news, a real named columnist e.g.
`"Nabil Amr"` for opinion pieces, each with its own `url`/`logo`),
`publisher` (an `Organization`), and on at least one opinion sample an
`about` array (`["The November Elections: Different Inputs", "Different
Outputs"]` — this is the headline auto-split on a comma by the CMS, not a
curated topic-tag list; passed through as-is, present as `null` when
absent).

**Missing: `articleBody`.** Neither `NewsArticle` nor `OpinionNewsArticle`
nodes carry the full article text in ld+json on this CMS (unlike
gulfnews-scraper, arabnews-scraper, omanobserver-scraper, and
thenational-scraper in this portfolio, all of which get `articleBody`
directly from ld+json). Full text instead comes from HTML: every article
page has exactly one element with `id="article_node_id"` (a
`div.entry-content` node also carrying `data-nid`/`data-url`/
`data-bundle`/`data-title` attributes). The extractor collects the text
of every `<p>` tag found **anywhere inside it** (`find_all("p")`,
recursive) rather than only direct children, because the DOM nesting
depth of `<p>` tags under `#article_node_id` differs by content bundle:
- `data-bundle="article"` (regular news): `<p>` tags sit as **direct**
  children of `#article_node_id`.
- `data-bundle="opinion"`: `<p>` tags are nested **one level deeper**,
  inside a `div.field--name-body.field--type-text-with-summary` wrapper.

A direct-children-only selector (the pattern used by saudigazette-scraper
for its `div.body-div`) would silently return an empty body on every
opinion piece, so this extractor deliberately searches recursively
instead. Ad-slot `<div class="block-wrapper">` siblings interleaved
between paragraphs (Google-ad placeholder divs) carry no `<p>` text of
their own, so they contribute nothing and need no special exclusion —
confirmed by an exact paragraph-count match against the raw HTML on both
sampled bundle types (9 paragraphs for the Humain/Mistral news piece, 18
for the November-elections opinion piece).

**Quirk — `publisher.name` is Arabic even on the English edition:** every
sample's `publisher` node has `"name": "الشرق الأوسط"` (the outlet's
Arabic name), never an English "Asharq Al-Awsat" string — a CMS-wide
constant unrelated to article language. Passed through as-is per the
portfolio's raw-passthrough/minimal-renaming convention, not translated.

**`category`** is not present in ld+json at all (no `articleSection`
field on this CMS). Pulled instead from HTML: the closest
`div.entry-article` ancestor of `#article_node_id` contains a
`div.entry-category > a` link whose text is the section name (`Business`,
`Opinion`, `Sports`, etc.) — present and correctly scoped on every sample
of both bundle types, verified not to pick up the category of unrelated
"related articles" recommendation widgets embedded further down the same
page (those widgets reuse the `entry-category` class but sit outside any
`div.entry-article` that itself contains an `#article_node_id`
descendant, since `find_parent` walks up from the article's own body
element).

### 2. Latest headlines — `S2-html-listing`

No usable English-language RSS/sitemap feed exists (see "Language
scoping" above for why the site's `Sitemap:`-advertised feeds are
Arabic-only or broken on the English subdomain). `/feed` on
`english.aawsat.com` returns HTTP 200 but is the homepage HTML, not an
RSS/Atom document.

Instead, `GET https://english.aawsat.com/` (homepage) is scraped for
`<div role="article" typeof="schema:Article">` blocks — RDFa markup
Drupal emits for every teased-article widget on the page, the same
pattern used for the homepage-fallback approach in omanobserver-scraper/
chinadaily-scraper/jamaicagleaner-scraper when RSS/sitemap discovery is
broken, but with a cleaner selector available here:
- `about` attribute on the block = the article's canonical URL
- `data-nid` attribute = the numeric node ID
- a nested `<span property="schema:name" content="...">` tag carries the
  **exact headline text, already HTML-entity-decoded, with no teaser
  text glued on** — a cleaner signal than an anchor's `title=` attribute
  or `get_text()` (both of which risked the "hero card glues headline +
  teaser" problem documented for omanobserver-scraper), since this RDFa
  span exists purely to carry the headline metadata.

One homepage fetch yielded 57 raw `div[role=article]` blocks, deduplicating
to **44 unique articles** by `data-nid` (the same story appears in
multiple homepage widgets — "top story," category rail, "most read," etc.
— sharing one node ID). Homepage DOM order does **not** reliably match
recency (spot-checked: `5311056` appeared after `5310804`/`5310876` in
document order despite being the highest/newest ID), so the extractor
explicitly sorts the deduplicated set descending by numeric `data-nid`
rather than trusting document order — same defensive pattern as
omanobserver-scraper.

## Paywall behavior

None observed. No `isAccessibleForFree` field in any sampled ld+json
block, no paywall overlay markup, no truncated `articleBody`/HTML body
("..." cutoffs) on any of 5 sampled articles (business/AI news, an
opinion column, a sports piece, an interview, and a spot-check on a
second business piece) — appears fully open-access, consistent with the
rest of this portfolio's Middle East English-language outlets
(gulfnews-scraper, arabnews-scraper, omanobserver-scraper,
saudigazette-scraper).

## 404 behavior

Real HTTP 404s confirmed for two distinct synthetic bad-input cases:
- A 7-digit out-of-range article ID with a fabricated slug
  (`/business/9999999-this-is-a-totally-fake-slug-xyz`) → HTTP 404.
- A **correct, real** article ID paired with a **deliberately wrong**
  slug (`/business/5310876-this-is-a-deliberately-wrong-slug-xyz`, where
  `5310876` is a genuinely published article) → **also HTTP 404.**

This is a meaningful difference from omanobserver-scraper and several
other portfolio sites, where the numeric ID alone resolves the article
and the slug segment is purely cosmetic. On `english.aawsat.com`, **the
full URL (ID + slug) must match** what the CMS generated, or the request
404s — URLs cannot be reconstructed from the ID alone. This actor treats
every input URL as opaque and passes it through verbatim rather than
attempting any ID-only URL reconstruction.

## Known limits

- `category` and `articleType` are HTML/ld+json-derived best-effort
  signals, not a formal upstream taxonomy field — no `articleSection` at
  all exists in ld+json on this CMS.
- `about` is only populated on some opinion-type articles and is a
  CMS-auto-split of the headline, not curated topic tags — most records
  will have `about: null`.
- Only 5 articles sampled in depth (business/AI, opinion, sports,
  interview, one additional business spot-check). A structurally
  different template (e.g. a live-blog, photo-gallery, video-only, or
  cartoon page) was not sampled — if one lacks a `#article_node_id`
  element or an ld+json `NewsArticle`-type node, `UnexpectedShape` raises
  rather than silently returning nothing.
- Latest-mode coverage is capped by whatever fits on one homepage fetch
  (44 unique articles observed) — there is no pagination/"load more"
  mechanism wired into this actor. Requesting `limit` above that count
  simply returns however many unique articles were found.
- Full-URL-required 404 behavior (see above) means stale or hand-edited
  URLs (e.g. from a third-party mirror with a different slug) will fail
  with `_error: "not_found"` even if the numeric ID is valid — unlike
  omanobserver-scraper, this actor does not attempt any recovery for
  that case.

## Diff cadence

Quarterly smoke test recommended. Specifically re-check: (1) whether
`articleBody` has been added to ld+json directly (would let this actor
drop the HTML-fallback dependency), (2) whether `english.aawsat.com`'s
own `/googlenews.xml` has been fixed to carry real English URLs (would be
a strictly better `latest`-mode source than homepage-scraping), and (3)
that the opinion-bundle nested-paragraph DOM structure
(`div.field--name-body` wrapper) hasn't changed, since that's the one
CMS-quirk this extractor depends on non-obvious knowledge of.
