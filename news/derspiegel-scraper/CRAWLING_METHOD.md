# Crawling Method — Der Spiegel

**Last verified:** 2026-08-24

## WAF

None detected. `spiegel.de` returns 200 on homepage, article pages, and the
site-wide RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck` markers, no challenge body. Responses carry a
`via: 1.1 google` header (Google Cloud CDN front), not an anti-bot vendor.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default.

## Data sources

### 1. Article pages — `S1-html` (JSON-LD metadata + HTML body, both required)

`GET https://www.spiegel.de/<section>/<slug>-a-<uuid>`

Like `nypost-scraper`, this is a **hybrid** extraction:

- The page emits a single `application/ld+json` block as a JSON **list**
  (`[NewsArticle, BreadcrumbList]`, not a bare dict -- extractor scans list
  items for `@type: NewsArticle`). It carries `headline`, `author`, all
  three date fields, `articleSection`, `keywords`, `image`, `publisher`, and
  critically **`isAccessibleForFree`** (real JSON boolean, not a string) --
  but **no `articleBody`**.
- `__NEXT_DATA__` is absent.

Full text is pulled from HTML: `div[data-area="body"] > div[data-area="text"]
> p`. This is a **reliable, explicit signal**, not a heuristic:

- **Free articles** — `div[data-area="body"]` contains one or more
  `div[data-area="text"]` children (each a `RichText` block with `<p
  data-forward-id="...">` paragraphs), interspersed with unlabeled ad-slot
  divs and a `<section data-area="related_articles">` at the end (excluded
  by construction since the selector targets `div[data-area="text"]`
  specifically). Paragraphs joined in document order.
- **Premium ("SPIEGEL+") articles** — `div[data-area="body"]` contains
  exactly one `div[data-area="paywall"]` and **zero** `div[data-area="text"]`
  elements. No teaser paragraphs are exposed at all (confirmed on the one
  premium sample tested: body text was 0 characters, only the paywall CTA
  div was present). This is a **hard paywall** — unlike `washingtonpost-
  scraper`/`ft-scraper`/`business-standard-scraper` (soft/cosmetic paywalls
  where `articleBody` is present but the site *intends* to gate it), Spiegel
  genuinely withholds the content server-side.

`isAccessibleForFree` and the presence/absence of `div[data-area="text"]`
agreed on both sampled cases (one `true`+text-divs, one `false`+paywall-div)
-- the extractor doesn't rely on the JSON-LD flag alone since it's metadata
that could theoretically drift independently of the actual HTML gate; it
checks the HTML directly and derives `_paywalled` from what's actually
observed, with `isAccessibleForFree` passed through as raw metadata too.

**Output contract for premium articles:** `articleBody: null`,
`_paywalled: true`. No fabricated/truncated text is emitted — this is a
deliberate divergence from the raw-passthrough-of-whatever-exists pattern
used elsewhere in the portfolio, justified by the "fail loud, never fail
silent" principle: a consumer checking `_paywalled` gets an honest signal
instead of an empty string that could be mistaken for a scraping bug.

### 2. Latest headlines — `S2-rss`

`GET https://www.spiegel.de/schlagzeilen/index.rss`

Standard RSS 2.0 site-wide headline feed, 30 items per fetch, mixed
sections (ausland/panorama/kultur/wirtschaft/sport observed). Fields:
`title`, `link` (`#ref=rss` tracking suffix stripped), `guid`, `pubDate`,
`description`, `categories` (single `<category>` per item in samples). A
`<content:encoded>` tag is also present but its text is identical to
`<description>` on every sampled item (not a longer/full version), so it's
not surfaced as a separate field to avoid implying it carries more data than
it does.

## Paywall behavior

Mixed. Both free ("Schlagzeilen"-tier news briefs) and premium ("SPIEGEL+"
long-form/analysis) content exist on the same domain, same URL pattern, same
JSON-LD shape (differentiated only by `isAccessibleForFree` + presence of
`div[data-area="text"]` vs `div[data-area="paywall"]`). Expect a meaningful
fraction of URLs from `latest` mode or general crawling to come back with
`_paywalled: true` and no body text -- this is normal, not an error.

## Known limits

- No section-specific RSS feeds were tested; only the site-wide headline
  feed is wired up.
- Only one premium article was sampled during recon -- the paywall-div
  detection pattern should be re-verified against a second SPIEGEL+ sample
  if this actor sees a lot of use, to confirm the shape doesn't vary by
  section (e.g. opinion columns vs investigative long-reads).

## Diff cadence

Quarterly smoke test recommended. Test both a free and a premium article URL
(search `spiegel.de/wirtschaft/` or `spiegel.de/meinung/` for "SPIEGEL+"
badge text on the section front page to find a fresh premium sample) and
confirm `_paywalled` still tracks correctly with `isAccessibleForFree`.
