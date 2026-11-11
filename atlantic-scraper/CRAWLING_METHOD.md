# Crawling Method — The Atlantic

**Last verified:** 2026-08-24

## WAF

None detected. `theatlantic.com` returns 200 on homepage, article pages, and
the "best of" feed under `curl_cffi` `chrome124` impersonation, no
`cf-ray`/`x-datadome`/`_abck`/Fastly markers, no challenge body. A homepage
GET is done first for hygiene/consistency with the rest of the portfolio, not
because it's required.

**TLS profile pinned:** `chrome124`, consistent with the portfolio-wide
default (avoids the most-blocklisted `chrome131` profile even when it also
works).

## Data sources

### 1. Article pages — `S1-urql` (primary; JSON-LD alone is insufficient here)

`GET https://www.theatlantic.com/<section>/<year>/<month>/<slug>/<id>/`

**This is the only actor in the portfolio where JSON-LD does not carry the
full article text.** The page does emit a `NewsArticle` ld+json block, but
it is metadata-only (`headline`, `dateModified`, `isAccessibleForFree`,
`hasPart`/`.paywall` marker — no `articleBody` key at all). Per the
extraction priority order (JSON-LD > `__NEXT_DATA__` > Apollo state > HTML),
this actor escalates one tier further than most of the portfolio:

1. Parse `__NEXT_DATA__` (Next.js SSR state).
2. Read `props.pageProps.urqlState` — a GraphQL client (`urql`, an
   Apollo-state equivalent) cache, keyed by opaque numeric hashes. **Multiple
   cache entries exist per page** (observed: 4). Only one of them carries the
   full `article.content` array — the others are partial/stub versions of
   the same article (e.g. just `id`/`hasMeter`/`url`) left over from earlier
   render passes. `_find_article_cache()` in `extractor.py` scans all
   entries and picks the one where `article.content` is truthy.
3. `article.content` is a list of typed blocks (`ArticleParagraphContent`,
   `ArticleOverflowInlineImage`, etc.). Concatenate the `innerHtml` of every
   `ArticleParagraphContent` block and strip HTML tags to get plain-text
   `articleBody` (confirmed 12k-18k characters across 5 samples spanning
   ideas/culture verticals).

**Paywall caveat — same pattern as LA Times/Vox:** every article carries
`article.hasMeter: true` (Atlantic's metered-subscription flag), but full
`content` blocks were present and untruncated on every one of the 5 articles
sampled. Treat as soft/cosmetic from a scraping perspective today; if
Atlantic starts gating `content` server-side for meter-exhausted requests,
`extract_article` will raise `UnexpectedShape` (0 paragraph blocks found)
rather than emit an empty/partial record.

Also extracted: `dek` (subhead/description), `authors` (array, often 2+
co-bylines), `tags`, `primaryCategory`, `datePublished`/`dateModified`.

### 2. Latest headlines — `S2-atom` (non-standard: Atom, not RSS 2.0)

`GET https://www.theatlantic.com/feed/best-of/`

Like Vox in this portfolio, this feed is **Atom**
(`<feed xmlns="http://www.w3.org/2005/Atom">`, `<entry>` elements), not RSS
2.0 — the shared `extract_rss_items` RSS-2.0 parser used elsewhere in the
portfolio silently returns 0 items on it. A dedicated Atom parser reads
`<entry>/<link rel="alternate" href="...">`, `<published>`, `<updated>`,
`<summary>`, and **multiple** `<author><name>` tags (co-bylines, returned as
an `authors` array — richer than Vox's single-author feed).

**Notable:** this feed's own `<content type="html">` element already
contains the **full article body** as HTML — redundant with the `S1-urql`
path. This actor intentionally does NOT surface that field in `latest` mode,
keeping `description` as a teaser-only summary for interface consistency
with every other actor's `latest` mode in this portfolio. Use `article` mode
against the entry's `link` if full text is needed.

Confirmed chronological across ideas/culture verticals mixed together
(2026-08-24 spot check, 25 entries returned per fetch).

## Paywall behavior

`hasMeter: true` on every sampled article; full paragraph content present
regardless. See caveat above.

## Known limits

- If Atlantic changes the number/order of `urqlState` cache entries, the
  "pick the one with `content`" heuristic could need adjustment — it's
  robust to added/removed stub entries but assumes at least one entry always
  carries the full article.
- `tags`/`primaryCategory` are much thinner than other portfolio actors'
  `keywords`/`articleSection` — The Atlantic's GraphQL schema doesn't expose
  as rich a taxonomy per article.

## Diff cadence

Quarterly smoke test recommended: re-run `test_local.py` against a fresh
article URL and confirm `contentBlockCount` > 0 and `articleBody` is still
full-length (thousands of characters). If The Atlantic redesigns their
Next.js/GraphQL data layer, `extract_article` will raise `UnexpectedShape`
and the run will fail loudly rather than emit corrupt records.
