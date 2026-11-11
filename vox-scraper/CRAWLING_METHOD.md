# Crawling Method — Vox

**Last verified:** 2026-08-24

## WAF

None detected. `vox.com` returns 200 on homepage, article pages, and the
site-wide feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.vox.com/<vertical>/<id>/<slug>`

Each article page emits a single `application/ld+json` `NewsArticle` block
(bare dict, not wrapped in a list — unlike Axios/Business Standard/Economic
Times in this portfolio). It carries `articleBody` with the **full
plain-text article** (confirmed 9-12k characters across 5 sampled URLs,
across the-highlight/podcasts/future-perfect/america-actually/logoff-
newsletter verticals), `headline`, `description`, `keywords`,
`articleSection`, `author` (array with `name` + profile `url`),
`datePublished`/`dateModified`, and a `speakable` block (text-to-speech CSS
selector hint, unique to Vox in this portfolio — not currently surfaced as a
separate field, passed through as part of the raw dict).

Every sampled article carries `"isAccessibleForFree": false` (Vox has a
metered/donation-supported model) but `articleBody` was **not truncated** in
any of the 5 samples — same soft-paywall-marker-but-full-text pattern
observed on LA Times in this portfolio. See LA Times' `CRAWLING_METHOD.md`
for the caveat this implies (worth re-verifying periodically, not guaranteed
to hold forever).

### 2. Latest headlines — `S2-atom` (non-standard: Atom, not RSS 2.0)

`GET https://www.vox.com/rss/index.xml`

**Important:** despite the `.xml` extension and typical "RSS feed" framing,
this is an **Atom feed** (`<feed xmlns="http://www.w3.org/2005/Atom">`,
`<entry>` elements, not `<item>`). This is the only outlet in the portfolio
using Atom instead of RSS 2.0 for its `latest`-mode feed — the shared
`extract_rss_items` RSS-2.0 parser used by every other actor in this
portfolio returns 0 items on this feed silently (BeautifulSoup's `find_all
("item")` simply finds nothing, no error raised). A dedicated Atom parser
(`extract_rss_items` in this actor's `extractor.py`, same function name for
interface consistency with the rest of the portfolio but different
implementation) reads `<entry>/<link rel="alternate" href="...">`,
`<published>`, `<updated>`, `<summary>` (HTML-escaped teaser, ends in an
ellipsis entity `&#8230;`), `<author>/<name>` (single author, unlike Axios'
multi-`dc:creator`), and `<category term="...">` tags.

Confirmed chronological across the-highlight/podcasts/future-perfect
verticals mixed together (2026-08-24 spot check).

## Paywall behavior

`isAccessibleForFree: false` present on every article tested, but
`articleBody` was full-text on every sample. Same caveat as LA Times: treat
as soft/cosmetic from a scraping perspective today, re-verify periodically.

## Known limits

- If Vox ever migrates `latest` mode back to RSS 2.0 or a different Atom
  variant, `extract_rss_items` here will need re-verification — it does not
  share code with the RSS-2.0 implementation used elsewhere in the
  portfolio, so a schema change here does not affect other actors and vice
  versa.
- `speakable` (text-to-speech selector block) is passed through raw but not
  documented as a first-class output field — it's schema.org noise for this
  actor's purposes.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py latest` and confirm
entries are still parsed via `<entry>` (not silently zero, which is what
happens if Vox switches back to RSS 2.0 without this actor being updated to
detect the format change). Also re-check `articleBody` length on a fresh
article per the LA Times-style paywall caveat above.
