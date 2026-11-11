# Crawling Method — LA Times

**Last verified:** 2026-08-24

## WAF

None detected. `latimes.com` returns 200 on homepage, article pages, and the
site-wide RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.latimes.com/<section>/story/<date>/<slug>`

Each article page emits a single `application/ld+json` `NewsArticle` block
(no `NewsMediaOrganization`/`WebPage` noise blocks like Economic Times). It
carries `articleBody` with the **full plain-text article**, `headline`,
`description`, `author` (array of `Person` objects with `email`/`jobTitle`/
`description` bios — unusually rich), `datePublished`/`dateModified`,
`articleSection`, and `image` (array of `ImageObject`, multiple crops).

**Important caveat — paywall marker present but not enforced in the data:**
every article tested carries `"isAccessibleForFree": false` and a
`"hasPart": {"@type": "WebPageElement", "isAccessibleForFree": false,
"cssSelector": ".paywall"}` block (the standard schema.org paywall-signal
pattern used by many metered-paywall sites to tell Google which portion is
gated). Despite this marker, `articleBody` was **not truncated** in any of
the 5 articles sampled across 4 sections (politics, california, business,
sports) — full text was present every time, including on articles clearly
behind LA Times' subscriber paywall in-browser. This is passed through
verbatim per raw-passthrough convention; it is **not guaranteed to remain
this way** — if LA Times tightens their JSON-LD emission to match the
`cssSelector` marker, `articleBody` could start truncating without any HTTP
status change. No `UnexpectedShape` trigger exists for "body got shorter";
this is a known blind spot, documented here for the next agent who
investigates a sudden drop in average `articleBody` length.

No `__NEXT_DATA__` was found — this site does not expose page state via
Next.js SSR data injection (or does, but it's not needed since JSON-LD
already carries everything required).

### 2. Latest headlines — `S2-rss`

`GET https://www.latimes.com/rss2.0.xml`

Standard RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`, `guid`,
`pubDate`, `description` (HTML-formatted teaser paragraph). Confirmed
chronological and cross-section (politics/california/business/sports items
all appeared, all within the last 3 days as of 2026-08-24) — unlike Economic
Times' default feed, no stale/evergreen items were observed mixed in.

## Paywall behavior

See caveat above — `isAccessibleForFree: false` + `.paywall` cssSelector
marker present on every article, but `articleBody` was full-text on every
sample regardless. Treat as a soft/cosmetic paywall from a scraping
perspective today, but re-verify periodically (see Diff cadence).

## Known limits

- Author bios/emails are personal-ish data (staff `Person` objects with
  direct `@latimes.com` email addresses) — this is publisher-published
  byline metadata already public on the page, not scraped from a private
  source, but downstream consumers building a contacts list from this field
  should be aware of what it is.
- No section-specific RSS feeds were tested; only the site-wide feed is
  wired up, consistent with the portfolio's stated preference for the one
  documented always-live feed over a section-ID list that could rot.

## Diff cadence

Quarterly smoke test recommended, with special attention to `articleBody`
length: re-run `test_local.py` against a fresh article URL from at least 2
different sections and confirm `articleBody` is still full-length (thousands
of characters, not a ~500-800 char teaser). If LA Times starts enforcing the
`.paywall` marker server-side, `articleBody` will visibly shrink without any
HTTP status or JSON-LD shape change — this failure mode will NOT raise
`UnexpectedShape` on its own.
