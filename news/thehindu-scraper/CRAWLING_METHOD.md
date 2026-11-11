# Crawling Method — The Hindu

**Last verified:** 2026-08-24

## WAF

`thehindu.com` is fronted by Cloudflare (`cf-ray` header present) but **no
active challenge** was observed. `curl_cffi` `chrome124` gets a clean 200 on
homepage, article pages, and the site-wide RSS feed -- no challenge body, no
403.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-microdata`

`GET https://www.thehindu.com/<section>/<slug>/article<id>.ece`

**Unusual for this portfolio: no `application/ld+json` at all.** The string
`"ld+json"` does not appear anywhere in sampled article HTML. Structured
data is emitted as **schema.org microdata** instead (`itemprop`/`itemscope`
attributes on plain tags, the pre-JSON-LD schema.org convention):

- `headline`, `description`, `articleSection`, `datePublished`,
  `dateModified` are all `<meta itemprop="..." content="...">` tags --
  read the `content` attribute.
- `itemprop="author"` exists (`<span itemprop="author" itemscope
  itemtype="https://schema.org/Person"></span>`) but was an **empty
  placeholder** on every sampled article (3/3), including bylined wire
  pieces -- the actual author name is NOT inside this span. The visible
  byline lives in a plain `.author-name` class element elsewhere on the
  page (e.g. `"AFP"` for wire content) -- extractor falls back to this
  selector.
- Full article text: `div[itemprop="articleBody"] > p` (bare `<p>` tags).
  "Also read" inline-link boxes (`div.also-read.print-hide`) and
  subheadings (`h4.sub_head`) are separate sibling elements at the same
  level and are excluded automatically since only `<p>` tags are collected
  (subheading text is therefore not preserved as a marker in the joined
  body -- acceptable tradeoff, documented here for the next agent who might
  want to re-add it).

No paywall marker (`isAccessibleForFree` or similar) exists in this
microdata vocabulary. The literal strings `"paywall"` and `"subscriber"`
appear in page HTML (a generic subscribe-CTA banner present sitewide) but
`articleBody` was full-length (1,800-4,000+ characters) on every sampled
article regardless -- The Hindu does have a subscription product for some
premium content in the live site, but no sampled URL (general news +
sports, 3 articles) exposed a truncation signal. Revisit if a
"Premium"-badged article is specifically targeted (see Known limits).

### 2. Latest headlines — `S2-rss`

`GET https://www.thehindu.com/feeder/default.rss`

Standard RSS 2.0 feed, 60 items per fetch (larger than most of the
portfolio's news feeds), CDATA-wrapped `title`/`description`/`link`
(transparently unwrapped by the XML parser). Fields: `title`, `link`,
`guid` (`article-<id>` format, not the full URL), `pubDate`, `description`,
`categories` (single `<category>` per item in samples).

## Paywall behavior

No truncation observed in this recon (see caveat above re: premium content
not specifically sampled).

## Known limits

- Only 3 articles sampled (2 sports, 1 national-news breaking item), all
  from the general RSS feed -- none were premium/subscriber-only content.
  If The Hindu's paywalled tier behaves differently (server-side
  truncation), this actor would currently return whatever HTML is served
  without a `_paywalled` flag -- unlike `derspiegel-scraper`, no explicit
  gate-detection was implemented since no gated sample was found to design
  against. Revisit if this becomes an issue in production.
- `h4.sub_head` subheading text is dropped from the joined `articleBody`
  (only `<p>` tags are collected).

## Diff cadence

Quarterly smoke test recommended. Specifically re-check whether
`itemprop="author"` is still consistently empty (if The Hindu ever
populates it, prefer it over the `.author-name` class fallback since
microdata `itemprop` fields are generally more stable across redesigns than
presentation classes).
