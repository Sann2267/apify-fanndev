# Crawling Method — Bangkok Post

**Last verified:** 2026-08-24

## WAF

None detected. `bangkokpost.com` returns 200 on homepage, article pages, and
the top-stories RSS feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-jsonld` (primary, only strategy needed)

`GET https://www.bangkokpost.com/<section>/<subsection>/<id>/<slug>`

Each article page emits a single `application/ld+json` `NewsArticle` block
(bare dict). It carries `articleBody` with the **full plain-text article**
(1,600-4,500 characters across 5 samples spanning thailand/general and
business/general sections), `headline`, `description`, `author` (array of
`Person`, frequently a shared byline like `"Online Reporters"` rather than an
individual name), `datePublished`/`dateModified`, `copyrightHolder`/
`copyrightYear`, `sourceOrganization` (e.g. `"Reuters"` on wire-service
pieces), and `image`.

**Quirk:** `isAccessibleForFree` is present but its value is the **string**
`"True"`/`"False"` (capitalized, quoted), not a JSON boolean `true`/`false`
like every other outlet in this portfolio that carries this field (LA Times,
Vox). Downstream consumers doing a strict boolean comparison need to handle
this — passed through verbatim per raw-passthrough convention, not
normalized. All 5 samples tested were `"True"` (free content); no
`"False"`/paywalled sample was encountered to confirm `articleBody` behavior
under that state.

No `__NEXT_DATA__` was found — this site does not expose page state via
Next.js SSR data injection.

### 2. Latest headlines — `S2-rss`

`GET https://www.bangkokpost.com/rss/data/topstories.xml`

Standard RSS 2.0 (`<channel>/<item>`), fields: `title`, `link`, `pubDate`,
`description` (teaser paragraph, sometimes wrapped in stray `&nbsp;` /
newline noise as authored). **No `<guid>` tag is present in this feed** —
unlike every other RSS-based actor in this portfolio, `guid` is always
`null` here. Confirmed chronological across thailand/general and business/
general sections mixed together (2026-08-24 spot check).

## Paywall behavior

`isAccessibleForFree: "True"` (string) observed on every sampled article,
`articleBody` full-text on all of them. No paywalled sample was encountered
during recon to confirm behavior on `"False"` content.

## Known limits

- `guid` is always `null` in `latest` mode — use `link` as the dedup key
  instead if building an incremental pipeline.
- `isAccessibleForFree` is a string, not a boolean (see Quirk above).
- `author` is frequently a shared desk byline ("Online Reporters") rather
  than an individual reporter.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm the `NewsArticle` ld+json block still carries
`articleBody`. If Bangkok Post redesigns the page, `extract_article` will
raise `UnexpectedShape` and the run will fail loudly rather than emit corrupt
records.
