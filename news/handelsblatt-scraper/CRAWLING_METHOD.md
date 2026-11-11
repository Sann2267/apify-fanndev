# Crawling Method — Handelsblatt

**Last verified:** 2026-08-24

## WAF

None detected. `handelsblatt.com` returns 200 on homepage, article pages, and
the site-wide "Schlagzeilen" (headlines) RSS feed under `curl_cffi`
`chrome124` impersonation, no `cf-ray`/`x-datadome`/`_abck`/Fastly markers,
no challenge body. A homepage GET is done first for hygiene/consistency with
the rest of the portfolio, not because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.handelsblatt.com/<section>/<subsection>/<slug>/<id>.html`

Each article page emits a single `application/ld+json` `NewsArticle` block
(bare dict). It carries `articleBody` with the **full plain-text article**
(1,300-4,600 characters across 6 of 8 samples — see Known limits for the
other 2), `headline`, `creator` (array of plain name strings) + `author`
(array of `Person`/`Organization` objects with profile `url` and headshot
`image` — richer dual representation of the byline), `articleSection`,
`keywords`, `datePublished`/`dateModified`.

**Paywall marker present, not enforced in the data — same pattern as LA
Times/Vox/The Atlantic in this portfolio:** every article carries
`"isAccessibleForFree": false` (real JSON boolean here, unlike Bangkok
Post's string) and a `"hasPart": {"@type": "WebPageElement",
"isAccessibleForFree": "False", "cssSelector": ".hmg-paywalled"}` block.
Despite this, `articleBody` was full-length on 6 of 8 sampled articles —
truncation was NOT observed to correlate with this flag (both 0-body and
full-body samples carried the same `isAccessibleForFree: false`). Passed
through verbatim per raw-passthrough convention; re-verify periodically per
the portfolio-wide soft-paywall caveat (see LA Times' `CRAWLING_METHOD.md`).

No `__NEXT_DATA__` was found — this site does not expose page state via
Next.js SSR data injection.

### 2. Latest headlines — `S2-rss`

`GET https://www.handelsblatt.com/contentexport/feed/schlagzeilen`

Standard RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`, `guid`,
`pubDate`, `description`. Confirmed chronological across politik/finanzen
sections mixed together (2026-08-24 spot check, 8 samples). Some `title`
values carry a live-blog prefix (`"+++ USA +++: ..."`), passed through
verbatim.

## Paywall behavior

See caveat above. `isAccessibleForFree: false` + `.hmg-paywalled` marker on
every article, but truncation only observed on 2 of 8 samples and it did not
correlate with the paywall flag — see Known limits for the actual cause.

## Known limits

- **2 of 8 sampled articles had no `articleBody` key at all** (not an empty
  string — the key was simply absent), both short wire-brief/live-ticker
  style items (`"+++ USA +++: ..."` prefix, one linked from the
  `Ukraine-Krieg` live-ticker). This appears to be a content-type
  distinction (live-blog/ticker items vs. full feature articles) rather than
  a paywall or extraction failure — `extract_article` still succeeds and
  returns the record with every other field intact, just without
  `articleBody`. Downstream consumers should treat a missing `articleBody`
  as "this was a short-form item," not as an error.
- `creator` (plain name strings) and `author` (rich objects) both carry the
  byline redundantly — kept as-is per raw-passthrough convention.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
*feature-length* article URL (not a live-ticker item) and confirm the
`NewsArticle` ld+json block still carries `articleBody`. If Handelsblatt
redesigns the page, `extract_article` will raise `UnexpectedShape` and the
run will fail loudly rather than emit corrupt records.
